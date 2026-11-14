"""Feedback revise loop, rate limiting and public-mode Reppo lock on /api/v1/supervise."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.evaluation.clients import ReppoClient, SERVAnalyst
from app.main import create_app
from app.storage.repository import SQLiteRepository


class EchoSERV(SERVAnalyst):
    """Returns the bounded fallback candidate and records the feedback it was given."""

    def __init__(self):
        super().__init__(api_key="mock")
        self.contexts: list[dict] = []

    def is_configured(self) -> bool:
        return True

    def generate_proposal(self, observed_at, dataset_name, old_weights, candidate_weights, momentum_score,
                          reversal_score, matured_count, allowed_evidence_ids, extra_context=None):
        self.contexts.append(extra_context or {})
        return SERVAnalyst._build_deterministic_proposal(
            observed_at, dataset_name, old_weights, candidate_weights, momentum_score, reversal_score,
            matured_count, allowed_evidence_ids, "mock",
        ).model_copy(update={"provenance": "SERV_GENERATED", "modelUsed": "mock"})


ROGUE = {
    "agentName": "rogue-bot",
    "datasetId": "momentum-breakdown",
    "currentWeights": {"momentum": 0.6, "reversal": 0.4},
    "proposedWeights": {"momentum": 0.05, "reversal": 0.95},
}


def make(tmp_path: Path, serv=None, monkeypatch=None, **env):
    if monkeypatch:
        for k, v in env.items():
            monkeypatch.setenv(k, v)
    return TestClient(create_app(repo=SQLiteRepository(tmp_path / "s.db"), serv_analyst=serv or EchoSERV(),
                                 reppo_client=ReppoClient(api_key="")))


def test_default_has_single_round(tmp_path: Path) -> None:
    body = make(tmp_path).post("/api/v1/supervise", json=ROGUE).json()
    assert body["decision"] == "BLOCK"
    assert len(body["rounds"]) == 1
    assert body["rounds"][0]["source"] == "caller"


def test_rejection_feedback_reaches_serv_and_revisions_shrink(tmp_path: Path) -> None:
    serv = EchoSERV()
    body = make(tmp_path, serv).post("/api/v1/supervise", json={**ROGUE, "maxRevisions": 2}).json()
    rounds = body["rounds"]
    assert rounds[0]["verdict"] == "BLOCK"
    assert len(rounds) >= 2
    assert rounds[1]["source"] == "serv-revision"
    # The gate's rejection reason is passed to SERV as feedback.
    feedback = [c for c in serv.contexts if c.get("revisionRound")]
    assert feedback and "REJECTED" in feedback[0]["gateFeedback"]
    # Each revision moves back toward the current 60/40 mix.
    moves = [abs(r["weights"]["momentum"] - 0.6) for r in rounds]
    assert moves == sorted(moves, reverse=True)
    assert body["improvement"]["rounds"] == len(rounds)
    assert body["improvement"]["firstVerdict"] == "BLOCK"


def test_rate_limit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = make(tmp_path, monkeypatch=monkeypatch, APTURA_SUPERVISE_PER_MIN="2")
    codes = [client.post("/api/v1/supervise", json=ROGUE).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_public_mode_refuses_reppo_without_admin_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = make(tmp_path, monkeypatch=monkeypatch, APTURA_PUBLIC="1", APTURA_ADMIN_KEY="secret")
    body = client.post("/api/v1/supervise", json={**ROGUE, "runReppoReview": True}).json()
    assert body["unitEconomics"]["reppoReviewAllowed"] is False
    assert body["reppoEvaluation"] is None
    ok = client.post("/api/v1/supervise", json={**ROGUE, "runReppoReview": True},
                     headers={"x-aptura-admin-key": "secret"}).json()
    assert ok["unitEconomics"]["reppoReviewAllowed"] is True


class WorseRevisionSERV(EchoSERV):
    """First proposal is the caller's; every revision jumps to an extreme-but-bounded mix that fails the gate."""

    def generate_proposal(self, *a, extra_context=None, **k):
        p = super().generate_proposal(*a, extra_context=extra_context, **k)
        if extra_context and extra_context.get("revisionRound"):
            p = p.model_copy(update={"suggestedWeights": {"momentum": 0.85, "reversal": 0.15}})
        return p


def test_revision_never_replaces_a_passing_round(tmp_path: Path) -> None:
    client = make(tmp_path, WorseRevisionSERV())
    body = client.post("/api/v1/supervise", json={
        "agentName": "ok-bot", "datasetId": "momentum-breakdown", "cursorIndex": 70,
        "currentWeights": {"momentum": 0.6, "reversal": 0.4},
        "proposedWeights": {"momentum": 0.45, "reversal": 0.55}, "maxRevisions": 1,
    }).json()
    assert body["rounds"][0]["gatePassed"] is True
    # Round 0 already ships (SERV configured, gate passed, no review requested), so no revision is attempted.
    assert body["decision"] == "SHIP"
    assert body["proposedWeights"] == {"momentum": 0.45, "reversal": 0.55}
    assert body["improvement"]["chosenRound"] == 0


class ReviewRoutingReppo(ReppoClient):
    """Settles every review instantly with route=review (medium confidence), like the live run."""

    def __init__(self):
        super().__init__(api_key="mock")

    def is_configured(self) -> bool:
        return True

    def submit_evaluation(self, event, dataset_name):
        from app.domain.models import ReppoEvaluationRecord
        return ReppoEvaluationRecord(
            evalId=f"mock_{event.id}", adaptationEventId=event.id, runId=event.runId, type="action",
            status="SETTLED", submittedAt="2026-11-14T00:00:00Z", payload="{}", criteria=[], context="",
            requestHash="x", score=81.0, decision="accept", confidence="medium", route="review",
            critique="Medium confidence.", provenance="REPPO_LIVE", creditsCharged=440,
        )


def test_worse_revision_after_review_keeps_the_passing_round(tmp_path: Path) -> None:
    client = TestClient(create_app(repo=SQLiteRepository(tmp_path / "r.db"), serv_analyst=WorseRevisionSERV(),
                                   reppo_client=ReviewRoutingReppo()))
    body = client.post("/api/v1/supervise", json={
        "agentName": "ok-bot", "datasetId": "momentum-breakdown", "cursorIndex": 70,
        "currentWeights": {"momentum": 0.6, "reversal": 0.4},
        "proposedWeights": {"momentum": 0.45, "reversal": 0.55},
        "runReppoReview": True, "maxRevisions": 1,
    }).json()
    assert [r["verdict"] for r in body["rounds"]] == ["REVIEW", "BLOCK"]
    assert body["decision"] == "REVIEW"
    assert body["proposedWeights"] == {"momentum": 0.45, "reversal": 0.55}
    assert body["improvement"]["chosenRound"] == 0
    # The failing revision was never sent to Reppo.
    assert body["unitEconomics"]["reppoCreditsCharged"] == 440
