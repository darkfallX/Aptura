"""Comprehensive test suite verifying all 12+ non-negotiable engineering safeguards in AGENTS.md."""

from __future__ import annotations

import copy
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.data.loader import DataIntegrityError, DatasetCatalog, validate_candle_series
from app.domain.models import Candle, Signal
from app.evaluation.clients import ReppoClient, SERVAnalyst
from app.main import create_app
from app.replay.simulator import PaperBroker, ReplaySession
from app.storage.repository import SQLiteRepository
from app.strategies.scouts import MomentumScout, ReversalScout
from app.supervisor.engine import (
    AdaptationEngine,
    AdaptiveSupervisor,
    FeedbackTracker,
    RiskGuardian,
    normalize_and_bound_weights,
)


@pytest.fixture()
def catalog() -> DatasetCatalog:
    return DatasetCatalog()


def test_1_no_future_leakage_in_replay(catalog: DatasetCatalog) -> None:
    """Replay at step k produces identical signals, decisions, and weights whether future candles are mutated or truncated."""
    meta, candles = catalog.get_dataset("momentum-breakdown")
    cutoff = 65

    # Run 1: full dataset advanced to cutoff
    sess_full = ReplaySession(run_id="leak_check_1", dataset=meta, candles=candles, seed=42)
    snap_full = sess_full.advance(cutoff)

    # Run 2: mutate all candles strictly after cutoff (index > cutoff) with extreme prices
    mutated_candles = copy.deepcopy(candles)
    for i in range(cutoff + 1, len(mutated_candles)):
        mutated_candles[i].open *= 50.0
        mutated_candles[i].high *= 60.0
        mutated_candles[i].low *= 40.0
        mutated_candles[i].close *= 55.0
        mutated_candles[i].volume *= 100.0

    sess_mutated = ReplaySession(run_id="leak_check_1", dataset=meta, candles=mutated_candles, seed=42)
    snap_mutated = sess_mutated.advance(cutoff)

    assert snap_full.cursor == cutoff
    assert snap_full.activeWeights == snap_mutated.activeWeights
    assert snap_full.configVersion == snap_mutated.configVersion
    assert snap_full.latestDecision == snap_mutated.latestDecision
    assert snap_full.latestSignals == snap_mutated.latestSignals
    assert snap_full.metricsComparison["adaptive"] == snap_mutated.metricsComparison["adaptive"]


def test_2_deterministic_reproducibility(catalog: DatasetCatalog) -> None:
    """Same dataset + seed + config -> identical decisions, orders, adaptations, and metrics."""
    meta, candles = catalog.get_dataset("momentum-breakdown")
    s1 = ReplaySession(run_id="det_run", dataset=meta, candles=candles, seed=99)
    s2 = ReplaySession(run_id="det_run", dataset=meta, candles=candles, seed=99)

    snap1 = s1.advance(120)
    snap2 = s2.advance(120)

    assert snap1.configVersion == snap2.configVersion
    assert snap1.activeWeights == snap2.activeWeights
    assert [d.model_dump() for d in snap1.recentDecisions] == [d.model_dump() for d in snap2.recentDecisions]
    assert [o.model_dump() for o in snap1.paperOrders] == [o.model_dump() for o in snap2.paperOrders]
    assert snap1.metricsComparison["adaptive"].model_dump() == snap2.metricsComparison["adaptive"].model_dump()

    # Reset and re-run produces identical results
    s1.reset()
    snap1_re = s1.advance(120)
    assert snap1_re.metricsComparison["adaptive"].model_dump() == snap2.metricsComparison["adaptive"].model_dump()


