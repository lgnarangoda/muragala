"""POST /check form handling. No Gemini call: every case stops before the agent runs.
Run from backend/: python tests/test_check_form.py   (pytest also works)"""
import os
import pathlib
import sys

os.environ["USE_FIRESTORE"] = "false"
os.environ.setdefault("MODEL_ID", "test-model")
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)


def test_empty_files_field_from_swagger_is_ignored():
    # Swagger UI on /docs always sends "files=" as a text part, even with no file chosen.
    r = client.post("/check", files=[("text", (None, "")), ("files", (None, ""))])
    assert r.status_code == 400, r.text
    assert r.json()["detail"] == "Nothing to check"


def test_swagger_example_string_in_files_is_ignored():
    r = client.post("/check", files=[("text", (None, "")), ("files", (None, "6tU6i0a$B"))])
    assert r.status_code == 400, r.text


def test_empty_uploaded_file_is_ignored():
    r = client.post("/check", files=[("text", (None, "")), ("files", ("a.png", b"", "image/png"))])
    assert r.status_code == 400, r.text


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
