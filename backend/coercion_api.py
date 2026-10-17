"""Coercion Shield API. The phone sends facts about a call (never audio or OTP
digits) and gets a coercion score; a bank or ATM asks before releasing money
and can be told to hold it until the user's trusted person co-signs."""
import datetime
import time
import uuid
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

import coercion
import store

router = APIRouter(prefix="/v1", tags=["Coercion Shield"])
clock = time.time  # tests replace this to control time

PROFILE_TTL_S = 7 * 24 * 60 * 60
COSIGN_TTL_S = 15 * 60


class SessionEvent(BaseModel):
    # Unknown fields are rejected, so OTP digits or message text can never be stored.
    model_config = ConfigDict(extra="forbid")
    device_token: str = Field(min_length=1, max_length=64, description="Pseudonymous phone token")
    customer_token: str | None = Field(None, max_length=64, description="Pseudonymous bank customer token; defaults to device_token")
    event: Literal["call_started", "otp_arrived", "call_ended", "message_checked"]
    caller_known: bool = Field(False, description="Caller is in the phone's contacts")
    has_guardian: bool | None = Field(None, description="User has set up a trusted person")
    call_seconds: int | None = Field(None, ge=0)
    otp_class: Literal[coercion.OTP_CLASSES] | None = Field(None, description="Kind of code that arrived; never the digits")
    check_id: str | None = Field(None, description="For message_checked: the check_id returned by POST /check")


class CosignCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")
    customer_token: str = Field(min_length=1, max_length=64)
    action: Literal["atm_withdrawal", "transfer"]
    amount: int = Field(ge=0, description="LKR")
    payee_token: str | None = Field(None, max_length=64, description="Pseudonymous payee, for transfers")


class CosignDecision(BaseModel):
    decision: Literal["approve", "deny"]


def _ts(seconds: float) -> datetime.datetime:
    return datetime.datetime.fromtimestamp(seconds, datetime.timezone.utc)


def _load_profile(key: str, now: float) -> dict:
    p = store.get("coercion_profiles", key)
    if not p or p["expires_at"] < _ts(now):  # Firestore TTL deletes expired docs within a day
        return coercion.new_profile(key)
    return p


def _save_profile(p: dict, now: float) -> None:
    window = coercion.HISTORY_WINDOW_S
    p["flagged_at"] = [t for t in p["flagged_at"] if now - t <= window]
    p["transfers"] = [t for t in p["transfers"] if now - t["at"] <= window]
    p["expires_at"] = _ts(now + PROFILE_TTL_S)
    store.put("coercion_profiles", p["key"], p)


def _assess(p: dict, now: float, transfer: dict | None = None) -> dict:
    sig = coercion.signals(p, now, transfer)
    s = coercion.score(sig)
    level = coercion.risk_level(s)
    si, en = coercion.explain(p, sig)
    alert = level == "high" and p["has_guardian"]
    return {
        "score": s,
        "risk_level": level,
        "signals": [name for name, _ in sig],
        "explanation_si": si,
        "explanation_en": en,
        "guardian_alert": alert,
        "guardian_message_si": coercion.guardian_message(p, now) if alert else None,
    }


@router.post("/sessions/events")
def session_event(e: SessionEvent):
    """Records one phone event and returns the current coercion score (0-10)."""
    now = clock()
    p = _load_profile(e.customer_token or e.device_token, now)
    if e.has_guardian is not None:
        p["has_guardian"] = e.has_guardian
    risk = None
    if e.event == "message_checked":
        check = store.get("checks", e.check_id) if e.check_id else None
        if not check:
            raise HTTPException(status_code=404, detail="check_id not found")
        risk = check["risk_score"]
    coercion.apply_event(p, e.event, now, caller_known=e.caller_known,
                         call_seconds=e.call_seconds, otp_class=e.otp_class, risk_score=risk)
    _save_profile(p, now)
    return {"device_token": e.device_token, "event": e.event, **_assess(p, now)}


@router.post("/cosign/check")
def cosign_check(c: CosignCheck):
    """Asked by the bank or ATM before money leaves. Returns allow, pause
    (10-minute cooling-off) or hold_cosign (wait for the trusted person)."""
    now = clock()
    p = _load_profile(c.customer_token, now)
    transfer = {"payee": c.payee_token, "amount": c.amount, "at": now} if c.action == "transfer" else None
    a = _assess(p, now, transfer)
    paused = bool(p["pause_until"] and now < p["pause_until"])
    decision = coercion.decide(a["score"], p["has_guardian"], c.amount, paused)
    out = {"decision": decision, "action": c.action, "amount": c.amount, **a}
    if decision == "pause":
        if not paused:
            p["pause_until"] = now + coercion.PAUSE_MINUTES * 60
        out["pause_until"] = _ts(p["pause_until"]).isoformat()
    elif decision == "hold_cosign":
        cosign_id = str(uuid.uuid4())
        store.put("cosign_requests", cosign_id, {
            "customer_token": c.customer_token, "action": c.action, "amount": c.amount,
            "status": "pending", "created_at": _ts(now), "expires_at": _ts(now + COSIGN_TTL_S),
        })
        out["cosign_id"] = cosign_id
        out["expires_at"] = _ts(now + COSIGN_TTL_S).isoformat()
    if transfer and c.payee_token:
        p["transfers"].append(transfer)
    _save_profile(p, now)
    return out


def _load_cosign(cosign_id: str, now: float) -> dict:
    req = store.get("cosign_requests", cosign_id)
    if not req:
        raise HTTPException(status_code=404, detail="cosign request not found")
    if req["status"] == "pending" and req["expires_at"] < _ts(now):
        req["status"] = "expired"
    return req


@router.get("/cosign/{cosign_id}")
def cosign_status(cosign_id: str):
    """Polled by the ATM or bank while the money is on hold."""
    req = _load_cosign(cosign_id, clock())
    return {"cosign_id": cosign_id, "status": req["status"], "action": req["action"], "amount": req["amount"]}


@router.post("/cosign/{cosign_id}/decision")
def cosign_decide(cosign_id: str, d: CosignDecision):
    """The trusted person approves or denies the held action."""
    now = clock()
    req = _load_cosign(cosign_id, now)
    if req["status"] == "expired":
        raise HTTPException(status_code=410, detail="cosign request expired")
    if req["status"] != "pending":
        raise HTTPException(status_code=409, detail=f"already {req['status']}")
    req["status"] = "approved" if d.decision == "approve" else "denied"
    req["decided_at"] = _ts(now)
    store.put("cosign_requests", cosign_id, req)
    return {"cosign_id": cosign_id, "status": req["status"], "action": req["action"], "amount": req["amount"]}
