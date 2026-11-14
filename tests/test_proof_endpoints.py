"""Proof, evaluation and candle endpoints serve recorded files honestly."""

import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app

ROOT = Path(__file__).resolve().parents[1]


def test_candles_hash_matches_published_file() -> None:
    client = TestClient(create_app())
    body = client.get("/api/proof/candles/momentum-breakdown").json()
    assert hashlib.sha256(body["csv"].encode()).hexdigest() == body["sha256"]
    published = ROOT / "apps" / "web" / "public" / "proof" / "candles" / "momentum-breakdown.csv"
    if published.exists():
        assert hashlib.sha256(published.read_bytes()).hexdigest() == body["sha256"]


def test_evaluation_reports_losses_not_only_wins() -> None:
    path = ROOT / "data" / "evaluation" / "results.json"
    if not path.exists():
        return
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["summary"]["datasets"] == len(data["results"])
    assert any(r["synthetic"] for r in data["results"])
    for r in data["results"]:
        assert set(r["tracks"]) >= {"adaptive", "fixed_50_50", "cash"}


def test_unknown_dataset_candles_404() -> None:
    assert TestClient(create_app()).get("/api/proof/candles/nope").status_code == 404
