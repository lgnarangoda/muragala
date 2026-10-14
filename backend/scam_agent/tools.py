"""Deterministic tools the analysis agent can call."""
import json
import pathlib
import re

from google.cloud import webrisk_v1

_DATA = pathlib.Path(__file__).resolve().parent.parent / "data"
_PROHIBITED = json.loads((_DATA / "cbsl_prohibited.json").read_text(encoding="utf-8"))
_webrisk = None


def _webrisk_client():
    global _webrisk
    if _webrisk is None:
        _webrisk = webrisk_v1.WebRiskServiceClient()
    return _webrisk


def check_url(url: str) -> dict:
    """Checks one URL against Google Web Risk. Returns whether it is a known
    phishing, malware or unwanted-software site."""
    if not url.startswith(("http://", "https://")):
        url = "http://" + url
    try:
        resp = _webrisk_client().search_uris(
            uri=url,
            threat_types=[
                webrisk_v1.ThreatType.SOCIAL_ENGINEERING,
                webrisk_v1.ThreatType.MALWARE,
                webrisk_v1.ThreatType.UNWANTED_SOFTWARE,
            ],
        )
        threats = [webrisk_v1.ThreatType(t).name for t in resp.threat.threat_types]
        return {"url": url, "flagged": bool(threats), "threats": threats}
    except Exception as e:  # never crash the pipeline
        return {"url": url, "flagged": False, "error": str(e)}


# Company-form words are dropped before matching; generic words alone never
# count as a match ("Lanka", "Global", "Bank" must not hit a listed entity).
_COMPANY_WORDS = {"pvt", "private", "ltd", "limited", "plc", "co", "company", "inc", "the"}
_GENERIC = {
    "bank", "ceylon", "lanka", "sri", "international", "investment", "investments",
    "capital", "app", "group", "holdings", "global", "finance", "trading", "care",
    "life", "online", "advertising", "education", "centre", "center", "society",
    "success", "health", "business", "school", "foundation", "film", "production",
    "lifestyle", "pro", "smart", "win", "fast", "net", "block", "chain", "sport",
    "of", "and", "sl", "dt", "zs",
}


def _norm(s: str) -> str:
    words = re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).split()
    return " ".join(w for w in words if w not in _COMPANY_WORDS)


def _host(d: str) -> str:
    d = re.sub(r"^[a-z]+://", "", (d or "").strip().lower())
    d = d.split("/")[0].split(":")[0]
    return d[4:] if d.startswith("www.") else d


def _keys(e):
    """Normalized name + aliases, minus keys made only of generic words."""
    official = _norm(e["name"])
    out = {}
    for raw in [e["name"]] + e.get("aliases", []):
        k = _norm(raw)
        distinctive = [w for w in k.split() if w not in _GENERIC]
        if len(k) >= 4 and distinctive:
            # the full official name (2+ words) counts as a strong match
            full = k == official and len(k.split()) >= 2
            out[k] = max(len(distinctive), 2 if full else 0)
    return out


_ENTITY_KEYS = [(e, _keys(e)) for e in _PROHIBITED]


def match_prohibited_entity(names: list[str], domains: list[str]) -> dict:
    """Checks company names and web domains against the Central Bank of
    Sri Lanka lists: prohibited schemes (Banking Act Section 83C) and
    companies found taking deposits illegally (Finance Business Act).
    Each hit has confidence "high" (exact domain, or a distinctive multi-word
    name) or "medium" (one distinctive word, e.g. "Windex", which can also
    be an unrelated business)."""
    hits = []
    for e, keys in _ENTITY_KEYS:
        base = {"entity": e["name"], "category": e.get("category", ""),
                "source_url": e["source_url"]}
        for n in names or []:
            padded = f" {_norm(n)} "
            # whole-phrase match, listed key inside the extracted name only
            best = max((score for k, score in keys.items() if f" {k} " in padded), default=0)
            if best:
                hits.append({**base, "matched": n, "confidence": "high" if best >= 2 else "medium"})
        for d in domains or []:
            h = _host(d)
            if h and any(h == dom.lower() or h.endswith("." + dom.lower()) for dom in e.get("domains", [])):
                hits.append({**base, "matched": d, "confidence": "high"})
    return {"found": bool(hits), "hits": hits}


_SIGNALS = {
    "urgency": ["urgent", "immediately", "today only", "ikmanin", "ada ma", "ඉක්මනින්", "අදම"],
    "secrecy": ["don't tell", "kiyanna epa", "කියන්න එපා", "secret"],
    "authority": ["police", "customs", "cbsl", "central bank", "court", "cid", "පොලිස්", "රේගු", "මහ බැංකු"],
    "guaranteed_returns": ["guaranteed", "guarantee", "double", "daily profit", "ලාභ", "සහතික"],
    "payment_request": ["salli ewanna", "ewanna", "transfer", "deposit", "pay now", "fee", "ගෙවන්න", "එවන්න"],
    "channel_switch": ["whatsapp", "telegram", "join group", "join karanna"],
    "credential_request": ["otp", "pin", "password", "cvv"],
    "app_install": [".apk", "install", "download the app"],
}


def rule_signals(text: str) -> dict:
    """Finds common manipulation patterns in message text: urgency, secrecy,
    authority, guaranteed returns, payment request, channel switch, requests
    for OTP/PIN and requests to install an app."""
    t = (text or "").lower()

    def found(word):
        w = word.lower()
        if w.isascii():  # whole-word match, so "pin" does not match "shopping"
            return re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", t) is not None
        return w in t

    evidence = {k: [w for w in words if found(w)] for k, words in _SIGNALS.items()}
    evidence = {k: v for k, v in evidence.items() if v}
    return {"signals": list(evidence), "evidence": evidence}
