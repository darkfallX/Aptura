"""FastAPI backend entry point for Aptura Adaptive AI Trading Supervisor."""

from __future__ import annotations

import datetime
import hashlib
import uuid
from copy import deepcopy
import time
import threading
from contextlib import asynccontextmanager
from app.storage.locking import process_lock
from app.evaluation.workflow import new_job, process_job
from functools import wraps
from app.replay.comparisons import report
from pathlib import Path
from typing import Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.data.loader import DatasetCatalog
from app.data.market import MarketRecorder
from app.data.live import LiveMarket
from app.supervisor.live import LiveSupervisors
import httpx
from app.domain.models import (
    AdaptationEvent,
    DatasetMetadata,
    ReplayAdvanceRequest,
    ReplayCreateRequest,
    ReplaySnapshot,
    ReppoEvaluationRecord,
    SuperviseRequest,
    SuperviseResponse,
)
from app.evaluation.clients import ReppoClient, SERVAnalyst
from app.replay.comparisons import validate_weights
from app.replay.simulator import ReplaySession
from app.storage.repository import SQLiteRepository
from app.supervisor.engine import normalize_and_bound_weights


class MarketWatchRequest(BaseModel):
    enabled: bool = True


class ReplaySeekRequest(BaseModel):
    targetIndex: int = Field(ge=0, le=100000)


