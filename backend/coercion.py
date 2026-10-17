"""Coercion Shield scoring. Uses phone facts only: whether the caller is a known
contact, how long the call has run, and what kind of code arrived. It never
receives call audio, message text or OTP digits. Pure functions, no I/O."""

CALL_WINDOW_S = 60 * 60                 # call facts count for an hour after the last call event
HISTORY_WINDOW_S = 7 * 24 * 60 * 60     # flagged messages and transfers look back 7 days
HOLD_SCORE = 7
PAUSE_SCORE = 5
PAUSE_MINUTES = 10
COSIGN_MIN_AMOUNT = 10_000              # LKR; smaller actions are never held
FLAGGED_RISK = 70                       # a /check verdict at or above this counts as a scam message

# What each kind of code unlocks, in Sinhala and English.
OTP_UNLOCKS = {
    "bank_transfer": ("මේ කේතය දුන්නොත් ඔබේ ගිණුමෙන් වෙන කෙනෙකුට මුදල් යවන්න පුළුවන්.",
                      "This code lets someone send money out of your account."),
    "new_payee": ("මේ කේතයෙන් ඔබේ ගිණුමට අලුත් ලබන්නෙක් එකතු වෙනවා. ඊට පස්සේ ඒ අයට මුදල් යවන්න පුළුවන්.",
                  "This code adds a new payee to your account, so money can then be sent to them."),
    "card_payment": ("මේ කේතයෙන් ඔබේ card එකෙන් ගෙවීමක් තහවුරු වෙනවා.",
                     "This code approves a payment from your card."),
    "login": ("මේ කේතයෙන් වෙන කෙනෙකුට ඔබේ ගිණුමට ඇතුළු වෙන්න පුළුවන්.",
              "This code lets someone log in to your account."),
    "account_recovery": ("මේ කේතයෙන් ඔබේ WhatsApp වැනි ගිණුමක් වෙන කෙනෙකුගේ phone එකකට ගන්න පුළුවන්.",
                         "This code can move an account such as WhatsApp to someone else's phone."),
    "other": ("මේ කේතය ඔබේ ගිණුමේ වැදගත් දෙයක් තහවුරු කරනවා.",
              "This code confirms something important on your account."),
}
OTP_CLASSES = tuple(OTP_UNLOCKS)
MONEY_CODES = {"bank_transfer", "new_payee", "card_payment"}

NEVER_ASK = (
    "බැංකුව, පොලීසිය, CID හෝ රේගුව කවදාවත් call එකකදී මේ කේතය ඉල්ලන්නේ නැහැ. "
    "කේතය කාටවත් කියන්න එපා. Call එක නවත්වලා ඔබේ card එකේ පිටුපස ඇති අංකයට බැංකුවට කතා කරන්න.",
    "No bank, police, CID or customs officer will ever ask for this code on a call. "
    "Do not share it. End the call and phone your bank on the number on the back of your card.",
)


def new_profile(key: str) -> dict:
    return {"key": key, "in_call": False, "caller_known": False, "call_seconds": 0,
            "otp_during_call": False, "otp_class": None, "last_call_at": None,
            "has_guardian": False, "flagged_at": [], "transfers": [], "pause_until": None}


def apply_event(p: dict, event: str, now: float, *, caller_known: bool = False,
                call_seconds: int | None = None, otp_class: str | None = None,
                risk_score: int | None = None) -> dict:
    """Updates profile `p` in place with one phone event and returns it."""
    if event == "call_started":
        p.update(in_call=True, caller_known=caller_known, call_seconds=0,
                 otp_during_call=False, otp_class=None, last_call_at=now)
    elif event in ("otp_arrived", "call_ended") and p["in_call"]:
        if call_seconds is not None:
            p["call_seconds"] = call_seconds
        if event == "otp_arrived":
            p.update(otp_during_call=True, otp_class=otp_class or "other")
        else:
            p["in_call"] = False
        p["last_call_at"] = now
    elif event == "message_checked" and risk_score is not None and risk_score >= FLAGGED_RISK:
        p["flagged_at"].append(now)
    return p


def _call_recent(p: dict, now: float) -> bool:
    return p["last_call_at"] is not None and now - p["last_call_at"] <= CALL_WINDOW_S


def _rising(p: dict, transfer: dict, now: float) -> bool:
    """True when this is at least the third transfer to the same payee in the
    last 7 days and every amount is larger than the one before."""
    earlier = [t["amount"] for t in p["transfers"]
               if t["payee"] == transfer["payee"] and now - t["at"] <= HISTORY_WINDOW_S]
    amounts = earlier + [transfer["amount"]]
    return len(amounts) >= 3 and all(a < b for a, b in zip(amounts, amounts[1:]))


