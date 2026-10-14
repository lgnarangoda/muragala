import json
import pathlib

_DATA = pathlib.Path(__file__).resolve().parent.parent / "data"


def load_advisories_text() -> str:
    items = json.loads((_DATA / "advisories.json").read_text(encoding="utf-8"))
    lines = []
    for a in items:
        lines.append(
            f"[{a['id']}] ({a['source']}, {a['date']}) type={a['scam_type']}: "
            f"{a['summary_en']} Red flags: {'; '.join(a['red_flags'])}. "
            f"Advice: {a['advice_en']}"
        )
    return "\n".join(lines)
