"""Deterministic, zero-look-ahead ReplayEngine and next-bar PaperBroker."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
from copy import deepcopy
from typing import Any, Optional

from app.domain.models import (
    AdaptationEvent,
    Candle,
    ConfigVersionRecord,
    DatasetMetadata,
    EquityPoint,
    PaperOrder,
    ReplaySnapshot,
    ReppoEvaluationRecord,
    RiskGuardianAssessment,
    RiskProfile,
    RunStatus,
    Signal,
    SupervisorDecision,
    TrackId,
    TrackMetrics,
)
from app.evaluation.clients import ReppoClient, SERVAnalyst
from app.strategies.scouts import MomentumScout, ReversalScout
from app.supervisor.engine import (
    AdaptationEngine,
    AdaptiveSupervisor,
    FeedbackTracker,
    RiskGuardian,
)


@dataclass
class PendingOrderIntent:
    decision_candle_index: int
    decision_observed_at: str
    side: str  # "BUY" | "SELL"
    size_fraction: float
    config_version: str
    reason: str


class PaperBroker:
    """Deterministic next-bar paper broker with zero leverage and non-negative cash."""

    def __init__(
        self,
        track: TrackId,
        label: str,
        initial_capital_usd: float,
        fee_bps: float,
        slippage_bps: float,
    ) -> None:
        self.track = track
        self.label = label
        self.initial_capital_usd = initial_capital_usd
        self.cash_usd = initial_capital_usd
        self.position_qty = 0.0
        self.avg_entry_price = 0.0
        self.entry_fee_usd = 0.0
        self.fee_bps = fee_bps
        self.slippage_bps = slippage_bps
        self.pending_intent: Optional[PendingOrderIntent] = None
        self.orders: list[PaperOrder] = []
        self.peak_equity = initial_capital_usd
        self.max_drawdown_pct = 0.0
        self.current_drawdown_pct = 0.0
        self.equity_history: list[float] = []
        self.exposure_history: list[float] = []
        self.total_fees_usd = 0.0
        self.total_slippage_usd = 0.0
        self.win_count = 0
        self.loss_count = 0

    def has_open_position(self) -> bool:
        return self.position_qty > 1e-12

    def current_equity(self, mark_price: float) -> float:
        return round(self.cash_usd + self.position_qty * mark_price, 4)

    def current_exposure_pct(self, mark_price: float) -> float:
        eq = self.current_equity(mark_price)
        if eq <= 0:
            return 0.0
        pos_val = self.position_qty * mark_price
        return round(min(100.0, max(0.0, (pos_val / eq) * 100.0)), 4)

    def queue_intent(
        self,
        decision_candle_index: int,
        decision_observed_at: str,
        side: str,
        size_fraction: float,
        config_version: str,
        reason: str,
    ) -> None:
        """Queue an order to execute on the NEXT candle's open."""
        if getattr(self, "preserve_pending", False) and self.pending_intent and self.pending_intent.side == side:
            return
        if side == "BUY" and not self.has_open_position():
            self.pending_intent = PendingOrderIntent(
                decision_candle_index=decision_candle_index,
                decision_observed_at=decision_observed_at,
                side="BUY",
                size_fraction=max(0.0, min(0.95, size_fraction)),
                config_version=config_version,
                reason=reason,
            )
        elif side == "SELL" and self.has_open_position():
            self.pending_intent = PendingOrderIntent(
                decision_candle_index=decision_candle_index,
                decision_observed_at=decision_observed_at,
                side="SELL",
                size_fraction=1.0,
                config_version=config_version,
                reason=reason,
            )

    def execute_pending_at_open(self, run_id: str, fill_candle: Candle) -> Optional[PaperOrder]:
        """Fill any queued intent from the prior candle at the current candle's open price."""
        if self.pending_intent is None:
            return None
        intent = self.pending_intent
        self.pending_intent = None

        # Strictly require fill candle to be after decision candle
        if fill_candle.index <= intent.decision_candle_index:
            return None

        ref_price = fill_candle.open
        slip_rate = self.slippage_bps / 10000.0
        fee_rate = self.fee_bps / 10000.0

        if intent.side == "BUY" and not self.has_open_position():
            alloc_usd = min(self.cash_usd, self.cash_usd * intent.size_fraction)
            if alloc_usd <= 1.0:
                return None
            fill_price = ref_price * (1.0 + slip_rate)
            # Ensure cash_usd - notional - fee >= 0 (no negative cash, no leverage)
            notional_usd = alloc_usd / (1.0 + fee_rate)
            fee_usd = notional_usd * fee_rate
            slippage_usd = notional_usd * slip_rate
            qty = notional_usd / fill_price

            self.cash_usd = max(0.0, round(self.cash_usd - notional_usd - fee_usd, 6))
            self.position_qty = qty
            self.avg_entry_price = fill_price
            self.entry_fee_usd = fee_usd
            self.total_fees_usd += fee_usd
            self.total_slippage_usd += slippage_usd

            order = PaperOrder(
                id=f"ord_{self.track}_{run_id}_{fill_candle.index}",
                runId=run_id,
                track=self.track,
                decisionObservedAt=intent.decision_observed_at,
                filledAt=datetime.fromtimestamp(fill_candle.timestamp, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                decisionCandleIndex=intent.decision_candle_index,
                fillCandleIndex=fill_candle.index,
                side="BUY",
                referencePrice=round(ref_price, 12),
                fillPrice=round(fill_price, 12),
                quantity=round(qty, 6),
                notionalUsd=round(notional_usd, 4),
                feeUsd=round(fee_usd, 4),
                slippageUsd=round(slippage_usd, 4),
                realizedPnlUsd=0.0,
                configVersion=intent.config_version,
                reason=intent.reason,
            )
            self.orders.append(order)
            return order

        if intent.side == "SELL" and self.has_open_position():
            qty = self.position_qty
            fill_price = ref_price * (1.0 - slip_rate)
            gross_proceeds = qty * fill_price
            fee_usd = gross_proceeds * fee_rate
            slippage_usd = (qty * ref_price) * slip_rate
            net_proceeds = max(0.0, gross_proceeds - fee_usd)
            cost_basis = qty * self.avg_entry_price
            realized_pnl = net_proceeds - cost_basis - self.entry_fee_usd

            self.cash_usd = round(self.cash_usd + net_proceeds, 6)
            self.position_qty = 0.0
            self.avg_entry_price = 0.0
            self.total_fees_usd += fee_usd
            self.total_slippage_usd += slippage_usd
            if realized_pnl > 0:
                self.win_count += 1
            else:
                self.loss_count += 1

            order = PaperOrder(
                id=f"ord_{self.track}_{run_id}_{fill_candle.index}",
                runId=run_id,
                track=self.track,
                decisionObservedAt=intent.decision_observed_at,
                filledAt=datetime.fromtimestamp(fill_candle.timestamp, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                decisionCandleIndex=intent.decision_candle_index,
                fillCandleIndex=fill_candle.index,
                side="SELL",
                referencePrice=round(ref_price, 12),
                fillPrice=round(fill_price, 12),
                quantity=round(qty, 6),
                notionalUsd=round(gross_proceeds, 4),
                feeUsd=round(fee_usd, 4),
                slippageUsd=round(slippage_usd, 4),
                realizedPnlUsd=round(realized_pnl, 4),
                configVersion=intent.config_version,
                reason=intent.reason,
            )
            self.orders.append(order)
            return order

        return None

    def mark_to_market(self, close_price: float) -> tuple[float, float, float]:
        eq = self.current_equity(close_price)
        exp = self.current_exposure_pct(close_price)
        if eq > self.peak_equity:
            self.peak_equity = eq
        dd = ((self.peak_equity - eq) / self.peak_equity) * 100.0 if self.peak_equity > 0 else 0.0
        self.current_drawdown_pct = round(dd, 4)
        if dd > self.max_drawdown_pct:
            self.max_drawdown_pct = round(dd, 4)
        self.equity_history.append(eq)
        self.exposure_history.append(exp)
        return eq, self.current_drawdown_pct, exp

    def compute_metrics(self) -> TrackMetrics:
        final_eq = self.equity_history[-1] if self.equity_history else self.initial_capital_usd
        net_ret = ((final_eq / self.initial_capital_usd) - 1.0) * 100.0 if self.initial_capital_usd > 0 else 0.0
        avg_exp = sum(self.exposure_history) / len(self.exposure_history) if self.exposure_history else 0.0

        # Compute step returns for Sharpe-like ratio
        if len(self.equity_history) >= 3:
            rets = [
                (self.equity_history[i] / self.equity_history[i - 1]) - 1.0
                for i in range(1, len(self.equity_history))
                if self.equity_history[i - 1] > 0
            ]
            mean_r = sum(rets) / len(rets) if rets else 0.0
            var_r = sum((r - mean_r) ** 2 for r in rets) / len(rets) if rets else 0.0
            std_r = math.sqrt(var_r)
            sharpe = (mean_r / std_r) * math.sqrt(getattr(self, "annualization_factor", 24 * 365)) if std_r > 1e-9 else 0.0
        else:
            sharpe = 0.0

        return TrackMetrics(
            track=self.track,
            label=self.label,
            initialCapitalUsd=round(self.initial_capital_usd, 2),
            finalEquityUsd=round(final_eq, 2),
            netReturnPct=round(net_ret, 3),
            maxDrawdownPct=round(self.max_drawdown_pct, 3),
            tradeCount=len(self.orders),
            totalFeesUsd=round(self.total_fees_usd, 3),
            totalSlippageUsd=round(self.total_slippage_usd, 3),
            avgExposurePct=round(avg_exp, 2),
            sharpeLikeRatio=round(sharpe, 2),
            winCount=self.win_count,
            lossCount=self.loss_count,
        )


class ReplaySession:
    """Authoritative causal replay state machine for a single run."""

    POSITION_SIZING = {
        "conservative": {"allow": 0.60, "caution": 0.30},
        "balanced": {"allow": 0.75, "caution": 0.40},
        "aggressive": {"allow": 0.90, "caution": 0.50},
    }

    def __init__(
        self,
        run_id: str,
        dataset: DatasetMetadata,
        candles: list[Candle],
        seed: int = 42,
        initial_capital_usd: float = 1000.0,
        risk_profile: RiskProfile = "conservative",
        fee_bps: float = 20.0,
        slippage_bps: float = 15.0,
        warmup_bars: int = 20,
        evaluation_horizon_bars: int = 4,
        serv_analyst: Optional[SERVAnalyst] = None,
        reppo_client: Optional[ReppoClient] = None,
        activation_commands: Optional[list[dict]] = None,
    ) -> None:
        self.run_id = run_id
        self.dataset = dataset
        self._all_candles = candles
        self.seed = seed
        self.initial_capital_usd = initial_capital_usd
        self.risk_profile = risk_profile
        self.fee_bps = fee_bps
        self.slippage_bps = slippage_bps
        self.warmup_bars = warmup_bars
        self.evaluation_horizon_bars = evaluation_horizon_bars
        self.serv_analyst = serv_analyst or SERVAnalyst()
        self.reppo_client = reppo_client or ReppoClient()

        if not hasattr(self, "is_live"):
            self.is_live = False
        self.activation_commands = activation_commands or []
        self.reset()

    def reset(self) -> None:
        self.cursor: int = -1
        self.status: RunStatus = "READY"
        self.config_version: str = "v1.0.0"
        self.version_counter: int = 1
        # Start with Momentum-tilted weights (60/40) as depicted in product.md ("60% -> 35% / 40% -> 65%")
        self.active_weights: dict[str, float] = {"momentum": 0.60, "reversal": 0.40}

        self.config_history: list[ConfigVersionRecord] = [
            ConfigVersionRecord(
                version="v1.0.0",
                runId=self.run_id,
                createdAt=self._all_candles[0].observedAt,
                candleIndex=0,
                weights={"momentum": 0.60, "reversal": 0.40},
                mechanism="INITIAL",
                sourceEventId=None,
                rationale="Initial baseline strategy weights (60% Momentum Scout / 40% Reversal Scout).",
            )
        ]

        self.brokers: dict[TrackId, PaperBroker] = {
            "adaptive": PaperBroker("adaptive", "Aptura Adaptive Supervisor", self.initial_capital_usd, self.fee_bps, self.slippage_bps),
            "fixed_50_50": PaperBroker("fixed_50_50", "Fixed 50/50 Baseline", self.initial_capital_usd, self.fee_bps, self.slippage_bps),
            "momentum_only": PaperBroker("momentum_only", "Momentum-Only Baseline", self.initial_capital_usd, self.fee_bps, self.slippage_bps),
            "cash": PaperBroker("cash", "No-Trade / Cash Benchmark", self.initial_capital_usd, self.fee_bps, self.slippage_bps),
        }

        self.tracker = self.make_tracker(
            horizon_bars=self.evaluation_horizon_bars,
            fee_bps=self.fee_bps,
            slippage_bps=self.slippage_bps,
        )
        self.adaptation_engine = AdaptationEngine(
            min_matured_samples=6,
            cooldown_bars=18,
            drift_threshold_pct=0.42,
        )

        self.signals_by_bar: list[dict[str, Signal]] = []
        self.decisions: list[SupervisorDecision] = []
        self.guardian_assessments: list[RiskGuardianAssessment] = []
        self.adaptation_events: list[AdaptationEvent] = []
        self.intervention_branches = []
        self.equity_curve: list[EquityPoint] = []
        self.evaluations: dict[str, ReppoEvaluationRecord] = {}

        # Advance 1 bar so initial state at cursor=0 is visible
        self._step_one_bar()
        self.status = "READY"

    def strategy_window(self, visible):
        return visible

    def make_tracker(self, **kwargs):
        return FeedbackTracker(**kwargs)

    def execute_broker(self, broker, index):
        candle = self._all_candles[index]
        if index and candle.timestamp - self._all_candles[index - 1].timestamp != 3600:
            broker.pending_intent = None
        return broker.execute_pending_at_open(self.run_id, candle)

    def assess_risk(self, visible, broker):
        return RiskGuardian.assess(visible, broker.current_exposure_pct(visible[-1].close), self.risk_profile)

    def advance(self, steps: int = 1) -> ReplaySnapshot:
        for _ in range(steps):
            if self.cursor >= len(self._all_candles) - 1:
                self.status = "FINISHED"
                break
            self._step_one_bar()
        if self.cursor >= len(self._all_candles) - 1:
            self.status = "FINISHED"
        elif self.status == "READY" and self.cursor > 0:
            self.status = "RUNNING"
        return self.snapshot()

    def _step_one_bar(self) -> None:
        if self.cursor >= len(self._all_candles) - 1:
            self.status = "FINISHED"
            return

        self.cursor += 1
        # Crucial invariant: ONLY slice closed candles up to self.cursor! Never touch self._all_candles[self.cursor + 1:]
        visible_candles = self._all_candles[: self.cursor + 1]
        current_candle = visible_candles[-1]

        # 1. Execute any pending paper orders queued at cursor - 1 at current_candle.open
        for broker in self.brokers.values():
            self.execute_broker(broker, self.cursor)

        # 2. Mature eligible shadow signals whose evaluation horizon has completed at or before current_candle
        self.tracker.mature_eligible_signals(visible_candles)

        # 3. Compute deterministic strategy signals on visible_candles (closed bars <= t)
        mom_sig = MomentumScout.evaluate(self.strategy_window(visible_candles), warmup_bars=self.warmup_bars, run_id=self.run_id)
        rev_sig = ReversalScout.evaluate(self.strategy_window(visible_candles), warmup_bars=self.warmup_bars, run_id=self.run_id)
        self.signals_by_bar.append({"momentum": mom_sig, "reversal": rev_sig})

        # Record shadow signals for future causal evaluation after horizon elapses
        self.tracker.record_shadow_signal(mom_sig)
        self.tracker.record_shadow_signal(rev_sig)

        # 4. Check for strategy drift and run deterministic adaptation gate
        from app.replay.comparisons import validate_weights
        previous_accepted_bar = self.adaptation_engine.last_accepted_bar
        scheduled_here = any(c["candleIndex"] == self.cursor for c in self.activation_commands)
        adapt_event = None if scheduled_here else self.adaptation_engine.check_and_propose(
            run_id=self.run_id,
            dataset_name=self.dataset.name,
            current_candle=current_candle,
            active_version=self.config_version,
            version_counter=self.version_counter,
            active_weights=self.active_weights,
            tracker=self.tracker,
            serv_analyst=self.serv_analyst,
            broker_validation=lambda old, new: validate_weights(self, old, new),
        )
        scheduled = next((command for command in self.activation_commands
                          if command['candleIndex'] == self.cursor), None)
        if scheduled:
            adapt_event = AdaptationEvent.model_validate(scheduled['event'])
            adapt_event.activatedAt = current_candle.observedAt
            self.adaptation_engine.last_accepted_bar = self.cursor
        if adapt_event is not None:
            if self.is_live:
                adapt_event.provenanceBadges = [b for b in adapt_event.provenanceBadges if b != "HISTORICAL"] + ["LIVE OBSERVATIONS"]
                if self.interruptions[self.cursor] or (self.cursor and current_candle.timestamp - visible_candles[-2].timestamp > 90):
                    adapt_event.status = "REJECTED"
                    adapt_event.activatedAt = None
                    adapt_event.rejectionReason = "Feed gap: change cancelled; fresh evidence required."
                    self.adaptation_engine.last_accepted_bar = previous_accepted_bar
            self.adaptation_events.append(adapt_event)
            if adapt_event.status == "ACCEPTED" and adapt_event.proposedWeights and adapt_event.proposedVersion:
                self.intervention_branches.append({"event": adapt_event.model_copy(deep=True),
                    "old": deepcopy(self.brokers["adaptive"]), "new": deepcopy(self.brokers["adaptive"])})
                self.config_version = adapt_event.proposedVersion
                self.version_counter += 1
                self.active_weights = {
                    "momentum": adapt_event.proposedWeights[0],
                    "reversal": adapt_event.proposedWeights[1],
                }
                self.config_history.append(
                    ConfigVersionRecord(
                        version=self.config_version,
                        runId=self.run_id,
                        createdAt=current_candle.observedAt,
                        candleIndex=current_candle.index,
                        weights=dict(self.active_weights),
                        mechanism=adapt_event.mechanism,
                        sourceEventId=adapt_event.id,
                        rationale=adapt_event.rationale,
                    )
                )

        # 5. Run RiskGuardian assessment at current_candle
        adaptive_broker = self.brokers["adaptive"]
        guardian = self.assess_risk(visible_candles, adaptive_broker)
        self.guardian_assessments.append(guardian)

        # 6. Produce SupervisorDecision for the adaptive track
        decision = AdaptiveSupervisor.decide(
            run_id=self.run_id,
            current_candle=current_candle,
            config_version=self.config_version,
            weights=self.active_weights,
            mom_signal=mom_sig,
            rev_signal=rev_sig,
            guardian=guardian,
            has_open_position=adaptive_broker.has_open_position(),
        )
        self.decisions.append(decision)
        if self.is_live and decision.action not in ("BUY", "EXIT"):
            adaptive_broker.pending_intent = None

        # Queue next-bar order intents for all tracks under identical friction assumptions
        sizing_cfg = self.POSITION_SIZING.get(self.risk_profile, self.POSITION_SIZING["conservative"])
        size_frac = sizing_cfg["allow"] if guardian.status == "ALLOW" else sizing_cfg["caution"]

        # Track 1: Adaptive Supervisor
        if decision.action == "BUY":
            adaptive_broker.queue_intent(
                decision_candle_index=current_candle.index,
                decision_observed_at=current_candle.observedAt,
                side="BUY",
                size_fraction=size_frac,
                config_version=self.config_version,
                reason=decision.reason,
            )
        elif decision.action == "EXIT":
            adaptive_broker.queue_intent(
                decision_candle_index=current_candle.index,
                decision_observed_at=current_candle.observedAt,
                side="SELL",
                size_fraction=1.0,
                config_version=self.config_version,
                reason=decision.reason,
            )

        # Frozen comparisons use the exact same decision and risk policy, with
        # each portfolio's own exposure. Only strategy weights differ.
        fixed_broker = self.brokers["fixed_50_50"]
        mom_broker = self.brokers["momentum_only"]
        for broker, weights in ((fixed_broker, {"momentum": .5, "reversal": .5}),
                                (mom_broker, {"momentum": 1.0, "reversal": 0.0})):
            own_guardian = self.assess_risk(visible_candles, broker)
            baseline_decision = AdaptiveSupervisor.decide(self.run_id, current_candle,
                "frozen", weights, mom_sig, rev_sig, own_guardian, broker.has_open_position())
            if self.is_live and baseline_decision.action not in ("BUY", "EXIT"):
                broker.pending_intent = None
            if baseline_decision.action in ("BUY", "EXIT"):
                broker.queue_intent(current_candle.index, current_candle.observedAt,
                    "BUY" if baseline_decision.action == "BUY" else "SELL",
                    sizing_cfg["allow"] if own_guardian.status == "ALLOW" else sizing_cfg["caution"],
                    "frozen", baseline_decision.reason)

        # Track 4: Cash benchmark never trades

        # 7. Mark all 4 tracks to market at current_candle.close
        ad_eq, ad_dd, ad_exp = adaptive_broker.mark_to_market(current_candle.close)
        fx_eq, fx_dd, _ = fixed_broker.mark_to_market(current_candle.close)
        mo_eq, mo_dd, _ = mom_broker.mark_to_market(current_candle.close)
        ca_eq, _, _ = self.brokers["cash"].mark_to_market(current_candle.close)

        self.equity_curve.append(
            EquityPoint(
                candleIndex=current_candle.index,
                observedAt=current_candle.observedAt,
                closePrice=current_candle.close,
                adaptiveEquity=ad_eq,
                fixedEquity=fx_eq,
                momentumOnlyEquity=mo_eq,
                cashEquity=ca_eq,
                adaptiveDrawdownPct=ad_dd,
                fixedDrawdownPct=fx_dd,
                momentumOnlyDrawdownPct=mo_dd,
                adaptiveExposurePct=ad_exp,
                configVersion=self.config_version,
            )
        )

    def submit_adaptation_to_reppo(self, adaptation_id: str) -> ReppoEvaluationRecord:
        target = next((e for e in self.adaptation_events if e.id == adaptation_id), None)
        if target is None:
            raise KeyError(f"Adaptation event '{adaptation_id}' not found in run '{self.run_id}'")
        record = self.reppo_client.submit_evaluation(target, self.dataset.name)
        target.evaluationId = record.evalId
        target.reppoStatus = record.status
        if "PENDING REVIEW" not in target.provenanceBadges and record.status == "PENDING":
            target.provenanceBadges.append("PENDING REVIEW")
        self.evaluations[record.evalId] = record
        return record

    def snapshot(self) -> ReplaySnapshot:
        visible = self._all_candles[: self.cursor + 1]
        latest_sigs = self.signals_by_bar[-1] if self.signals_by_bar else {}
        latest_dec = self.decisions[-1] if self.decisions else None
        latest_guard = self.guardian_assessments[-1] if self.guardian_assessments else None

        all_orders: list[PaperOrder] = []
        for b in self.brokers.values():
            all_orders.extend(b.orders)
        all_orders.sort(key=lambda o: (o.fillCandleIndex, o.track))

        strategy_perf: dict[str, dict[str, Any]] = {}
        for strat_id in ("momentum", "reversal"):
            m_count = self.tracker.matured_counts[strat_id]
            h_count = self.tracker.helpful_counts[strat_id]
            strategy_perf[strat_id] = {
                "strategyId": strat_id,
                "weight": self.active_weights[strat_id],
                "trailingEwmaReturnPct": self.tracker.trailing_ewma[strat_id],
                "maturedSignalsCount": m_count,
                "helpfulSignalsCount": h_count,
                "helpfulRatioPct": round((h_count / m_count) * 100.0, 1) if m_count > 0 else None,
                "statusLabel": "Not enough data" if m_count < 3 else ("Leading" if self.tracker.trailing_ewma[strat_id] >= 0 else "Deteriorating"),
            }

        metrics_comp = {
            track_id: broker.compute_metrics()
            for track_id, broker in self.brokers.items()
        }

        return ReplaySnapshot(
            runId=self.run_id,
            dataset=self.dataset,
            seed=self.seed,
            status=self.status,
            cursor=self.cursor,
            totalCandles=len(self._all_candles),
            currentObservedAt=visible[-1].observedAt if visible else self.dataset.startTimeUtc,
            configVersion=self.config_version,
            activeWeights=dict(self.active_weights),
            initialCapitalUsd=self.initial_capital_usd,
            riskProfile=self.risk_profile,
            feeBps=self.fee_bps,
            slippageBps=self.slippage_bps,
            warmupBars=self.warmup_bars,
            evaluationHorizonBars=self.evaluation_horizon_bars,
            visibleCandles=visible,
            latestSignals=latest_sigs,
            latestDecision=latest_dec,
            latestGuardian=latest_guard,
            strategyPerformance=strategy_perf,
            recentDecisions=self.decisions[-40:],
            adaptationEvents=list(self.adaptation_events),
            configHistory=list(self.config_history),
            paperOrders=all_orders,
            equityCurve=list(self.equity_curve),
            metricsComparison=metrics_comp,
            evaluations=list(self.evaluations.values()),
            maturedOutcomes=self.tracker.matured_outcomes[-30:],
        )
