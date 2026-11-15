"""Replay every dataset end to end and write honest, reproducible results.

Usage (repo root):
    PYTHONPATH=services/api python scripts/run_evaluation.py

Writes data/evaluation/results.json. No network calls: SERV and Reppo are
disabled so the numbers depend only on the deterministic engine.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "api"))
os.environ["SERV_API_KEY"] = ""
os.environ["REPPO_API_KEY"] = ""

from app.data.loader import DatasetCatalog  # noqa: E402
from app.evaluation.clients import ReppoClient, SERVAnalyst  # noqa: E402
from app.replay.simulator import ReplaySession  # noqa: E402


def run_dataset(meta, candles) -> dict:
    session = ReplaySession(
        run_id=f"eval_{meta.id}",
        dataset=meta,
        candles=candles,
        seed=42,
        serv_analyst=SERVAnalyst(api_key=""),
        reppo_client=ReppoClient(api_key=""),
    )
    snap = session.snapshot()
    while snap.status != "FINISHED":
        snap = session.advance(1)

    tracks = {
        key: {
            "label": m.label,
            "netReturnPct": round(m.netReturnPct, 3),
            "maxDrawdownPct": round(m.maxDrawdownPct, 3),
            "trades": m.tradeCount,
            "feesUsd": round(m.totalFeesUsd + m.totalSlippageUsd, 2),
        }
        for key, m in snap.metricsComparison.items()
    }
    events = snap.adaptationEvents
    accepted = [e for e in events if e.status in ("ACCEPTED", "ACTIVE", "ACTIVATED")]
    rejected = [e for e in events if e.status == "REJECTED"]
    actions: dict[str, int] = {}
    for d in session.decisions:
        actions[d.action] = actions.get(d.action, 0) + 1

    adaptive = tracks.get("adaptive", {}).get("netReturnPct")
    fixed = tracks.get("fixed_50_50", {}).get("netReturnPct")
    return {
        "datasetId": meta.id,
        "name": meta.name,
        "scenario": meta.scenarioLabel,
        "synthetic": meta.isSynthetic,
        "candles": len(candles),
        "tracks": tracks,
        "adaptiveMinusFixedPct": None if adaptive is None or fixed is None else round(adaptive - fixed, 3),
        "adaptiveBeatFixed": None if adaptive is None or fixed is None else adaptive > fixed,
        "adaptations": {
            "proposed": len(events),
            "accepted": len(accepted),
            "rejected": len(rejected),
            "statuses": sorted({e.status for e in events}),
            "events": [
                {"index": e.candleIndex, "status": e.status,
                 "deltaPct": round(e.validationResult.pastSegmentDeltaPct, 3) if e.validationResult else None}
                for e in events
            ],
            "rejectionReasons": [e.rejectionReason for e in rejected if e.rejectionReason][:5],
        },
        "decisionMix": actions,
        "curve": {
            k: [round(getattr(pt, f), 2) for pt in snap.equityCurve[:: max(1, len(snap.equityCurve) // 40)]]
            for k, f in (("adaptive", "adaptiveEquity"), ("fixed", "fixedEquity"))
        },
        "finalWeights": snap.activeWeights,
        "finalVersion": snap.configVersion,
    }


def main() -> None:
    catalog = DatasetCatalog()
    results = []
    for meta in catalog.list_metadata():
        _, candles = catalog.get_dataset(meta.id)
        results.append(run_dataset(meta, candles))

    real = [r for r in results if not r["synthetic"] and r["adaptiveBeatFixed"] is not None]
    payload = {
        "generatedAtUtc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "engine": "deterministic replay, next-bar-open fills, 20 bps fee + 15 bps slippage per side",
        "datasetsHash": hashlib.sha256((ROOT / "data" / "datasets.json").read_bytes()).hexdigest()[:16],
        "summary": {
            "datasets": len(results),
            "adaptiveBeatFixedOnReal": sum(1 for r in real if r["adaptiveBeatFixed"]),
            "realDatasets": len(real),
            "adaptiveProfitableOnReal": sum(1 for r in real if r["tracks"]["adaptive"]["netReturnPct"] > 0),
            "cashBeatAdaptive": sum(1 for r in results if r["tracks"]["adaptive"]["netReturnPct"] < 0),
            "adaptationsProposed": sum(r["adaptations"]["proposed"] for r in results),
            "adaptationsRejected": sum(r["adaptations"]["rejected"] for r in results),
        },
        "results": results,
    }
    public = ROOT / "apps" / "web" / "public" / "proof"
    (public / "candles").mkdir(parents=True, exist_ok=True)
    hashes = {}
    for meta in catalog.list_metadata():
        _, candles = catalog.get_dataset(meta.id)
        csv = "index,observedAt,open,high,low,close\n" + "\n".join(
            f"{c.index},{c.observedAt},{c.open!r},{c.high!r},{c.low!r},{c.close!r}" for c in candles
        )
        (public / "candles" / f"{meta.id}.csv").write_bytes(csv.encode())
        hashes[meta.id] = {"sha256": hashlib.sha256(csv.encode()).hexdigest(), "source": meta.source,
                           "sourceUrl": meta.sourceUrl, "synthetic": meta.isSynthetic}
    payload["candleFiles"] = hashes
    for out in (ROOT / "data" / "evaluation" / "results.json", public / "evaluation.json"):
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2))
    for r in results:
        print(r["datasetId"], r["adaptiveMinusFixedPct"], r["adaptations"], r["decisionMix"])


if __name__ == "__main__":
    main()
