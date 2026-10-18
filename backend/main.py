"""Muragala API: POST /check runs the ADK pipeline; GET /v1/scam-context-signal/{id} is the bank-facing signal."""
import datetime
import json
import unicodedata
import uuid

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

import store
from coercion_api import router as coercion_router
from scam_agent.agent import root_agent
from scam_agent.corpus import advisory_ids

APP_NAME = "muragala"
KNOWN_IDS = advisory_ids()
CHECK_TTL = datetime.timedelta(days=30)  # Firestore TTL deletes verdicts after this
session_service = InMemorySessionService()
runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=session_service)

app = FastAPI(title="Muragala API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(coercion_router)


def _only_script(texts, first, last):
    """True when every letter is ASCII or in the [first, last] Unicode block."""
    return all(c.isascii() or first <= c <= last
               for t in texts for c in t if unicodedata.category(c).startswith("L"))


def _as_dict(value):
    """Agents may return JSON as text, sometimes inside ``` fences."""
    if isinstance(value, dict) or value is None:
        return value
    cleaned = str(value).strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"raw": str(value)}


@app.get("/health")  # not /healthz: Cloud Run reserves that path
def health():
    return {"ok": True}


@app.post("/check")
async def check(text: str = Form(""), files: list[UploadFile | str] | None = File(None)):
    parts = []
    if text.strip():
        parts.append(types.Part(text=text))
    # Swagger UI on /docs sends "files" as a text part even with no file chosen; skip it.
    for f in [f for f in files or [] if not isinstance(f, str)]:
        data = await f.read()
        if data:
            parts.append(types.Part.from_bytes(data=data, mime_type=f.content_type or "application/octet-stream"))
    if not parts:
        raise HTTPException(status_code=400, detail="Nothing to check")
    parts.append(types.Part(text="Please check this shared message for scams."))

    user_id = "anonymous"
    session = await session_service.create_session(app_name=APP_NAME, user_id=user_id)
    message = types.Content(role="user", parts=parts)
    async for _event in runner.run_async(user_id=user_id, session_id=session.id, new_message=message):
        pass

    done = await session_service.get_session(app_name=APP_NAME, user_id=user_id, session_id=session.id)
    result = _as_dict(done.state.get("result"))
    analysis = _as_dict(done.state.get("analysis"))
    if not result or "risk_score" not in result:
        raise HTTPException(status_code=502, detail="Agent did not return a result")

    # Hallucination guard: keep only advisory IDs that exist in the corpus.
    result["citations"] = [c for c in result.get("citations", []) if c in KNOWN_IDS]
    # Gemini sometimes drops a word from another script into the Tamil; the app then shows English.
    if not _only_script([result.get("explanation_ta", ""), *result.get("actions_ta", [])], "஀", "௿"):
        result["explanation_ta"], result["actions_ta"] = None, None

    check_id = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc)
    # Only the verdict is stored. The screenshot and message text are never saved.
    store.put("checks", check_id, {
        "created": now.isoformat(),
        "expires_at": now + CHECK_TTL,
        "risk_score": result["risk_score"],
        "scam_type": result.get("scam_type", ""),
        "citations": result["citations"],
    })
    await session_service.delete_session(app_name=APP_NAME, user_id=user_id, session_id=session.id)
    return {"check_id": check_id, **result, "analysis": analysis}


@app.get("/v1/scam-context-signal/{check_id}")
def scam_context_signal(check_id: str):
    d = store.get("checks", check_id)
    if not d:
        raise HTTPException(status_code=404, detail="not found")
    score = d["risk_score"]
    action = "hold_and_call_customer" if score >= 70 else "show_warning" if score >= 40 else "allow"
    return {
        "check_id": check_id,
        "risk_score": score,
        "scam_type": d["scam_type"],
        "advisory_refs": d["citations"],
        "recommended_action": action,
    }