def create_app(
    catalog: DatasetCatalog | None = None,
    repo: SQLiteRepository | None = None,
    serv_analyst: SERVAnalyst | None = None,
    reppo_client: ReppoClient | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app):
        stop = threading.Event()
        worker = threading.Thread(target=review_worker, args=(stop,), daemon=True)
        worker.start()
        live_worker = threading.Thread(target=supervision_worker, args=(stop,), daemon=True)
        live_worker.start()
        yield
        stop.set()
        worker.join(timeout=1)
        live_worker.join(timeout=1)

    app = FastAPI(
        lifespan=lifespan,
        title="Aptura - Adaptive AI Strategy Supervisor API",
        version="1.0.0",
        description=(
            "Paper-trading research laboratory and adaptive strategy supervisor for historical Solana pool replay. "
            "Built for OpenServ Hackathon 02 (Reppo Track)."
        ),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    data_catalog = catalog or DatasetCatalog()
    storage_repo = repo or SQLiteRepository()
    live_market = LiveMarket()
    recorder = MarketRecorder(storage_repo.db_path.parent / "market-captures")
    recorder.restore(data_catalog)
    serv = serv_analyst or SERVAnalyst()
    reppo = reppo_client or ReppoClient()
    live_supervisors = LiveSupervisors(storage_repo, data_catalog, serv, reppo)

    # Sync all datasets into SQLite on startup
    for meta in data_catalog.list_metadata():
        _, candles = data_catalog.get_dataset(meta.id)
        storage_repo.sync_dataset(meta, candles)

    sessions: dict[str, ReplaySession] = {}
    mutation_lock = threading.RLock()
    lock_depth = threading.local()
    def serialized(fn):
        @wraps(fn)
        def invoke(*args, **kwargs):
            with mutation_lock:
                if getattr(lock_depth, 'active', False):
                    return fn(*args, **kwargs)
                with process_lock(str(storage_repo.db_path) + '.lock'):
                    lock_depth.active = True
                    try:
                        return fn(*args, **kwargs)
                    finally:
                        lock_depth.active = False
        return invoke


    def resolve_session(run_id: str) -> ReplaySession | None:
        if live_supervisors.state_for(run_id=run_id):
            return live_supervisors.resolve(run_id)
        saved = storage_repo.get_snapshot(run_id)
        if run_id in sessions and saved and sessions[run_id].cursor == saved.cursor:
            sessions[run_id].activation_commands = storage_repo.list_activations(run_id)
            return sessions[run_id]
        if saved is None:
            return None
        if saved.dataset.id not in {m.id for m in data_catalog.list_metadata()}:
            recorder.restore(data_catalog)
        meta, candles = data_catalog.get_dataset(saved.dataset.id)
        if meta.sha256Hash != saved.dataset.sha256Hash:
            raise HTTPException(status_code=409, detail="Dataset changed; cannot resume this run")
        # Reconstruct the deterministic engine without making external calls.
        restored = ReplaySession(
            run_id=run_id, dataset=meta, candles=candles, seed=saved.seed,
            initial_capital_usd=saved.initialCapitalUsd, risk_profile=saved.riskProfile,
            fee_bps=saved.feeBps, slippage_bps=saved.slippageBps,
            warmup_bars=saved.warmupBars, evaluation_horizon_bars=saved.evaluationHorizonBars,
            serv_analyst=SERVAnalyst(api_key=""), reppo_client=reppo,
            activation_commands=storage_repo.list_activations(run_id),
        )
        restored.advance(saved.cursor)
        # Never silently resume a run whose recorded algorithm produced different results.
        if restored.snapshot().equityCurve != saved.equityCurve:
            raise HTTPException(status_code=409, detail="Algorithm changed; start a new run")
        storage_repo.restore_outcomes(run_id, restored.tracker.matured_outcomes)
        restored.evaluations = {e.evalId: e for e in saved.evaluations}
        for event in restored.adaptation_events:
            original = next((e for e in saved.adaptationEvents if e.id == event.id), None)
            if original and original.evaluationId in restored.evaluations:
                event.evaluationId = original.evaluationId
                event.reppoStatus = restored.evaluations[original.evaluationId].status
        sessions[run_id] = restored
        return restored

    @serialized
    def review_context(run_id):
        session = resolve_session(run_id)
        return deepcopy(session) if session else None

    @serialized
    def finalize_review(job):
        from app.domain.models import ReppoEvaluationRecord
        class SettledResult:
            def poll_evaluation(self, record):
                return ReppoEvaluationRecord.model_validate(job['evaluation'])
        session = resolve_session(job['runId'])
        live_state = live_supervisors.state_for(run_id=job['runId'])
        if live_state and (not live_state['enabled'] or live_state['feedStatus'] != 'FRESH'):
            job.update(state='EXPIRED', message='Live supervision is paused or delayed; no change activated.')
            storage_repo.save_job(job)
            return
        job['nextAttemptAt'] = 0
        process_job(job, session, storage_repo, serv, SettledResult())

    def review_tick():
        for job in storage_repo.list_jobs():
            if job['state'] not in ('QUEUED', 'READY_TO_SUBMIT', 'SUBMITTING', 'PENDING_REVIEW', 'SCHEDULED'):
                continue
            try:
                session = review_context(job['runId'])
                if session:
                    process_job(job, session, storage_repo, serv, reppo, finalize=finalize_review)
            except Exception as exc:
                job.update(state='FAILED', message=f'Review halted ({type(exc).__name__}); no promotion.')
                storage_repo.save_job(job)

    def review_worker(stop):
        while not stop.wait(2):
            try:
                with process_lock(str(storage_repo.db_path) + ".worker.lock"):
                    review_tick()
                    market_tick()
            except Exception:
                # Contention is retried; persisted state is authoritative.
                continue

    @serialized
    def commit_live(metadata, feed):
        return live_supervisors.observe(metadata, feed)

    def supervision_tick():
        for state in storage_repo.list_live_supervisors():
            if not state['enabled']:
                continue
            metadata, _ = data_catalog.get_dataset(state['marketId'])
            feed = live_market.snapshot(metadata)
            commit_live(metadata, feed)

    def supervision_worker(stop):
        while not stop.wait(15):
            try:
                with process_lock(str(storage_repo.db_path) + '.live-worker.lock'):
                    supervision_tick()
            except Exception:
                # No fabricated update on failure. Existing state ages into PAUSED.
                continue

    app.state.supervision_tick = supervision_tick

    @app.post('/api/live/{market_id}/supervision')
    @serialized
    def toggle_supervision(market_id: str, req: MarketWatchRequest):
        state = live_supervisors.state_for(market_id=market_id)
        if state is None:
            raise HTTPException(404, 'Open this live market first')
        state['enabled'] = req.enabled
        state['hadInterruption'] = True
        storage_repo.save_live_supervisor(state)
        return live_supervisors.summary(state)

    @serialized
    def commit_capture(meta, candles):
        data_catalog.register(meta, candles)
        storage_repo.sync_dataset(meta, candles)

    def market_tick():
        for watch in storage_repo.list_watches():
            if not watch['enabled'] or time.time() < watch.get('nextAttemptAt', 0):
                continue
            try:
                metadata, _ = data_catalog.get_dataset(watch['id'])
                meta, candles, status = recorder.capture(metadata)
                commit_capture(meta, candles)
                watch.update(status, failures=0, message='Recording closed hourly candles; no live execution.')
                watch['nextAttemptAt'] = time.time() + 60
            except Exception as exc:
                failures = watch.get('failures', 0) + 1
                watch.update(status='UNAVAILABLE', failures=failures,
                    message=f'Provider fetch failed ({type(exc).__name__}); last capture retained.',
                    nextAttemptAt=time.time() + min(900, 30 * 2 ** min(failures, 5)))
            current = next((w for w in storage_repo.list_watches() if w['id'] == watch['id']), watch)
            watch['enabled'] = current['enabled']
            storage_repo.save_watch(watch)

    @app.get('/api/market/watches')
    @serialized
    def get_market_watches():
        watches = storage_repo.list_watches()
        for watch in watches:
            if watch.get('lastClosedAt'):
                age = time.time() - datetime.datetime.fromisoformat(watch['lastClosedAt'].replace('Z', '+00:00')).timestamp()
                watch['ageSeconds'] = max(0, round(age))
                if watch.get('status') == 'FRESH' and age > 3900:
                    watch['status'] = 'STALE'
        return watches

    @app.post('/api/market/{dataset_id}/watch')
    @serialized
    def set_market_watch(dataset_id: str, req: MarketWatchRequest):
        try:
            metadata, _ = data_catalog.get_dataset(dataset_id)
        except KeyError:
            raise HTTPException(404, 'Dataset not found')
        if metadata.isSynthetic:
            raise HTTPException(422, 'Synthetic dataset has no live feed')
        watch = next((w for w in storage_repo.list_watches() if w['id'] == dataset_id),
                     {'id': dataset_id, 'status': 'WAITING', 'nextAttemptAt': 0})
        watch['enabled'] = req.enabled
        storage_repo.save_watch(watch)
        return watch

    app.state.review_tick = review_tick
    app.state.market_tick = market_tick

    @app.get('/api/replays/{run_id}/reviews')
    @serialized
    def get_reviews(run_id: str):
        if resolve_session(run_id) is None:
            raise HTTPException(404, 'Run not found')
        return storage_repo.list_jobs(run_id)

    @app.post('/api/adaptations/{adaptation_id}/review')
    @serialized
    def request_review(adaptation_id: str):
        event = storage_repo.get_adaptation_event(adaptation_id)
        if event is None:
            raise HTTPException(404, 'Adaptation not found')
        session = resolve_session(event.runId)
        existing = next((j for j in storage_repo.list_jobs(event.runId)
            if j['sourceEventId'] == adaptation_id and j['state'] not in ('REJECTED', 'FAILED', 'EXPIRED', 'UNCONFIGURED')), None)
        if existing:
            return existing
        job = new_job(session, event, serv.is_configured() and reppo.is_configured())
        storage_repo.save_job(job)
        return job

    @app.get('/api/live/markets')
    def live_markets():
        return [{'id':m.id,'name':m.baseAsset,'pair':m.name} for m in data_catalog.list_metadata()
                if not m.isSynthetic and not m.id.startswith('capture_')]

    @app.get('/api/live/{market_id}')
    def live_snapshot(market_id: str):
        try:
            meta, _ = data_catalog.get_dataset(market_id)
        except KeyError:
            raise HTTPException(404, 'Market not found')
        if meta.isSynthetic or market_id.startswith('capture_'):
            raise HTTPException(422, 'Choose a current market')
        feed = live_market.snapshot(meta)
        feed["supervisor"] = commit_live(meta, feed)
        return feed

    @app.get("/api/health")
    @serialized
    def get_health() -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "aptura-api",
            "version": "1.0.0",
            "timestampUtc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "datasetsLoaded": len(data_catalog.list_metadata()),
            "integrations": {
                "servReasoningConfigured": serv.is_configured(),
                "servBaseUrl": serv.base_url,
                "servModel": serv.model,
                "reppoConfigured": reppo.is_configured(),
                "reppoBaseUrl": reppo.base_url,
                "reppoSettlementMinutes": reppo.settlement_minutes,
            },
        }

    @app.post('/api/market/{dataset_id}/capture')
    def capture_market(dataset_id: str):
        try:
            metadata, _ = data_catalog.get_dataset(dataset_id)
        except KeyError:
            raise HTTPException(404, 'Dataset not found')
        if metadata.isSynthetic:
            raise HTTPException(422, 'Synthetic datasets have no market feed')
        try:
            meta, candles, status = recorder.capture(metadata)
        except httpx.HTTPError:
            raise HTTPException(503, 'Market provider unavailable or rate limited. Existing captures remain available.')
        except (ValueError, KeyError, IndexError):
            raise HTTPException(502, 'Market response failed integrity validation; no capture registered.')
        commit_capture(meta, candles)
        return status

    @app.get("/api/datasets", response_model=list[DatasetMetadata])
    @serialized
    def list_datasets() -> list[DatasetMetadata]:
        recorder.restore(data_catalog)
        return data_catalog.list_metadata()

    @app.post("/api/replays", response_model=ReplaySnapshot)
    @serialized
    def create_replay(req: ReplayCreateRequest) -> ReplaySnapshot:
        try:
            meta, candles = data_catalog.get_dataset(req.datasetId)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        # Unique session identity; numerical reproducibility comes from inputs.
        run_id = "run_" + uuid.uuid4().hex

        session = ReplaySession(
            run_id=run_id,
            dataset=meta,
            candles=candles,
            seed=req.seed,
            initial_capital_usd=req.initialCapitalUsd,
            risk_profile=req.riskProfile,
            fee_bps=req.feeBps,
            slippage_bps=req.slippageBps,
            warmup_bars=req.warmupBars,
            evaluation_horizon_bars=req.evaluationHorizonBars,
            serv_analyst=serv,
            reppo_client=reppo,
        )
        sessions[run_id] = session
        snap = session.snapshot()
        storage_repo.save_snapshot(snap)
        return snap

    @app.get("/api/replays/{run_id}", response_model=ReplaySnapshot)
    @serialized
    def get_replay(run_id: str) -> ReplaySnapshot:
        session = resolve_session(run_id)
        if session is None:
            raise HTTPException(status_code=404, detail=f"Replay run '{run_id}' not found")
        return session.snapshot()

    @app.post("/api/replays/{run_id}/advance", response_model=ReplaySnapshot)
    @serialized
    def advance_replay(run_id: str, req: ReplayAdvanceRequest) -> ReplaySnapshot:
        session = resolve_session(run_id)
        if session and session.is_live:
            raise HTTPException(409, "Live runs advance only when fresh market observations arrive")
        if session is None:
            raise HTTPException(status_code=404, detail=f"Replay run '{run_id}' not found")
        snap = session.snapshot()
        for _ in range(req.steps):
            snap = session.advance(1)
            storage_repo.save_snapshot(snap)
            if snap.status == "FINISHED":
                break
        return snap

    @app.post("/api/replays/{run_id}/seek", response_model=ReplaySnapshot)
    @serialized
    def seek_replay(run_id: str, req: ReplaySeekRequest) -> ReplaySnapshot:
        session = resolve_session(run_id)
        if session and session.is_live:
            raise HTTPException(409, "Live runs advance only when fresh market observations arrive")
        if session is None:
            raise HTTPException(status_code=404, detail=f"Replay run '{run_id}' not found")
        target = min(req.targetIndex, len(session._all_candles) - 1)
        if target < session.cursor:
            fresh = reset_replay(run_id)
            session = resolve_session(fresh.runId)
        steps_needed = target - session.cursor
        if steps_needed > 0:
            for _ in range(steps_needed):
                storage_repo.save_snapshot(session.advance(1))
        snap = session.snapshot()
        storage_repo.save_snapshot(snap)
        return snap

    @app.post("/api/replays/{run_id}/reset", response_model=ReplaySnapshot)
    @serialized
    def reset_replay(run_id: str) -> ReplaySnapshot:
        session = resolve_session(run_id)
        if session and session.is_live:
            raise HTTPException(409, "Live runs advance only when fresh market observations arrive")
        if session is None:
            raise HTTPException(status_code=404, detail=f"Replay run '{run_id}' not found")
        # Reset starts a new run; the original audit remains addressable.
        return create_replay(ReplayCreateRequest(datasetId=session.dataset.id,
            seed=session.seed, initialCapitalUsd=session.initial_capital_usd,
            riskProfile=session.risk_profile, feeBps=session.fee_bps,
            slippageBps=session.slippage_bps, warmupBars=session.warmup_bars,
            evaluationHorizonBars=session.evaluation_horizon_bars))

    @app.get('/api/replays/{run_id}/audit')
    @serialized
    def export_audit(run_id: str):
        saved = storage_repo.get_snapshot(run_id)
        if saved is None:
            raise HTTPException(404, 'Run not found')
        return {'snapshot': saved, 'audit': storage_repo.audit_trail(run_id),
                'reviews': storage_repo.list_jobs(run_id),
                'methodology': 'Paper only. USD prices. Candle observations at close, fills at next contiguous open. Selection precedes a separate 24-bar broker validation. Shadow utility is not portfolio P&L.'}

    @app.get("/api/replays/{run_id}/report")
    @serialized
    def get_report(run_id: str):
        session = resolve_session(run_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Run not found")
        return report(session)

    @app.get("/api/replays/{run_id}/events")
    @serialized
    def get_replay_events(run_id: str) -> dict[str, Any]:
        session = resolve_session(run_id)
        if session is None:
            raise HTTPException(status_code=404, detail=f"Replay run '{run_id}' not found")
        snap = session.snapshot()
        return {
            "runId": snap.runId,
            "cursor": snap.cursor,
            "currentObservedAt": snap.currentObservedAt,
            "configVersion": snap.configVersion,
            "adaptationEvents": snap.adaptationEvents,
            "configHistory": snap.configHistory,
            "recentDecisions": snap.recentDecisions,
            "evaluations": snap.evaluations,
        }

    @app.post("/api/adaptations/{adaptation_id}/evaluate", response_model=ReppoEvaluationRecord)
    @serialized
    def evaluate_adaptation(adaptation_id: str) -> ReppoEvaluationRecord:
        stored_event = storage_repo.get_adaptation_event(adaptation_id)
        resolved_session = resolve_session(stored_event.runId) if stored_event else None
        candidate_sessions = list(sessions.values())
        if resolved_session and resolved_session not in candidate_sessions:
            candidate_sessions.insert(0, resolved_session)
        for session in candidate_sessions:
            for ev in session.adaptation_events:
                if ev.id == adaptation_id:
                    if serv.is_configured() and (ev.servProposal is None or ev.servProposal.provenance != "SERV_GENERATED"):
                        proposal = serv.generate_proposal(
                            observed_at=ev.detectedAt,
                            dataset_name=session.dataset.name,
                            old_weights=ev.oldWeights,
                            candidate_weights=ev.proposedWeights or ev.oldWeights,
                            momentum_score=ev.momentumTrailingScore,
                            reversal_score=ev.reversalTrailingScore,
                            matured_count=ev.maturedSampleCount,
                            allowed_evidence_ids=ev.evidenceIds,
                        )
                        ev.servProposal = proposal
                        if proposal.provenance == "SERV_GENERATED" and proposal.schemaValid:
                            ev.rationale = proposal.hypothesis
                            if "SERV GENERATED" not in ev.provenanceBadges:
                                ev.provenanceBadges.append("SERV GENERATED")
                    rec = session.submit_adaptation_to_reppo(adaptation_id)
                    storage_repo.save_evaluation(rec)
                    storage_repo.save_snapshot(session.snapshot())
                    return rec

        raise HTTPException(status_code=404, detail=f"Adaptation event '{adaptation_id}' not found")

    @app.get("/api/evaluations/{eval_id}", response_model=ReppoEvaluationRecord)
    @serialized
    def get_evaluation(eval_id: str) -> ReppoEvaluationRecord:
        # Check in-memory active sessions (replay and live) first
        all_sessions = list(sessions.values()) + list(live_supervisors.sessions.values())
        for session in all_sessions:
            if eval_id in session.evaluations:
                rec = session.evaluations[eval_id]
                updated = reppo.poll_evaluation(rec)
                session.evaluations[eval_id] = updated
                storage_repo.save_evaluation(updated)
                for event in session.adaptation_events:
                    if event.evaluationId == eval_id:
                        event.reppoStatus = updated.status
                        event.provenanceBadges = [b for b in event.provenanceBadges if b != 'PENDING REVIEW']
                        if updated.status == 'PENDING':
                            event.provenanceBadges.append('PENDING REVIEW')
                        elif updated.status == 'SETTLED' and 'REPPO REVIEWED' not in event.provenanceBadges:
                            event.provenanceBadges.append('REPPO REVIEWED')
                storage_repo.save_snapshot(session.snapshot())
                return updated

        stored = storage_repo.get_evaluation(eval_id)
        if stored is not None:
            updated = reppo.poll_evaluation(stored)
            storage_repo.save_evaluation(updated)
            return updated

        raise HTTPException(status_code=404, detail=f"Evaluation '{eval_id}' not found")

    @app.get("/api/agent/manifest")
    def get_agent_manifest() -> dict[str, Any]:
        """OpenServ-compatible agent capability manifest for Supervisor-as-a-Service."""
        return {
            "name": "Aptura Adaptive Strategy Supervisor",
            "version": "1.0.0",
            "hackathon": "OpenServ Hackathon 02 (Reppo Track)",
            "description": (
                "Auditable 3-gate risk governor for algorithmic & AI trading agents. "
                "Combines OpenServ SERV Reasoning, zero-look-ahead 24-bar deterministic backtest validation, "
                "and Reppo Eval Router panel review before any strategy configuration change can ship."
            ),
            "integrations": {
                "servReasoning": serv.is_configured(),
                "servModel": serv.model or None,
                "reppoEvalRouter": reppo.is_configured(),
            },
            "capabilities": [
                {
                    "id": "supervise_strategy_adaptation",
                    "method": "POST",
                    "endpoint": "/api/v1/supervise",
                    "description": "Evaluate a proposed or SERV-synthesized strategy weight update through causal math gates and Reppo panel audit.",
                    "returns": ["SHIP", "REVIEW", "BLOCK"],
                },
                {
                    "id": "audit_replay_run",
                    "method": "GET",
                    "endpoint": "/api/replays/{runId}/audit",
                    "description": "Export full immutable causal signal, shadow outcome, decision, review transition, and activation trail.",
                },
                {
                    "id": "live_market_supervision",
                    "method": "GET",
                    "endpoint": "/api/live/{marketId}",
                    "description": "Observe live Solana pool trades and persistent adaptive paper supervision state.",
                },
            ],
            "unitEconomics": {
                "localDeterministicGateUsd": 0.0,
                "reppoTextEvalCredits": 440,
                "reppoTextEvalUsd": 0.22,
            },
        }

    @app.post("/api/v1/supervise", response_model=SuperviseResponse)
    @serialized
    def supervise_agent_adaptation(req: SuperviseRequest) -> SuperviseResponse:
        """Supervisor-as-a-Service endpoint: Gate 1 (SERV) -> Gate 2 (Causal Math) -> Gate 3 (Reppo)."""
        try:
            meta, candles = data_catalog.get_dataset(req.datasetId)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"Unknown dataset '{req.datasetId}'") from exc

        run_id = "sup_" + uuid.uuid4().hex[:12]
        session = ReplaySession(
            run_id=run_id,
            dataset=meta,
            candles=candles,
            seed=42,
            serv_analyst=SERVAnalyst(api_key=""),
            reppo_client=reppo,
        )
        if req.cursorIndex is not None:
            target_idx = min(req.cursorIndex, len(candles) - 1)
            session.advance(target_idx)
        else:
            # Advance to first drift event or bar 65 so callers immediately get rich matured telemetry
            session.advance(min(50, len(candles) - 1))
            while session.cursor < len(candles) - 1 and not session.adaptation_events:
                session.advance(1)

        selection = [o for o in session.tracker.matured_outcomes if o.maturedAtIndex < session.cursor - 23]
        if not selection:
            selection = list(session.tracker.matured_outcomes)

        scores = {"momentum": 0.0, "reversal": 0.0}
        for outcome in selection:
            scores[outcome.strategyId] = 0.3 * outcome.netReturnPct + 0.7 * scores[outcome.strategyId]
        mom_score = round(scores["momentum"], 4)
        rev_score = round(scores["reversal"], 4)

        cur_mom = float(req.currentWeights.get("momentum", 0.6))
        cur_rev = float(req.currentWeights.get("reversal", 0.4))
        old_w = [round(cur_mom, 4), round(cur_rev, 4)]

        divergence = rev_score - mom_score
        shift = max(-0.25, min(0.25, divergence * 0.22))
        fallback_mom, fallback_rev = normalize_and_bound_weights(old_w[0] - shift, old_w[1] + shift)
        recent_outcomes = selection[-6:]
        evidence_ids = [
            f"ev_mat_{o.strategyId}_{o.issuedAtIndex}_to_{o.maturedAtIndex}:{o.netReturnPct:+.2f}%"
            for o in recent_outcomes
        ] or [f"ev_candle_{session.cursor}:ts={session.snapshot().currentObservedAt}"]

        extra_ctx: dict[str, Any] = {"callingAgent": req.agentName}
        if req.rationale:
            extra_ctx["callerRationale"] = req.rationale
        if req.proposedWeights:
            extra_ctx["callerProposedWeights"] = req.proposedWeights

        observed_at = session.snapshot().currentObservedAt
        serv_proposal = serv.generate_proposal(
            observed_at=observed_at,
            dataset_name=meta.name,
            old_weights=old_w,
            candidate_weights=[fallback_mom, fallback_rev],
            momentum_score=mom_score,
            reversal_score=rev_score,
            matured_count=len(selection),
            allowed_evidence_ids=evidence_ids,
            extra_context=extra_ctx,
        )

        if req.proposedWeights is not None:
            cand_w = [
                round(float(req.proposedWeights.get("momentum", 0.5)), 4),
                round(float(req.proposedWeights.get("reversal", 0.5)), 4),
            ]
        else:
            cand_w = [
                round(float(serv_proposal.suggestedWeights["momentum"]), 4),
                round(float(serv_proposal.suggestedWeights["reversal"]), 4),
            ]

        gate = session.adaptation_engine.validate_proposal(
            current_idx=session.cursor,
            old_weights=old_w,
            proposed_weights=cand_w,
            matured_outcomes=selection,
            evidence_ids=evidence_ids,
            cooldown_respected=True,
            broker_validation=lambda b, c: validate_weights(session, b, c),
        )

        reppo_record: ReppoEvaluationRecord | None = None
        if req.runReppoReview:
            ev = AdaptationEvent(
                id=f"adapt_{run_id}_{session.cursor}",
                runId=run_id,
                detectedAt=observed_at,
                candleIndex=session.cursor,
                mechanism="REVIEWED_PROPOSAL",
                status="PROPOSED",
                fromVersion="v1.0.0",
                proposedVersion="v1.1.0",
                oldWeights=old_w,
                proposedWeights=cand_w,
                triggerMetric=f"EWMA divergence {divergence:+.2f}% (Mom {mom_score:+.2f}% vs Rev {rev_score:+.2f}%)",
                maturedSampleCount=len(selection),
                momentumTrailingScore=mom_score,
                reversalTrailingScore=rev_score,
                evidenceIds=evidence_ids,
                rationale=req.rationale or serv_proposal.hypothesis,
                servProposal=serv_proposal,
                validationResult=gate,
            )
            reppo_record = reppo.submit_evaluation(ev, meta.name)
            storage_repo.save_evaluation(reppo_record)

        if not gate.passed:
            verdict = "BLOCK"
            summary = f"BLOCKED by deterministic math gate: {gate.summary}"
        elif reppo_record and reppo_record.status == "SETTLED" and (reppo_record.route == "block" or reppo_record.decision == "reject"):
            verdict = "BLOCK"
            summary = f"BLOCKED by Reppo panel ({reppo_record.score}/100): {reppo_record.critique}"
        elif reppo_record and reppo_record.status == "PENDING":
            verdict = "REVIEW"
            summary = f"Deterministic gate passed ({gate.pastSegmentDeltaPct:+.3f}%); awaiting Reppo eval {reppo_record.evalId}."
        elif reppo_record and reppo_record.route == "review":
            verdict = "REVIEW"
            summary = f"Deterministic gate passed; Reppo routed to human review ({reppo_record.score}/100)."
        elif serv_proposal.provenance != "SERV_GENERATED" or not serv_proposal.schemaValid:
            verdict = "REVIEW"
            summary = f"Deterministic gate passed ({gate.pastSegmentDeltaPct:+.3f}%); SERV Reasoning unavailable or schema-invalid."
        else:
            verdict = "SHIP"
            summary = f"SHIP: SERV Reasoning + 24-bar causal math gate ({gate.pastSegmentDeltaPct:+.3f}%) passed."

        return SuperviseResponse(
            requestId=run_id,
            agentName=req.agentName,
            datasetId=meta.id,
            datasetName=meta.name,
            observedAtUtc=observed_at,
            cursorIndex=session.cursor,
            decision=verdict,
            currentWeights={"momentum": old_w[0], "reversal": old_w[1]},
            proposedWeights={"momentum": cand_w[0], "reversal": cand_w[1]},
            servProposal=serv_proposal,
            deterministicGate=gate,
            reppoEvaluation=reppo_record,
            unitEconomics={
                "localMathGateUsd": 0.0,
                "servReasoningModel": serv_proposal.modelUsed,
                "servLatencyMs": serv_proposal.latencyMs,
                "reppoCreditsCharged": reppo_record.creditsCharged if reppo_record else 0,
                "reppoEstimatedUsd": 0.22 if req.runReppoReview else 0.0,
            },
            summary=summary,
        )

    @app.get("/api/download/aptura.zip")
    @serialized
    def download_project_zip() -> FileResponse:
        zip_path = Path(__file__).resolve().parents[3] / "aptura.zip"
        if not zip_path.exists():
            raise HTTPException(status_code=404, detail="Project archive not found")
        return FileResponse(
            path=str(zip_path),
            media_type="application/zip",
            filename="aptura.zip",
        )

    return app


app = create_app()
