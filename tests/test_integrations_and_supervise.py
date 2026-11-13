"""Tests for updated SERV/Reppo live contracts, Supervisor-as-a-Service, and opt-in live smoke tests."""

from __future__ import annotations

import json
import os
from pathlib import Path
import time
import httpx
import pytest
from fastapi.testclient import TestClient

from app.data.loader import DatasetCatalog
from app.evaluation.clients import ReppoClient, SERVAnalyst
from app.main import create_app
from app.replay.simulator import ReplaySession
from app.storage.repository import SQLiteRepository


def test_serv_omits_unsupported_temperature_and_repairs_invalid_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []

    class FakeResponse:
        def __init__(self, status_code: int, payload: dict) -> None:
            self.status_code = status_code
            self._payload = payload

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise httpx.HTTPStatusError("err", request=None, response=self)

        def json(self) -> dict:
            return self._payload

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            pass

        def post(self, url: str, headers: dict, json: dict) -> FakeResponse:
            calls.append(json)
            if len(calls) == 1:
                # First call mimics wrong field names
                return FakeResponse(200, {
                    "id": "chatcmpl-1",
                    "model": "gpt-5.6-sol",
                    "choices": [{"message": {"content": '{"hypothesis":"x","evidenceReferences":["ev_1"],"weights":{"momentum":0.4,"reversal":0.6}}'}}],
                })
            return FakeResponse(200, {
                "id": "chatcmpl-2",
                "model": "gpt-5.6-sol",
                "choices": [{"message": {"content": json_dump_valid()}}],
            })

    def json_dump_valid() -> str:
        return json.dumps({
            "hypothesis": "Reversal outperformed momentum on matured outcomes.",
            "evidenceIds": ["ev_1"],
            "suggestedWeights": {"momentum": 0.4, "reversal": 0.6},
            "regimeDiagnosis": "MEAN_REVERTING",
            "buyThresholdDelta": 0.02,
            "assumptions": ["Closed candles only."],
            "uncertainties": ["Regime may revert."],
        })

    monkeypatch.setattr(httpx, "Client", FakeClient)
    analyst = SERVAnalyst(api_key="test-key", model="gpt-5.6-sol")
    proposal = analyst.generate_proposal(
        observed_at="2026-11-11T12:00:00Z",
        dataset_name="BONK / SOL",
        old_weights=[0.6, 0.4],
        candidate_weights=[0.45, 0.55],
        momentum_score=-0.9,
        reversal_score=0.7,
        matured_count=14,
        allowed_evidence_ids=["ev_1", "ev_2"],
    )
    assert len(calls) == 2
    assert "temperature" not in calls[0]
    assert calls[0]["response_format"]["type"] == "json_schema"
    assert proposal.provenance == "SERV_GENERATED"
    assert proposal.schemaValid is True
    assert proposal.regimeDiagnosis == "MEAN_REVERTING"
    assert proposal.buyThresholdDelta == 0.02
    assert proposal.responseId == "chatcmpl-2"


def test_reppo_client_matches_evals_v1_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    posted: list[dict] = []

    class FakeResponse:
        def __init__(self, status_code: int, payload: dict) -> None:
            self.status_code = status_code
            self._payload = payload

        def raise_for_status(self) -> None:
            if self.status_code >= 400:
                raise httpx.HTTPStatusError("err", request=None, response=self)

        def json(self) -> dict:
            return self._payload

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args) -> None:
            pass

        def post(self, url: str, headers: dict, json: dict) -> FakeResponse:
            assert url.endswith("/api/v1/agents/evals")
            assert json["taskType"] == "action"
            posted.append(json)
            return FakeResponse(201, {
                "id": "eval_live_123",
                "taskType": "action",
                "status": "QUEUED",
                "createdAt": "2026-11-13T00:00:00Z",
            })

        def get(self, url: str, headers: dict) -> FakeResponse:
            assert url.endswith("/api/v1/agents/evals/eval_live_123")
            return FakeResponse(200, {
                "id": "eval_live_123",
                "status": "COMPLETED",
                "score": 88,
                "route": "ship",
                "creditsCharged": 440,
                "completedAt": "2026-11-13T00:01:05Z",
                "result": {
                    "score": 88,
                    "decision": "accept",
                    "confidence": "high",
                    "route": "ship",
                    "reason": "Evidence IDs predate proposal time and bounds are respected.",
                    "rubric_scores": {"causality": 92, "bounds": 90, "uncertainty": 82},
                    "explain": {"route_reasons": ["High evaluator consensus"]},
                },
            })

    monkeypatch.setattr(httpx, "Client", FakeClient)
    meta, candles = DatasetCatalog().get_dataset("momentum-breakdown")
    sess = ReplaySession("reppo-v1", meta, candles)
    sess.advance(50)
    ev = sess.adaptation_events[0]

    client = ReppoClient(api_key="test-reppo-key")
    rec = client.submit_evaluation(ev, meta.name)
    assert len(posted) == 1
    assert rec.evalId == "eval_live_123"
    assert rec.status == "PENDING"
    assert rec.providerStatus == "QUEUED"
    assert rec.provenance == "REPPO_LIVE"

    settled = client.poll_evaluation(rec)
    assert settled.status == "SETTLED"
    assert settled.providerStatus == "COMPLETED"
    assert settled.score == 88.0
    assert settled.decision == "accept"
    assert settled.route == "ship"
    assert settled.creditsCharged == 440
    assert settled.rubricScores == {"causality": 92.0, "bounds": 90.0, "uncertainty": 82.0}
    assert "Evidence IDs predate proposal time" in (settled.critique or "")


