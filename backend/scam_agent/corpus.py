"""Loads the grounding corpus as plain text for the agent instructions.
ADK treats {name} in instructions as state placeholders, so braces are removed."""
import json
import pathlib

_DATA = pathlib.Path(__file__).resolve().parent.parent / "data"


def _no_braces(s: str) -> str:
    return s.replace("{", "(").replace("}", ")")


def load_advisories_text() -> str:
    items = json.loads((_DATA / "advisories.json").read_text(encoding="utf-8"))
    lines = []
    for a in items:
        lines.append(
            f"[{a['id']}] ({a['source']}, {a['date']}) type={a['scam_type']}: "
            f"{a['summary_en']} Red flags: {'; '.join(a['red_flags'])}. "
            f"Advice: {a['advice_en']}"
        )
    return _no_braces("\n".join(lines))


def advisory_ids() -> set[str]:
    items = json.loads((_DATA / "advisories.json").read_text(encoding="utf-8"))
    return {a["id"] for a in items}


def load_singlish_examples() -> str:
    return _no_braces((_DATA / "singlish_examples.txt").read_text(encoding="utf-8"))