def signals(p: dict, now: float, transfer: dict | None = None) -> list[tuple[str, int]]:
    """Returns the (signal, points) pairs that apply now. `transfer` is a bank
    transfer being checked at this moment: {"payee": ..., "amount": ...}."""
    out = []
    if _call_recent(p, now):
        if not p["caller_known"]:
            out.append(("unknown_caller", 2))
        if p["call_seconds"] >= 600:
            out.append(("long_call", 2))
        elif p["call_seconds"] >= 300:
            out.append(("long_call", 1))
        if p["otp_during_call"]:
            out.append(("code_during_call", 3))
            if p["otp_class"] in MONEY_CODES:
                out.append(("money_code", 1))
    if any(now - t <= HISTORY_WINDOW_S for t in p["flagged_at"]):
        out.append(("flagged_message", 3))
    if transfer and transfer.get("payee") and _rising(p, transfer, now):
        out.append(("rising_payments", 3))
    return out


def score(sig: list[tuple[str, int]]) -> int:
    return min(10, sum(points for _, points in sig))


def risk_level(s: int) -> str:
    return "high" if s >= HOLD_SCORE else "medium" if s >= PAUSE_SCORE else "low"


def decide(s: int, has_guardian: bool, amount: int, paused: bool) -> str:
    """Bank-side decision for a money action: allow, pause or hold_cosign."""
    if amount < COSIGN_MIN_AMOUNT:
        return "allow"
    if s >= HOLD_SCORE:
        return "hold_cosign" if has_guardian else "pause"
    if s >= PAUSE_SCORE or paused:
        return "pause"
    return "allow"


def explain(p: dict, sig: list[tuple[str, int]]) -> tuple[str, str]:
    names = {n for n, _ in sig}
    if "code_during_call" in names:
        si, en = OTP_UNLOCKS[p["otp_class"]]
        return f"{si} {NEVER_ASK[0]}", f"{en} {NEVER_ASK[1]}"
    if "rising_payments" in names:
        return ("එකම අලුත් කෙනෙකුට යවන මුදල වරින් වර වැඩි වෙනවා. වංචාකාරයෝ මුලින් පොඩි ගානක් ඉල්ලලා "
                "පස්සේ ලොකු ගාන් ඉල්ලනවා. විනාඩි 10ක් නවතිලා ඔබ විශ්වාස කරන කෙනෙක් එක්ක කතා කරන්න.",
                "Payments to the same new payee keep rising. Scammers start small and then ask for more. "
                "Pause for 10 minutes and talk to someone you trust.")
    if "flagged_message" in names:
        return ("ඔබ check කළ message එකේ වංචා ලක්ෂණ තිබුණා. ගෙවන්න කලින් නවතින්න.",
                "A message you checked looked like a scam. Stop before you pay.")
    if "unknown_caller" in names and "long_call" in names:
        return ("ඔබ නොදන්නා අංකයක් සමඟ දිගු call එකක ඉන්නවා. කවුරුහරි මුදල් හෝ කේතයක් ඉල්ලනවා නම් call එක නවත්තන්න.",
                "You have been on a long call with an unknown number. If anyone asks for money or a code, end the call.")
    return "දැනට අවදානම් ලක්ෂණ පෙනෙන්නේ නැහැ.", "No warning signs right now."


def guardian_message(p: dict, now: float) -> str:
    """Short Sinhala note the user can send to their trusted person."""
    if _call_recent(p, now) and p["otp_during_call"]:
        who = "දන්නා" if p["caller_known"] else "නොදන්නා"
        minutes = p["call_seconds"] // 60
        return (f"Muragala: ඔබේ පවුලේ සාමාජිකයා {who} අංකයක් සමඟ විනාඩි {minutes}ක් call එකක ඉන්නවා. "
                "ඒ අතරේ බැංකු කේතයක් ආවා. කරුණාකර දැන්ම ඔවුන්ට call කරලා "
                "'කේතය කියන්න එපා, call එක නවත්තන්න' කියන්න.")
    return ("Muragala: ඔබේ පවුලේ සාමාජිකයාගේ ගෙවීම්වල වංචා අවදානම් ලක්ෂණ පෙනෙනවා. "
            "කරුණාකර දැන්ම ඔවුන්ට call කරලා ගෙවන්න කලින් කතා කරන්න.")