def test_agent_manifest_and_supervise_endpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = SQLiteRepository(tmp_path / "sup.db")

    class MockSERV(SERVAnalyst):
        def is_configured(self) -> bool:
            return True

        def generate_proposal(self, observed_at, dataset_name, old_weights, candidate_weights, momentum_score, reversal_score, matured_count, allowed_evidence_ids, extra_context=None):
            return SERVAnalyst._build_deterministic_proposal(
                observed_at, dataset_name, old_weights, candidate_weights,
                momentum_score, reversal_score, matured_count, allowed_evidence_ids, "mock",
            ).model_copy(update={"provenance": "SERV_GENERATED", "modelUsed": "gpt-5.6-sol", "latencyMs": 120})

    app = create_app(repo=repo, serv_analyst=MockSERV(api_key="mock"), reppo_client=ReppoClient(api_key=""))
    client = TestClient(app)

    manifest = client.get("/api/agent/manifest")
    assert manifest.status_code == 200
    assert manifest.json()["capabilities"][0]["endpoint"] == "/api/v1/supervise"

    # Invalid caller weights exceeding bounds must be BLOCKED regardless of SERV
    blocked = client.post("/api/v1/supervise", json={
        "agentName": "rogue-bot",
        "datasetId": "momentum-breakdown",
        "currentWeights": {"momentum": 0.6, "reversal": 0.4},
        "proposedWeights": {"momentum": 0.05, "reversal": 0.95},
        "runReppoReview": False,
    })
    assert blocked.status_code == 200
    assert blocked.json()["decision"] == "BLOCK"
    assert blocked.json()["deterministicGate"]["passed"] is False

    # Valid SERV-synthesized weights on momentum-breakdown should pass or return REVIEW/SHIP cleanly
    valid = client.post("/api/v1/supervise", json={
        "agentName": "alpha-scout",
        "datasetId": "momentum-breakdown",
        "currentWeights": {"momentum": 0.6, "reversal": 0.4},
        "runReppoReview": False,
    })
    assert valid.status_code == 200
    body = valid.json()
    assert body["servProposal"]["provenance"] == "SERV_GENERATED"
    assert body["decision"] in ("SHIP", "BLOCK")


@pytest.mark.live
def test_live_serv_and_reppo_round_trip() -> None:
    """Opt-in live integration smoke test: `pytest -m live`."""
    serv = SERVAnalyst()
    reppo = ReppoClient()
    if not serv.is_configured() or not reppo.is_configured():
        pytest.skip("SERV or Reppo credentials not configured")

    meta, candles = DatasetCatalog().get_dataset("momentum-breakdown")
    sess = ReplaySession("live-smoke", meta, candles, serv_analyst=SERVAnalyst(api_key=""))
    sess.advance(50)
    ev = sess.adaptation_events[0]

    proposal = serv.generate_proposal(
        observed_at=ev.detectedAt,
        dataset_name=meta.name,
        old_weights=ev.oldWeights,
        candidate_weights=ev.proposedWeights or ev.oldWeights,
        momentum_score=ev.momentumTrailingScore,
        reversal_score=ev.reversalTrailingScore,
        matured_count=ev.maturedSampleCount,
        allowed_evidence_ids=ev.evidenceIds,
    )
    assert proposal.provenance == "SERV_GENERATED"
    assert proposal.schemaValid is True
    assert len(proposal.evidenceIds) >= 1

    ev.servProposal = proposal
    ev.rationale = proposal.hypothesis
    rec = reppo.submit_evaluation(ev, meta.name)
    assert rec.provenance == "REPPO_LIVE"
    assert rec.status in ("PENDING", "SETTLED"), rec.critique

    deadline = time.time() + 120
    while rec.status == "PENDING" and time.time() < deadline:
        time.sleep(5)
        rec = reppo.poll_evaluation(rec)
    assert rec.status == "SETTLED", f"Reppo ended in {rec.status}: {rec.critique}"
    assert rec.score is not None and rec.route in ("ship", "review", "block")