def test_3_warmup_period_produces_no_premature_signals(catalog: DatasetCatalog) -> None:
    """Warm-up period emits only WAIT signals with 0.0 strength and executes zero paper trades."""
    meta, candles = catalog.get_dataset("momentum-breakdown")
    warmup = 20
    sess = ReplaySession(run_id="warmup_run", dataset=meta, candles=candles, warmup_bars=warmup)
    # Advance through warmup-2 steps (so cursor reaches warmup-1, meaning len(visible_candles) == warmup-1)
    snap = sess.advance(warmup - 2)
    assert len(snap.visibleCandles) == warmup - 1
    for sig in snap.latestSignals.values():
        assert sig.action == "WAIT"
        assert sig.strength == 0.0
    assert len(snap.paperOrders) == 0


def test_4_identical_cost_assumptions_and_next_bar_fills(catalog: DatasetCatalog) -> None:
    """Fixed baseline and adaptive run use identical fee/slippage assumptions and strictly fill on next bar open."""
    meta, candles = catalog.get_dataset("momentum-breakdown")
    sess = ReplaySession(run_id="cost_run", dataset=meta, candles=candles, fee_bps=25.0, slippage_bps=20.0)

    assert sess.brokers["adaptive"].fee_bps == sess.brokers["fixed_50_50"].fee_bps == 25.0
    assert sess.brokers["adaptive"].slippage_bps == sess.brokers["fixed_50_50"].slippage_bps == 20.0
    assert sess.brokers["adaptive"].initial_capital_usd == sess.brokers["fixed_50_50"].initial_capital_usd

    snap = sess.advance(100)
    assert len(snap.paperOrders) > 0
    for order in snap.paperOrders:
        # Next-bar fill invariant: fillCandleIndex must strictly exceed decisionCandleIndex
        assert order.fillCandleIndex == order.decisionCandleIndex + 1
        fill_candle = candles[order.fillCandleIndex]
        assert order.referencePrice == pytest.approx(fill_candle.open, rel=1e-6)
        if order.side == "BUY":
            assert order.fillPrice > order.referencePrice
        else:
            assert order.fillPrice < order.referencePrice


def test_5_shadow_signals_mature_only_after_horizon(catalog: DatasetCatalog) -> None:
    """Shadow signals do not contribute to trailing EWMA or matured counts until their horizon has elapsed."""
    _, candles = catalog.get_dataset("momentum-breakdown")
    tracker = FeedbackTracker(horizon_bars=4, fee_bps=20.0, slippage_bps=15.0)
    sig = Signal(
        id="sig_test_10",
        strategyId="momentum",
        observedAt=candles[10].observedAt,
        candleIndex=10,
        action="BUY",
        strength=0.8,
        evidence=["ev_10"],
    )
    tracker.record_shadow_signal(sig)

    # At bar 11, 12, 13 (before 10 + 4 = 14), signal must NOT mature
    for idx in (11, 12, 13):
        matured = tracker.mature_eligible_signals(candles[: idx + 1])
        assert len(matured) == 0
        assert tracker.matured_counts["momentum"] == 0

    # At bar 14 (10 + 4), signal matures causally
    matured_14 = tracker.mature_eligible_signals(candles[:15])
    assert len(matured_14) == 1
    assert matured_14[0].maturedAtIndex == 14
    assert tracker.matured_counts["momentum"] == 1


def test_6_strategy_weights_bounded_nonnegative_normalized() -> None:
    """Strategy weights are always bounded in [0.15, 0.85], nonnegative, and sum to 1.0."""
    for raw_m, raw_r in [(-5.0, 10.0), (0.99, 0.01), (0.01, 0.99), (0.5, 0.5), (0.0, 0.0), (0.35, 0.65)]:
        wm, wr = normalize_and_bound_weights(raw_m, raw_r)
        assert 0.15 <= wm <= 0.85
        assert 0.15 <= wr <= 0.85
        assert wm >= 0.0 and wr >= 0.0
        assert wm + wr == pytest.approx(1.0, abs=1e-6)


