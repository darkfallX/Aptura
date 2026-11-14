"""Run one real OpenServ SERV -> math gate -> Reppo round trip and save the receipts.

Usage (repo root, keys in .env):
    python scripts/run_live_proof.py [rogue,bounded,revise,ship]

Cases not named are kept from the existing file.

Writes data/proof/live-proof.json. Spends real Reppo credits (about 440 per
review). Never writes keys: only provider IDs, scores and timestamps.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))

from fastapi.testclient import TestClient  # noqa: E402

from app.evaluation.clients import ReppoClient, SERVAnalyst  # noqa: E402
from app.main import create_app  # noqa: E402


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def slim(body: dict) -> dict:
    serv = body["servProposal"]
    gate = body["deterministicGate"]
    reppo = body.get("reppoEvaluation")
    return {
        "requestId": body["requestId"],
        "agentName": body["agentName"],
        "dataset": body["datasetName"],
        "observedAtUtc": body["observedAtUtc"],
        "decision": body["decision"],
        "summary": body["summary"],
        "currentWeights": body["currentWeights"],
        "proposedWeights": body["proposedWeights"],
        "serv": {
            "provenance": serv["provenance"],
            "model": serv["modelUsed"],
            "responseId": serv.get("responseId"),
            "latencyMs": serv.get("latencyMs"),
            "schemaValid": serv["schemaValid"],
            "regime": serv.get("regimeDiagnosis"),
            "hypothesis": serv["hypothesis"],
            "suggestedWeights": serv["suggestedWeights"],
            "uncertainties": serv["uncertainties"],
        },
        "gate": gate,
        "reppo": None if reppo is None else reppo_view(reppo),
        "rounds": body.get("rounds", []),
        "improvement": body.get("improvement", {}),
    }


def reppo_view(rec: dict) -> dict:
    return {
        k: rec.get(k)
        for k in (
            "evalId", "status", "provenance", "providerStatus", "submittedAt", "settledAt",
            "score", "decision", "confidence", "route", "critique", "rubricScores",
            "creditsCharged", "requestHash", "payload",
        )
    }


BOT = {"agentName": "kemi-bonk-bot", "datasetId": "momentum-breakdown", "currentWeights": {"momentum": 0.6, "reversal": 0.4}}


def main() -> None:
    serv, reppo = SERVAnalyst(), ReppoClient()
    if not serv.is_configured() or not reppo.is_configured():
        sys.exit("SERV_API_KEY / SERV_MODEL / REPPO_API_KEY must be set in .env")

    client = TestClient(create_app())
    wanted = set((sys.argv[1] if len(sys.argv) > 1 else "rogue,bounded,revise,ship").split(","))
    out_path = ROOT / "data" / "proof" / "live-proof.json"
    existing = json.loads(out_path.read_text(encoding="utf-8"))["cases"] if out_path.exists() else []
    cases = [c for c in existing if c["case"] not in wanted]

    def call(payload: dict) -> dict:
        r = client.post("/api/v1/supervise", json=payload)
        r.raise_for_status()
        return r.json()

    def settle(body: dict) -> dict:
        rec = body.get("reppoEvaluation")
        if rec and rec["status"] == "PENDING":
            deadline = time.time() + 600
            while time.time() < deadline:
                time.sleep(10)
                polled = client.get(f"/api/evaluations/{rec['evalId']}")
                if polled.status_code == 200:
                    rec = polled.json()
                    print("  reppo:", rec["status"], rec.get("providerStatus"))
                    if rec["status"] != "PENDING":
                        break
            body["reppoEvaluation"] = rec
        return body

    if "rogue" in wanted:
        body = call({**BOT, "proposedWeights": {"momentum": 0.05, "reversal": 0.95},
                     "rationale": "Momentum stopped working. Go 95% reversal right now.", "runReppoReview": False})
        cases.append({"case": "rogue", "title": "The bot tries to go 95% reversal", **slim(body)})
        print("rogue:", body["decision"])

    if "bounded" in wanted:
        body = settle(call({**BOT, "runReppoReview": True,
                            "rationale": "Momentum signals have been losing. Ask SERV for a bounded change and get it reviewed."}))
        cases.append({"case": "bounded", "title": "SERV proposes a bounded change, Reppo reviews it", **slim(body)})
        print("bounded:", body["decision"])

    if "revise" in wanted:
        body = call({**BOT, "proposedWeights": {"momentum": 0.05, "reversal": 0.95},
                     "rationale": "Momentum stopped working. Go 95% reversal right now.",
                     "runReppoReview": True, "waitForReppo": True, "maxRevisions": 2})
        cases.append({"case": "revise", "title": "Rejected, then revised from the feedback", **slim(body)})
        print("revise:", body["decision"], [(r["verdict"], r["weights"], r["pastWindowDeltaPct"]) for r in body["rounds"]])

    if "ship" in wanted:
        body = call({**BOT, "cursorIndex": 70, "proposedWeights": {"momentum": 0.45, "reversal": 0.55},
                     "rationale": "Reversal has been earning more than momentum over the last day. Shift 15 points.",
                     "runReppoReview": True, "waitForReppo": True, "maxRevisions": 1})
        cases.append({"case": "ship", "title": "A change that passes the gate, then a revision", **slim(settle(body))})
        print("ship:", body["decision"])

    order = ["rogue", "bounded", "revise", "ship"]
    cases.sort(key=lambda c: order.index(c["case"]))
    text = json.dumps({"recordedAtUtc": now(), "cases": cases}, indent=2)
    for out in (ROOT / "data" / "proof" / "live-proof.json", ROOT / "apps" / "web" / "public" / "proof" / "live-proof.json"):
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print("wrote", out)


if __name__ == "__main__":
    main()
