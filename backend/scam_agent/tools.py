import json
import pathlib
from google.cloud import webrisk_v1

_DATA = pathlib.Path(__file__).resolve().parent.parent / "data"
_PROHIBITED = json.loads((_DATA / "cbsl_prohibited.json").read_text(encoding="utf-8"))
_webrisk = webrisk_v1.WebRiskServiceClient()


def check_url(url: str) -> dict:
    """Checks one URL against Google Web Risk. Returns whether it is a known
    phishing, malware or unwanted-software site."""
    if not url.startswith(("http://", "https://")):
        url = "http://" + url
    try:
        resp = _webrisk.search_uris(
            uri=url,
            threat_types=[
                webrisk_v1.ThreatType.SOCIAL_ENGINEERING,
                webrisk_v1.ThreatType.MALWARE,
                webrisk_v1.ThreatType.UNWANTED_SOFTWARE,
            ],
        )
        threats = [webrisk_v1.ThreatType(t).name for t in resp.threat.threat_types]
        return {"url": url, "flagged": bool(threats), "threats": threats}
    except Exception as e:  # කවදාවත් pipeline එක crash කරන්න එපා
        return {"url": url, "flagged": False, "error": str(e)}


def match_prohibited_entity(names: list[str], domains: list[str]) -> dict:
    """Checks company names and web domains against the Central Bank of
    Sri Lanka list of prohibited schemes (Banking Act Section 83C)."""
    hits = []
    for e in _PROHIBITED:
        keys = [e["name"].lower()] + [a.lower() for a in e.get("aliases", [])]
        for n in names:
            n_low = n.lower().strip()
            if len(n_low) >= 4 and any(n_low in k or k in n_low for k in keys):
                hits.append({"entity": e["name"], "category": e.get("category", ""), "matched": n, "source_url": e["source_url"]})
        for d in domains:
            if any(d.lower().endswith(dom.lower()) for dom in e.get("domains", [])):
                hits.append({"entity": e["name"], "category": e.get("category", ""), "matched": d, "source_url": e["source_url"]})
    return {"found": bool(hits), "hits": hits}


_SIGNALS = {
    "urgency": ["urgent", "immediately", "today only", "ikmanin", "ada ma", "ඉක්මනින්", "අදම"],
    "secrecy": ["don't tell", "kiyanna epa", "කියන්න එපා", "secret"],
    "authority": ["police", "customs", "cbsl", "court", "පොලිස්", "රේගු", "මහ බැංකු"],
    "guaranteed_returns": ["guaranteed", "double", "daily profit", "ලාභ", "සහතික"],
    "payment_request": ["salli ewanna", "ewanna", "transfer", "deposit", "pay now", "ගෙවන්න", "එවන්න"],
    "channel_switch": ["whatsapp", "telegram", "join group", "join karanna"],
    "credential_request": ["otp", "pin", "password", "cvv"],
}


def rule_signals(text: str) -> dict:
    """Finds common manipulation patterns in message text: urgency, secrecy,
    authority, guaranteed returns, payment request, channel switch and
    requests for OTP/PIN."""
    t = text.lower()
    evidence = {k: [w for w in words if w.lower() in t] for k, words in _SIGNALS.items()}
    evidence = {k: v for k, v in evidence.items() if v}
    return {"signals": list(evidence), "evidence": evidence}