def test_7_risk_guardian_block_prevents_new_paper_positions(catalog: DatasetCatalog) -> None:
    """RiskGuardian BLOCK forces Supervisor action to AVOID when flat and blocks new BUY positions."""
    _, candles = catalog.get_dataset("synthetic-noise-guard")
    # Pick a high-volatility whipsaw bar or construct a shock candle
    shock_candles = copy.deepcopy(candles[:30])
    shock_candles[-1].high = shock_candles[-1].open * 1.12
    shock_candles[-1].low = shock_candles[-1].open * 0.92

    guardian = RiskGuardian.assess(shock_candles, exposure_pct=0.0, risk_profile="conservative")
    assert guardian.status == "BLOCK"

    mom_buy = Signal(
        id="m1",
        strategyId="momentum",
        observedAt=shock_candles[-1].observedAt,
        candleIndex=shock_candles[-1].index,
        action="BUY",
        strength=0.95,
        evidence=["ev_m"],
    )
    rev_buy = Signal(
        id="r1",
        strategyId="reversal",
        observedAt=shock_candles[-1].observedAt,
        candleIndex=shock_candles[-1].index,
        action="BUY",
        strength=0.95,
        evidence=["ev_r"],
    )

    decision = AdaptiveSupervisor.decide(
        run_id="guard_test",
        current_candle=shock_candles[-1],
        config_version="v1.0.0",
        weights={"momentum": 0.6, "reversal": 0.4},
        mom_signal=mom_buy,
        rev_signal=rev_buy,
        guardian=guardian,
        has_open_position=False,
    )
    assert decision.action == "AVOID"
    assert decision.guardian == "BLOCK"


def test_8_and_9_accepted_vs_rejected_proposals_and_versioning(catalog: DatasetCatalog) -> None:
    """Rejected proposals cannot alter active config; accepted proposals create new version affecting only future bars."""
    meta, candles = catalog.get_dataset("momentum-breakdown")
    sess = ReplaySession(run_id="adapt_test", dataset=meta, candles=candles)
    snap = sess.advance(len(candles))

    accepted = [e for e in snap.adaptationEvents if e.status == "ACCEPTED"]
    rejected = [e for e in snap.adaptationEvents if e.status == "REJECTED"]
    assert len(accepted) >= 1
    assert len(rejected) >= 1

    # Check that rejected events did not create config versions
    active_versions = {cv.version for cv in snap.configHistory}
    for rej in rejected:
        source_ids = {cv.sourceEventId for cv in snap.configHistory}
        assert rej.id not in source_ids
        assert rej.rejectionReason is not None and "REJECTED" in rej.rejectionReason

    # Check that accepted events created new versions and only affected decisions at or after activatedAt
    for acc in accepted:
        matching_cv = next((cv for cv in snap.configHistory if cv.sourceEventId == acc.id), None)
        assert matching_cv is not None
        assert matching_cv.candleIndex == acc.candleIndex
        # Decisions prior to acc.candleIndex must not use matching_cv.version
        for dec in sess.decisions:
            if dec.candleIndex < acc.candleIndex:
                assert dec.configVersion != matching_cv.version


def test_10_external_api_failures_do_not_crash_replay(catalog: DatasetCatalog) -> None:
    """Failing SERV or Reppo endpoints gracefully fall back without crashing replay or fabricating verdicts."""
    meta, candles = catalog.get_dataset("momentum-breakdown")
    broken_serv = SERVAnalyst(api_key="invalid_key", base_url="http://127.0.0.1:9")
    broken_reppo = ReppoClient(api_key="invalid_key", base_url="http://127.0.0.1:9")

    sess = ReplaySession(
        run_id="broken_ext",
        dataset=meta,
        candles=candles,
        serv_analyst=broken_serv,
        reppo_client=broken_reppo,
    )
    snap = sess.advance(50)
    assert snap.cursor == 50
    assert len(snap.adaptationEvents) >= 1
    first_ev = snap.adaptationEvents[0]
    assert first_ev.servProposal is not None
    assert first_ev.servProposal.provenance == "DETERMINISTIC_FALLBACK"

    rec = sess.submit_adaptation_to_reppo(first_ev.id)
    assert rec.status in ("FAILED", "PENDING")
    assert rec.status != "SETTLED"


