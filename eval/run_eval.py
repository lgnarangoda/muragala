"""Runs eval_set.csv against the API and prints precision/recall per language.
Usage: python eval/run_eval.py http://localhost:8080   (or the Cloud Run URL)"""
import csv
import pathlib
import sys
import time
from collections import defaultdict

import requests

API = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080").rstrip("/")
HERE = pathlib.Path(__file__).resolve().parent
THRESHOLD = 50  # recall-first: risk_score >= 50 counts as "scam"


def scores(rows):
    tp = sum(1 for r in rows if r["label"] == "scam" and r["pred"] == "scam")
    fp = sum(1 for r in rows if r["label"] != "scam" and r["pred"] == "scam")
    fn = sum(1 for r in rows if r["label"] == "scam" and r["pred"] != "scam")
    p = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * p * rec / (p + rec) if p + rec else 0.0
    return p, rec, f1, len(rows)


rows = list(csv.DictReader(open(HERE / "eval_set.csv", encoding="utf-8")))
out = []
for r in rows:
    files = []
    if r.get("image_path"):
        files = [("files", open(HERE / r["image_path"], "rb"))]
    t0 = time.time()
    try:
        resp = requests.post(f"{API}/check", data={"text": r["text"]}, files=files, timeout=180).json()
    except Exception as e:
        resp = {"error": str(e)}
    latency = time.time() - t0
    score = resp.get("risk_score", -1)
    # A failed request is an error, not a "legit" prediction; it is left out of the metrics.
    pred = "error" if score < 0 else "scam" if score >= THRESHOLD else "legit"
    out.append({**r, "pred": pred, "risk_score": score, "pred_type": resp.get("scam_type", ""),
                "type_ok": resp.get("scam_type", "") == r["scam_type"], "latency_s": round(latency, 1),
                "citations": ";".join(resp.get("citations", []))})
    print(f'{r["id"]:>3} {r["language"]:<9} label={r["label"]:<5} pred={pred:<5} score={score:>3} '
          f'type={resp.get("scam_type", "?")} ({latency:.1f}s)')

errors = [o for o in out if o["pred"] == "error"]
if errors:
    print(f"\n{len(errors)} of {len(out)} requests failed and are excluded: ids {[o['id'] for o in errors]}")
out_all, out = out, [o for o in out if o["pred"] != "error"]

print("\n=== Overall ===")
p, rec, f1, n = scores(out)
print(f"precision={p:.2f} recall={rec:.2f} f1={f1:.2f} n={n}")
scam_rows = [o for o in out if o["label"] == "scam"]
if scam_rows:
    print(f"scam type accuracy={sum(o['type_ok'] for o in scam_rows) / len(scam_rows):.2f}")
lat = sorted(o["latency_s"] for o in out)
print(f"latency p50={lat[len(lat) // 2]}s p95={lat[max(0, int(len(lat) * 0.95) - 1)]}s")

print("\n=== By language ===")
by_lang = defaultdict(list)
for o in out:
    by_lang[o["language"]].append(o)
for lang, items in sorted(by_lang.items()):
    p, rec, f1, n = scores(items)
    print(f"{lang:<9} precision={p:.2f} recall={rec:.2f} f1={f1:.2f} n={n}")

with open(HERE / "results.csv", "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(out_all[0].keys()))
    w.writeheader()
    w.writerows(out_all)
print("\nSaved eval/results.csv")
