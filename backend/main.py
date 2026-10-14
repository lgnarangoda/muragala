import datetime
import json
import uuid

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.cloud import firestore
from google.genai import types

from scam_agent.agent import root_agent

APP_NAME = "scam_check"
session_service = InMemorySessionService()
runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=session_service)
db = firestore.Client()

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.post("/check")
async def check(text: str = Form(""), files: list[UploadFile] | None = File(None)):
    parts = []
    if text.strip():
        parts.append(types.Part(text=text))
    for f in files or []:
        data = await f.read()
        parts.append(types.Part.from_bytes(data=data, mime_type=f.content_type))
    if not parts:
        return {"error": "Nothing to check"}
    parts.append(types.Part(text="Please check this shared message for scams."))

    user_id = "demo-user"
    session = await session_service.create_session(app_name=APP_NAME, user_id=user_id)
    message = types.Content(role="user", parts=parts)
    async for _event in runner.run_async(user_id=user_id, session_id=session.id, new_message=message):
        pass

    done = await session_service.get_session(app_name=APP_NAME, user_id=user_id, session_id=session.id)
    result = done.state.get("result")
    if isinstance(result, str):
        result = json.loads(result)

    check_id = str(uuid.uuid4())
    db.collection("checks").document(check_id).set({
        "created": datetime.datetime.now(datetime.timezone.utc),
        "risk_score": result["risk_score"],
        "scam_type": result["scam_type"],
        "citations": result.get("citations", []),
    })
    return {"check_id": check_id, **result}


@app.get("/v1/scam-context-signal/{check_id}")
def scam_context_signal(check_id: str):
    doc = db.collection("checks").document(check_id).get()
    if not doc.exists:
        return {"error": "not found"}
    d = doc.to_dict()
    score = d["risk_score"]
    action = "hold_and_call_customer" if score >= 70 else "show_warning" if score >= 40 else "allow"
    return {
        "check_id": check_id,
        "risk_score": score,
        "scam_type": d["scam_type"],
        "advisory_refs": d["citations"],
        "recommended_action": action,
    }