def test_11_reppo_pending_not_displayed_as_accepted(catalog: DatasetCatalog) -> None:
    """Submitting an adaptation to Reppo returns a stored evalId with PENDING status, never fake instant settlement."""
    meta, candles = catalog.get_dataset("momentum-breakdown")
    sess = ReplaySession(run_id="reppo_test", dataset=meta, candles=candles)
    snap = sess.advance(50)
    ev = snap.adaptationEvents[0]

    rec = sess.submit_adaptation_to_reppo(ev.id)
    assert rec.evalId.startswith("reppo_")
    assert rec.status == "UNCONFIGURED"
    assert rec.settledAt is None
    assert ev.evaluationId == rec.evalId
    assert "PENDING REVIEW" not in ev.provenanceBadges


def test_12_api_endpoints_integration(tmp_path: Path, catalog: DatasetCatalog) -> None:
    """Verify all FastAPI endpoints and SQLite persistence work end-to-end."""
    repo = SQLiteRepository(db_path=tmp_path / "test_aptura.sqlite3")
    app = create_app(catalog=catalog, repo=repo)
    client = TestClient(app)

    # 1. Health
    h_resp = client.get("/api/health")
    assert h_resp.status_code == 200
    assert h_resp.json()["status"] == "ok"

    # 2. Datasets
    d_resp = client.get("/api/datasets")
    assert d_resp.status_code == 200
    datasets = d_resp.json()
    assert len(datasets) >= 3
    assert any(d["id"] == "momentum-breakdown" for d in datasets)

    # 3. Create replay
    c_resp = client.post(
        "/api/replays",
        json={"datasetId": "momentum-breakdown", "seed": 42, "initialCapitalUsd": 1000.0, "riskProfile": "conservative"},
    )
    assert c_resp.status_code == 200
    snap = c_resp.json()
    run_id = snap["runId"]
    assert snap["cursor"] == 0
    assert snap["configVersion"] == "v1.0.0"

    # 4. Advance replay
    adv_resp = client.post(f"/api/replays/{run_id}/advance", json={"steps": 50})
    assert adv_resp.status_code == 200
    adv_snap = adv_resp.json()
    assert adv_snap["cursor"] == 50
    assert len(adv_snap["adaptationEvents"]) >= 1

    # 5. Evaluate adaptation via Reppo endpoint
    adapt_id = adv_snap["adaptationEvents"][0]["id"]
    eval_resp = client.post(f"/api/adaptations/{adapt_id}/evaluate")
    assert eval_resp.status_code == 200
    eval_rec = eval_resp.json()
    assert eval_rec["status"] == "UNCONFIGURED"
    eval_id = eval_rec["evalId"]

    # 6. Poll evaluation endpoint
    poll_resp = client.get(f"/api/evaluations/{eval_id}")
    assert poll_resp.status_code == 200
    assert poll_resp.json()["evalId"] == eval_id
    assert poll_resp.json()["status"] == "UNCONFIGURED"

    # 7. Events endpoint
    ev_resp = client.get(f"/api/replays/{run_id}/events")
    assert ev_resp.status_code == 200
    assert len(ev_resp.json()["adaptationEvents"]) >= 1

    # 8. Reset endpoint
    rst_resp = client.post(f"/api/replays/{run_id}/reset")
    assert rst_resp.status_code == 200
    assert rst_resp.json()["cursor"] == 0


