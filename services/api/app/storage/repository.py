"""SQLite repository persisting all 10 required audit tables for Aptura."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Optional

from app.domain.models import (
    AdaptationEvent,
    Candle,
    DatasetMetadata,
    ReplaySnapshot,
    ReppoEvaluationRecord,
)


DEFAULT_DB_PATH = Path(os.environ.get("APTURA_DB_PATH", str(Path(__file__).resolve().parents[4] / "data" / "aptura.sqlite3")))


class SQLiteRepository:
    """SQLite persistence layer storing replay runs, signals, decisions, orders, adaptations, and evaluations."""

    def __init__(self, db_path: Path = DEFAULT_DB_PATH) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS live_supervisors (
                    market_id TEXT PRIMARY KEY, run_id TEXT UNIQUE NOT NULL, document TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS live_observations (
                    run_id TEXT NOT NULL, sequence INTEGER NOT NULL, source_timestamp INTEGER NOT NULL,
                    document TEXT NOT NULL, PRIMARY KEY(run_id, sequence), UNIQUE(run_id, source_timestamp)
                );
                CREATE TABLE IF NOT EXISTS shadow_outcomes (
                    signal_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, document TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS market_watches (
                    id TEXT PRIMARY KEY, document TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS review_jobs (
                    id TEXT PRIMARY KEY, run_id TEXT NOT NULL, state TEXT NOT NULL,
                    document TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS activation_commands (
                    id TEXT PRIMARY KEY, run_id TEXT NOT NULL, candle_index INTEGER NOT NULL,
                    document TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS review_audit (
                    sequence INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL,
                    recorded_at TEXT DEFAULT CURRENT_TIMESTAMP, document TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS datasets (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    pool_address TEXT NOT NULL,
                    sha256_hash TEXT NOT NULL,
                    is_synthetic INTEGER NOT NULL,
                    metadata_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS candles (
                    dataset_id TEXT NOT NULL,
                    candle_index INTEGER NOT NULL,
                    timestamp INTEGER NOT NULL,
                    observed_at TEXT NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL NOT NULL,
                    PRIMARY KEY (dataset_id, candle_index)
                );

                CREATE TABLE IF NOT EXISTS replay_runs (
                    run_id TEXT PRIMARY KEY,
                    dataset_id TEXT NOT NULL,
                    dataset_hash TEXT NOT NULL,
                    algorithm_version TEXT NOT NULL,
                    seed INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    cursor INTEGER NOT NULL,
                    config_version TEXT NOT NULL,
                    params_json TEXT NOT NULL,
                    snapshot_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS strategy_signals (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    strategy_id TEXT NOT NULL,
                    candle_index INTEGER NOT NULL,
                    observed_at TEXT NOT NULL,
                    action TEXT NOT NULL,
                    strength REAL NOT NULL,
                    signal_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS supervisor_decisions (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    candle_index INTEGER NOT NULL,
                    observed_at TEXT NOT NULL,
                    config_version TEXT NOT NULL,
                    action TEXT NOT NULL,
                    guardian TEXT NOT NULL,
                    decision_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS paper_orders (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    track TEXT NOT NULL,
                    fill_candle_index INTEGER NOT NULL,
                    filled_at TEXT NOT NULL,
                    side TEXT NOT NULL,
                    order_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS equity_snapshots (
                    run_id TEXT NOT NULL,
                    candle_index INTEGER NOT NULL,
                    observed_at TEXT NOT NULL,
                    adaptive_equity REAL NOT NULL,
                    fixed_equity REAL NOT NULL,
                    snapshot_json TEXT NOT NULL,
                    PRIMARY KEY (run_id, candle_index)
                );

                CREATE TABLE IF NOT EXISTS adaptation_events (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    candle_index INTEGER NOT NULL,
                    detected_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    from_version TEXT NOT NULL,
                    proposed_version TEXT,
                    event_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS config_versions (
                    run_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    candle_index INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    version_json TEXT NOT NULL,
                    PRIMARY KEY (run_id, version)
                );

                CREATE TABLE IF NOT EXISTS reppo_evaluations (
                    eval_id TEXT PRIMARY KEY,
                    adaptation_event_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    submitted_at TEXT NOT NULL,
                    settled_at TEXT,
                    record_json TEXT NOT NULL
                );
                """
            )

    def sync_dataset(self, meta: DatasetMetadata, candles: list[Candle]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO datasets (id, name, pool_address, sha256_hash, is_synthetic, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    meta.id,
                    meta.name,
                    meta.poolAddress,
                    meta.sha256Hash,
                    1 if meta.isSynthetic else 0,
                    meta.model_dump_json(),
                ),
            )
            conn.executemany(
                """
                INSERT OR REPLACE INTO candles
                (dataset_id, candle_index, timestamp, observed_at, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        meta.id,
                        c.index,
                        c.timestamp,
                        c.observedAt,
                        c.open,
                        c.high,
                        c.low,
                        c.close,
                        c.volume,
                    )
                    for c in candles
                ],
            )

    def save_snapshot(self, snap: ReplaySnapshot) -> None:
        params = {
            "dataMode": "LIVE_OBSERVATIONS" if snap.dataset.timeframe == "observed-trade" else "HISTORICAL_REPLAY",
            "initialCapitalUsd": snap.initialCapitalUsd,
            "riskProfile": snap.riskProfile,
            "feeBps": snap.feeBps,
            "slippageBps": snap.slippageBps,
            "warmupBars": snap.warmupBars,
            "evaluationHorizonBars": snap.evaluationHorizonBars,
        }
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO replay_runs
                (run_id, dataset_id, dataset_hash, algorithm_version, seed, status, cursor, config_version, params_json, snapshot_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    snap.runId,
                    snap.dataset.id,
                    snap.dataset.sha256Hash,
                    "aptura-live-observations-1.0.0" if snap.dataset.timeframe == "observed-trade" else "aptura-engine-2.0.0",
                    snap.seed,
                    snap.status,
                    snap.cursor,
                    snap.configVersion,
                    json.dumps(params, sort_keys=True),
                    snap.model_dump_json(),
                ),
            )

            for sig in snap.latestSignals.values():
                conn.execute(
                    """
                    INSERT OR REPLACE INTO strategy_signals
                    (id, run_id, strategy_id, candle_index, observed_at, action, strength, signal_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"{snap.runId}_{sig.id}",
                        snap.runId,
                        sig.strategyId,
                        sig.candleIndex,
                        sig.observedAt,
                        sig.action,
                        sig.strength,
                        sig.model_dump_json(),
                    ),
                )

            if snap.latestDecision:
                dec = snap.latestDecision
                conn.execute(
                    """
                    INSERT OR REPLACE INTO supervisor_decisions
                    (id, run_id, candle_index, observed_at, config_version, action, guardian, decision_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        dec.id,
                        snap.runId,
                        dec.candleIndex,
                        dec.observedAt,
                        dec.configVersion,
                        dec.action,
                        dec.guardian,
                        dec.model_dump_json(),
                    ),
                )

            for ord_item in snap.paperOrders:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO paper_orders
                    (id, run_id, track, fill_candle_index, filled_at, side, order_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ord_item.id,
                        snap.runId,
                        ord_item.track,
                        ord_item.fillCandleIndex,
                        ord_item.filledAt,
                        ord_item.side,
                        ord_item.model_dump_json(),
                    ),
                )

            if snap.equityCurve:
                ep = snap.equityCurve[-1]
                conn.execute(
                    """
                    INSERT OR REPLACE INTO equity_snapshots
                    (run_id, candle_index, observed_at, adaptive_equity, fixed_equity, snapshot_json)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        snap.runId,
                        ep.candleIndex,
                        ep.observedAt,
                        ep.adaptiveEquity,
                        ep.fixedEquity,
                        ep.model_dump_json(),
                    ),
                )

            for outcome in snap.maturedOutcomes:
                conn.execute("INSERT OR IGNORE INTO shadow_outcomes VALUES (?, ?, ?)",
                    (f"{snap.runId}_{outcome.signalId}", snap.runId, outcome.model_dump_json()))

            for ev in snap.adaptationEvents:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO adaptation_events
                    (id, run_id, candle_index, detected_at, status, from_version, proposed_version, event_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ev.id,
                        snap.runId,
                        ev.candleIndex,
                        ev.detectedAt,
                        ev.status,
                        ev.fromVersion,
                        ev.proposedVersion,
                        ev.model_dump_json(),
                    ),
                )

            for cv in snap.configHistory:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO config_versions
                    (run_id, version, candle_index, created_at, version_json)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        snap.runId,
                        cv.version,
                        cv.candleIndex,
                        cv.createdAt,
                        cv.model_dump_json(),
                    ),
                )

            for rep in snap.evaluations:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO reppo_evaluations
                    (eval_id, adaptation_event_id, run_id, status, submitted_at, settled_at, record_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        rep.evalId,
                        rep.adaptationEventId,
                        rep.runId,
                        rep.status,
                        rep.submittedAt,
                        rep.settledAt,
                        rep.model_dump_json(),
                    ),
                )

    def save_evaluation(self, record: ReppoEvaluationRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO reppo_evaluations
                (eval_id, adaptation_event_id, run_id, status, submitted_at, settled_at, record_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.evalId,
                    record.adaptationEventId,
                    record.runId,
                    record.status,
                    record.submittedAt,
                    record.settledAt,
                    record.model_dump_json(),
                ),
            )

    def get_evaluation(self, eval_id: str) -> Optional[ReppoEvaluationRecord]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT record_json FROM reppo_evaluations WHERE eval_id = ?",
                (eval_id,),
            ).fetchone()
            if not row:
                return None
            return ReppoEvaluationRecord.model_validate_json(row["record_json"])

    def get_adaptation_event(self, adaptation_id: str) -> Optional[AdaptationEvent]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT event_json FROM adaptation_events WHERE id = ?",
                (adaptation_id,),
            ).fetchone()
            if not row:
                return None
            return AdaptationEvent.model_validate_json(row["event_json"])

    def get_snapshot(self, run_id: str) -> Optional[ReplaySnapshot]:
        with self._connect() as conn:
            row = conn.execute("SELECT snapshot_json FROM replay_runs WHERE run_id = ?", (run_id,)).fetchone()
            return ReplaySnapshot.model_validate_json(row["snapshot_json"]) if row else None

    def save_job(self, job):
        document = json.dumps(job, sort_keys=True)
        with self._connect() as conn:
            conn.execute("INSERT INTO review_jobs VALUES (?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET state=excluded.state, document=excluded.document",
                         (job['id'], job['runId'], job['state'], document))
            conn.execute("INSERT INTO review_audit(job_id, document) VALUES (?, ?)", (job['id'], document))

    def list_jobs(self, run_id=None):
        with self._connect() as conn:
            rows = conn.execute("SELECT document FROM review_jobs" + (" WHERE run_id=?" if run_id else ""),
                                (run_id,) if run_id else ()).fetchall()
        return [json.loads(row[0]) for row in rows]

    def save_activation(self, command):
        with self._connect() as conn:
            conn.execute("INSERT OR IGNORE INTO activation_commands VALUES (?, ?, ?, ?)",
                         (command['id'], command['runId'], command['candleIndex'], json.dumps(command)))

    def list_activations(self, run_id):
        with self._connect() as conn:
            rows = conn.execute("SELECT document FROM activation_commands WHERE run_id=? ORDER BY candle_index", (run_id,)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def audit_trail(self, run_id):
        with self._connect() as conn:
            outcomes = [json.loads(r[0]) for r in conn.execute("SELECT document FROM shadow_outcomes WHERE run_id=?", (run_id,))]
            signals = [json.loads(r[0]) for r in conn.execute("SELECT signal_json FROM strategy_signals WHERE run_id=? ORDER BY candle_index", (run_id,))]
            decisions = [json.loads(r[0]) for r in conn.execute("SELECT decision_json FROM supervisor_decisions WHERE run_id=? ORDER BY candle_index", (run_id,))]
            reviews = [json.loads(r[0]) for r in conn.execute("SELECT a.document FROM review_audit a JOIN review_jobs j ON j.id=a.job_id WHERE j.run_id=? ORDER BY a.sequence", (run_id,))]
        return {'signals': signals, 'decisions': decisions, 'maturedOutcomes': outcomes, 'reviewTransitions': reviews,
                'activationCommands': self.list_activations(run_id), 'liveObservations': self.live_observations(run_id)}

    def save_watch(self, watch):
        with self._connect() as conn:
            conn.execute("INSERT INTO market_watches VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET document=excluded.document",
                         (watch['id'], json.dumps(watch)))

    def list_watches(self):
        with self._connect() as conn:
            return [json.loads(row[0]) for row in conn.execute("SELECT document FROM market_watches")]

    def restore_outcomes(self, run_id, outcomes):
        with self._connect() as conn:
            # Repair pre-v2 keys while preserving the original run's outcomes.
            for outcome in outcomes:
                conn.execute("DELETE FROM shadow_outcomes WHERE signal_id=? AND run_id=?", (outcome.signalId, run_id))
                conn.execute("INSERT OR IGNORE INTO shadow_outcomes VALUES (?, ?, ?)",
                    (f"{run_id}_{outcome.signalId}", run_id, outcome.model_dump_json()))

    def list_live_supervisors(self):
        with self._connect() as conn:
            return [json.loads(row[0]) for row in conn.execute("SELECT document FROM live_supervisors")]

    def save_live_supervisor(self, state):
        with self._connect() as conn:
            conn.execute("INSERT INTO live_supervisors VALUES (?, ?, ?) ON CONFLICT(market_id) DO UPDATE SET document=excluded.document",
                         (state['marketId'], state['runId'], json.dumps(state)))

    def add_live_observation(self, run_id, observation):
        with self._connect() as conn:
            conn.execute("INSERT INTO live_observations VALUES (?, ?, ?, ?)",
                         (run_id, observation['sequence'], observation['sourceTimestamp'], json.dumps(observation)))

    def live_observations(self, run_id):
        with self._connect() as conn:
            return [json.loads(row[0]) for row in conn.execute("SELECT document FROM live_observations WHERE run_id=? ORDER BY sequence", (run_id,))]
