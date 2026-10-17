"""Document storage: Firestore on Cloud Run (shared by all instances), a dict for
local runs and tests. Set USE_FIRESTORE=false to use the dict."""
import os

if os.environ.get("USE_FIRESTORE", "true").lower() == "true":
    from google.cloud import firestore

    _db = firestore.Client()

    def put(collection: str, doc_id: str, data: dict) -> None:
        _db.collection(collection).document(doc_id).set(data)

    def get(collection: str, doc_id: str) -> dict | None:
        doc = _db.collection(collection).document(doc_id).get()
        return doc.to_dict() if doc.exists else None
else:
    _mem: dict = {}

    def put(collection: str, doc_id: str, data: dict) -> None:
        _mem[(collection, doc_id)] = dict(data)

    def get(collection: str, doc_id: str) -> dict | None:
        data = _mem.get((collection, doc_id))
        return dict(data) if data else None
