"""Coercion Shield scenarios, run against the API with an in-memory store.
Run from backend/: python tests/test_coercion.py   (pytest also works)"""
import os
import pathlib
import sys

os.environ["USE_FIRESTORE"] = "false"
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import coercion_api  # noqa: E402
import store  # noqa: E402

app = FastAPI()
app.include_router(coercion_api.router)
client = TestClient(app)

T0 = 1_800_000_000.0
_now = [T0]
coercion_api.clock = lambda: _now[0]


def at(minutes: float) -> None:
    _now[0] = T0 + minutes * 60


def event(token, name, **kw):
    r = client.post("/v1/sessions/events", json={"device_token": token, "event": name, **kw})
    assert r.status_code == 200, r.text
    return r.json()


def cosign(token, action, amount, **kw):
    r = client.post("/v1/cosign/check", json={"customer_token": token, "action": action, "amount": amount, **kw})
    assert r.status_code == 200, r.text
    return r.json()


def fake_cid_call(token, has_guardian=True):
    """Story 1: an unknown 'CID officer' keeps the user on the line for 12
    minutes and a bank transfer code arrives during the call."""
    at(0)
    event(token, "call_started", has_guardian=has_guardian)
    at(12)
    return event(token, "otp_arrived", call_seconds=720, otp_class="bank_transfer")


def test_story1_code_during_long_unknown_call_scores_8():
    r = fake_cid_call("t1")
    assert r["score"] == 8 and r["risk_level"] == "high"
    assert r["signals"] == ["unknown_caller", "long_call", "code_during_call", "money_code"]
    assert "මුදල් යවන්න" in r["explanation_si"]  # explains what the code unlocks
    assert r["guardian_alert"] and "විනාඩි 12" in r["guardian_message_si"]


def test_story1_atm_is_held_and_guardian_denies():
    fake_cid_call("t2")
    at(20)
    r = cosign("t2", "atm_withdrawal", 200_000)
    assert r["decision"] == "hold_cosign" and r["score"] == 8
    cid = r["cosign_id"]
    assert client.get(f"/v1/cosign/{cid}").json()["status"] == "pending"
    d = client.post(f"/v1/cosign/{cid}/decision", json={"decision": "deny"})
    assert d.status_code == 200 and d.json()["status"] == "denied"
    again = client.post(f"/v1/cosign/{cid}/decision", json={"decision": "approve"})
    assert again.status_code == 409  # a decision cannot be changed


def test_guardian_can_approve():
    fake_cid_call("t3")
    cid = cosign("t3", "atm_withdrawal", 50_000)["cosign_id"]
    assert client.post(f"/v1/cosign/{cid}/decision", json={"decision": "approve"}).json()["status"] == "approved"


def test_short_call_with_known_contact_is_allowed():
    at(0)
    event("t4", "call_started", caller_known=True, has_guardian=True)
    at(2)
    r = event("t4", "call_ended", call_seconds=120)
    assert r["score"] == 0 and not r["guardian_alert"]
    assert cosign("t4", "atm_withdrawal", 200_000)["decision"] == "allow"


def test_without_guardian_high_risk_pauses_instead_of_hold():
    r = fake_cid_call("t5", has_guardian=False)
    assert r["score"] == 8 and not r["guardian_alert"]
    c = cosign("t5", "atm_withdrawal", 200_000)
    assert c["decision"] == "pause" and "pause_until" in c and "cosign_id" not in c


def test_small_amount_is_never_held():
    fake_cid_call("t6")
    assert cosign("t6", "atm_withdrawal", 5_000)["decision"] == "allow"


def test_story2_rising_transfers_and_flagged_screenshot_pause_third_transfer():
    store.put("checks", "chk-task-job", {"risk_score": 92, "scam_type": "job_task", "citations": []})
    at(0)
    r = event("t7", "message_checked", check_id="chk-task-job")
    assert r["signals"] == ["flagged_message"] and r["score"] == 3
    at(60)
    assert cosign("t7", "transfer", 12_000, payee_token="p-task")["decision"] == "allow"
    at(60 * 24)
    assert cosign("t7", "transfer", 25_000, payee_token="p-task")["decision"] == "allow"
    at(60 * 48)
    third = cosign("t7", "transfer", 60_000, payee_token="p-task")
    assert third["decision"] == "pause" and third["score"] == 6
    assert "rising_payments" in third["signals"] and "flagged_message" in third["signals"]


def test_call_facts_expire_after_an_hour():
    fake_cid_call("t8")
    at(12 + 61)
    assert cosign("t8", "atm_withdrawal", 200_000)["score"] == 0


def test_otp_digits_and_message_text_are_rejected_not_stored():
    at(0)
    r = client.post("/v1/sessions/events", json={"device_token": "t9", "event": "otp_arrived",
                                                 "otp_class": "bank_transfer", "otp": "482913"})
    assert r.status_code == 422
    event("t9", "call_started")
    saved = store.get("coercion_profiles", "t9")
    assert "482913" not in str(saved) and "otp" not in saved


def test_cosign_request_expires_after_15_minutes():
    fake_cid_call("t10")
    at(20)
    cid = cosign("t10", "atm_withdrawal", 200_000)["cosign_id"]
    at(20 + 16)
    assert client.get(f"/v1/cosign/{cid}").json()["status"] == "expired"
    assert client.post(f"/v1/cosign/{cid}/decision", json={"decision": "approve"}).status_code == 410


if __name__ == "__main__":
    tests = [f for name, f in sorted(globals().items()) if name.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"FAIL {t.__name__}: {type(e).__name__} {e}")
    print(f"{len(tests) - failed} passed" + (f", {failed} failed" if failed else ""))
    sys.exit(1 if failed else 0)