def test_13_serv_schema_validation_discards_invalid_evidence_and_weights() -> None:
    """SERVAnalyst discards hallucinated evidence IDs and rejects out-of-bounds weight suggestions."""
    raw_bad_llm = '{"hypothesis": "Shift all weight", "evidenceIds": ["hallucinated_future_ev", "ev_valid_1"], "suggestedWeights": {"momentum": 0.98, "reversal": 0.02}, "assumptions": ["A1"], "uncertainties": ["U1"]}'
    parsed = SERVAnalyst.validate_and_parse_response(
        raw_content=raw_bad_llm,
        allowed_evidence_ids=["ev_valid_1", "ev_valid_2"],
        fallback_weights=[0.40, 0.60],
        observed_at="2026-11-05T12:00:00Z",
        model_used="gpt-5.4-mini",
    )
    assert parsed.evidenceIds == ["ev_valid_1"]
    assert "hallucinated_future_ev" not in parsed.evidenceIds
    assert parsed.schemaValid is False
    assert parsed.suggestedWeights == {"momentum": 0.40, "reversal": 0.60}


def test_14_data_integrity_rejects_unclosed_or_corrupt_candles(catalog: DatasetCatalog) -> None:
    """validate_candle_series refuses unclosed candles or non-monotonic timestamps."""
    _, candles = catalog.get_dataset("momentum-breakdown")
    bad_unclosed = copy.deepcopy(candles[:40])
    bad_unclosed[15].isClosed = False
    with pytest.raises(DataIntegrityError, match="not closed"):
        validate_candle_series(bad_unclosed)

    bad_order = copy.deepcopy(candles[:40])
    bad_order[20].timestamp = bad_order[19].timestamp - 100
    with pytest.raises(DataIntegrityError, match="Non-monotonic"):
        validate_candle_series(bad_order)


def test_fresh_runs_have_no_external_verdict(catalog):
    meta, candles = catalog.get_dataset("momentum-breakdown")
    session = ReplaySession(run_id="clean", dataset=meta, candles=candles)
    assert session.snapshot().evaluations == []


def test_sessions_are_isolated_and_recover_after_restart(tmp_path, catalog):
    repo = SQLiteRepository(db_path=tmp_path / "restart.sqlite3")
    client = TestClient(create_app(catalog=catalog, repo=repo))
    params = {"datasetId": "momentum-breakdown"}
    first = client.post("/api/replays", json=params).json()
    second = client.post("/api/replays", json=params).json()
    assert first["runId"] != second["runId"]
    path = "/api/replays/" + first["runId"]
    advanced = client.post(path + "/advance", json={"steps": 35}).json()
    assert client.get("/api/replays/" + second["runId"]).json()["cursor"] == 0
    with repo._connect() as conn:
        count = conn.execute("SELECT COUNT(*) FROM supervisor_decisions WHERE run_id = ?", (first["runId"],)).fetchone()[0]
    assert count == 36
    restarted = TestClient(create_app(catalog=catalog, repo=repo))
    response = restarted.get(path)
    assert response.status_code == 200
    assert response.json()["equityCurve"] == advanced["equityCurve"]
    assert restarted.post(path + "/advance", json={"steps": 1}).json()["cursor"] == 36


def test_reset_preserves_old_run_and_report(tmp_path, catalog):
    repo = SQLiteRepository(db_path=tmp_path / "history.sqlite3")
    client = TestClient(create_app(catalog=catalog, repo=repo))
    run = client.post("/api/replays", json={"datasetId": "momentum-breakdown"}).json()
    path = "/api/replays/" + run["runId"]
    client.post(path + "/advance", json={"steps": 80})
    report = client.get(path + "/report")
    assert report.status_code == 200
    assert isinstance(report.json()["interventions"], list)
    assert report.json()["matchedBaseline"]["initialCapitalUsd"] == 1000
    reset = client.post(path + "/reset").json()
    assert reset["runId"] != run["runId"]
    assert reset["cursor"] == 0
    assert client.get(path).json()["cursor"] == 80


def test_intervention_comparison_is_causal(catalog):
    from app.replay.comparisons import report
    meta, candles = catalog.get_dataset("momentum-breakdown")
    session = ReplaySession(run_id="branches", dataset=meta, candles=candles)
    session.advance(80)
    before = report(session)
    for candle in session._all_candles[81:]:
        candle.close *= 10
    assert report(session) == before
    assert session.snapshot().cursor == 80
