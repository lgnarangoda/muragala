"""Muragala API: POST /check runs the ADK pipeline; GET /v1/scam-context-signal/{id} is the bank-facing signal."""
import datetime
import json
import os
import uuid

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from scam_agent.agent import root_agent
from scam_agent.corpus import advisory_ids

APP_NAME = "muragala"
KNOWN_IDS = advisory_ids()
session_service = InMemorySessionService()
runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=session_service)

# Firestore on Cloud Run; a simple in-memory store for local testing.
if os.environ.get("USE_FIRESTORE", "true").lower() == "true":
    from google.cloud import firestore
    _db = firestore.Client()

    def save_check(check_id, data):
        _db.collection("checks").document(check_id).set(data)

    def load_check(check_id):
        doc = _db.collection("checks").document(check_id).get()
        return doc.to_dict() if doc.exists else None
else:
    _mem = {}

    def save_check(check_id, data):
        _mem[check_id] = data

    def load_check(check_id):
        return _mem.get(check_id)


app = FastAPI(title="Muragala API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def _as_dict(value):
    """Agents may return JSON as text, sometimes inside ``` fences."""
    if isinstance(value, dict) or value is None:
        return value
    cleaned = str(value).strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {"raw": str(value)}


@app.get("/healthz")
def healthz():
    return {"ok": True}


@app.post("/check")
async def check(text: str = Form(""), files: list[UploadFile] | None = File(None)):
    parts = []
    if text.strip():
        parts.append(types.Part(text=text))
    for f in files or []:
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

    check_id = str(uuid.uuid4())
    # Only the verdict is stored. The screenshot and message text are never saved.
    save_check(check_id, {
        "created": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "risk_score": result["risk_score"],
        "scam_type": result.get("scam_type", ""),
        "citations": result["citations"],
    })
    await session_service.delete_session(app_name=APP_NAME, user_id=user_id, session_id=session.id)
    return {"check_id": check_id, **result, "analysis": analysis}


@app.get("/v1/scam-context-signal/{check_id}")
def scam_context_signal(check_id: str):
    d = load_check(check_id)
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
