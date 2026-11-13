"""RiskGuardian, FeedbackTracker, AdaptationEngine, and AdaptiveSupervisor."""

from __future__ import annotations

import math
from typing import Optional

from app.domain.models import (
    AdaptationEvent,
    Candle,
    ConfigVersionRecord,
    RiskGuardianAssessment,
    RiskProfile,
    SERVProposal,
    ShadowSignalOutcome,
    Signal,
    SupervisorDecision,
    ValidationGateResult,
)
from app.evaluation.clients import SERVAnalyst


MIN_WEIGHT = 0.15
MAX_WEIGHT = 0.85
MAX_STEP_DELTA = 0.25


def normalize_and_bound_weights(w_mom: float, w_rev: float) -> tuple[float, float]:
    """Ensure strategy weights are nonnegative, bounded in [0.15, 0.85], and sum to 1.0."""
    total = w_mom + w_rev
    if total <= 0:
        return 0.5, 0.5
    norm_mom = w_mom / total
    clamped_mom = max(MIN_WEIGHT, min(MAX_WEIGHT, norm_mom))
    clamped_rev = round(1.0 - clamped_mom, 4)
    clamped_mom = round(1.0 - clamped_rev, 4)
    return clamped_mom, clamped_rev


class RiskGuardian:
    """Deterministic OHLCV data-quality, volatility, and exposure guardrail.

    Never claims to inspect holder distribution, creator wallets, or orderbook depth
    when operating on OHLCV candle feeds.
    """

    THRESHOLDS = {
        "conservative": {"block_vol": 2.9, "caution_vol": 1.85, "block_bar_range": 5.5, "max_exposure": 0.65},
        "balanced": {"block_vol": 3.5, "caution_vol": 2.25, "block_bar_range": 6.8, "max_exposure": 0.80},
        "aggressive": {"block_vol": 4.2, "caution_vol": 2.75, "block_bar_range": 8.0, "max_exposure": 0.95},
    }

    @classmethod
    def assess(
        cls,
        visible_candles: list[Candle],
        exposure_pct: float,
        risk_profile: RiskProfile = "conservative",
        expected_interval_sec: int | None = 3600,
    ) -> RiskGuardianAssessment:
        current = visible_candles[-1]
        idx = current.index
        cfg = cls.THRESHOLDS.get(risk_profile, cls.THRESHOLDS["conservative"])

        data_ok = current.isClosed
        if len(visible_candles) >= 2:
            gap = current.timestamp - visible_candles[-2].timestamp
            if (gap != expected_interval_sec) if expected_interval_sec else not (0 < gap <= 90):
                data_ok = False

        # Compute 12-bar realized return volatility (%)
        window = visible_candles[-13:]
        if len(window) >= 3:
            rets = [((window[i].close / window[i - 1].close) - 1.0) * 100.0 for i in range(1, len(window))]
            mean_r = sum(rets) / len(rets)
            var_r = sum((r - mean_r) ** 2 for r in rets) / len(rets)
            realized_vol = math.sqrt(var_r)
        else:
            realized_vol = 0.0

        bar_range_pct = ((current.high - current.low) / current.open) * 100.0 if current.open > 0 else 0.0
        vol_window = [c.volume for c in visible_candles[-12:]]
        avg_vol = sum(vol_window[:-1]) / max(1, len(vol_window) - 1) if len(vol_window) > 1 else current.volume
        vol_ratio = current.volume / avg_vol if avg_vol > 0 else 1.0

        if expected_interval_sec is None:
            vol_ratio = 1.0  # Sampled quotes do not measure pool liquidity or interval volume.
        reasons: list[str] = []
        evidence_ids = [
            f"ev_guard_vol_{idx}:rvol={realized_vol:.2f}%",
            f"ev_guard_range_{idx}:hl_range={bar_range_pct:.2f}%",
            f"ev_guard_vratio_{idx}:vol_ratio={vol_ratio:.2f}x",
        ]

        if not data_ok:
            reasons.append("Data completeness check failed (unclosed candle or timestamp gap).")
            return RiskGuardianAssessment(
                observedAt=current.observedAt,
                candleIndex=idx,
                status="BLOCK",
                realizedVolatilityPct=round(realized_vol, 3),
                volumeRatio=round(vol_ratio, 3),
                dataCompletenessOk=False,
                exposurePct=round(exposure_pct, 3),
                reasons=reasons,
                evidenceIds=evidence_ids,
            )

        if realized_vol >= cfg["block_vol"] or bar_range_pct >= cfg["block_bar_range"]:
            reasons.append(
                f"Realized volatility ({realized_vol:.2f}%) or single-bar range ({bar_range_pct:.2f}%) exceeds {risk_profile} BLOCK ceiling."
            )
            return RiskGuardianAssessment(
                observedAt=current.observedAt,
                candleIndex=idx,
                status="BLOCK",
                realizedVolatilityPct=round(realized_vol, 3),
                volumeRatio=round(vol_ratio, 3),
                dataCompletenessOk=True,
                exposurePct=round(exposure_pct, 3),
                reasons=reasons,
                evidenceIds=evidence_ids,
            )

        if realized_vol >= cfg["caution_vol"] or vol_ratio < 0.25 or exposure_pct >= cfg["max_exposure"] * 100.0:
            if realized_vol >= cfg["caution_vol"]:
                reasons.append(f"Elevated 12-bar volatility ({realized_vol:.2f}% >= {cfg['caution_vol']:.2f}%).")
            if vol_ratio < 0.25:
                reasons.append(f"Thin candle volume ({vol_ratio:.2f}x of 12-bar average).")
            if exposure_pct >= cfg["max_exposure"] * 100.0:
                reasons.append(f"Portfolio exposure ({exposure_pct:.1f}%) near {risk_profile} cap.")
            return RiskGuardianAssessment(
                observedAt=current.observedAt,
                candleIndex=idx,
                status="CAUTION",
                realizedVolatilityPct=round(realized_vol, 3),
                volumeRatio=round(vol_ratio, 3),
                dataCompletenessOk=True,
                exposurePct=round(exposure_pct, 3),
                reasons=reasons,
                evidenceIds=evidence_ids,
            )

        reasons.append(
            f"OHLCV completeness verified; 12-bar volatility ({realized_vol:.2f}%) within {risk_profile} limits."
        )
        return RiskGuardianAssessment(
            observedAt=current.observedAt,
            candleIndex=idx,
            status="ALLOW",
            realizedVolatilityPct=round(realized_vol, 3),
            volumeRatio=round(vol_ratio, 3),
            dataCompletenessOk=True,
            exposurePct=round(exposure_pct, 3),
            reasons=reasons,
            evidenceIds=evidence_ids,
        )


class FeedbackTracker:
    """Tracks shadow signals for all strategies and scores them ONLY after horizon matures."""

    def __init__(self, horizon_bars: int = 4, fee_bps: float = 20.0, slippage_bps: float = 15.0) -> None:
        self.horizon_bars = horizon_bars
        self.fee_bps = fee_bps
        self.slippage_bps = slippage_bps
        self.pending_signals: list[Signal] = []
        self.matured_outcomes: list[ShadowSignalOutcome] = []
        self.trailing_ewma: dict[str, float] = {"momentum": 0.0, "reversal": 0.0}
        self.matured_counts: dict[str, int] = {"momentum": 0, "reversal": 0}
        self.helpful_counts: dict[str, int] = {"momentum": 0, "reversal": 0}

    def record_shadow_signal(self, signal: Signal) -> None:
        if signal.action in ("BUY", "EXIT"):
            self.pending_signals.append(signal)

    def execution_indices(self, signal, visible):
        return signal.candleIndex + 1, signal.candleIndex + self.horizon_bars

    def valid_segment(self, segment):
        return all(b.timestamp - a.timestamp == 3600 for a, b in zip(segment, segment[1:]))

    def mature_eligible_signals(self, visible_candles: list[Candle]) -> list[ShadowSignalOutcome]:
        """Mature only shadow signals whose evaluation horizon has fully elapsed at or before current candle."""
        if not visible_candles:
            return []
        current_idx = visible_candles[-1].index
        newly_matured: list[ShadowSignalOutcome] = []
        still_pending: list[Signal] = []
        roundtrip_cost_pct = ((self.fee_bps + self.slippage_bps) * 2.0) / 100.0  # bps to %

        for sig in self.pending_signals:
            indices = self.execution_indices(sig, visible_candles)
            if indices is None:
                still_pending.append(sig)
                continue
            entry_idx, mature_idx = indices
            if mature_idx <= current_idx and entry_idx < len(visible_candles):
                # Next-bar open entry, horizon close exit — strictly causal!
                segment = visible_candles[sig.candleIndex:mature_idx + 1]
                if not self.valid_segment(segment):
                    # A missing execution/evaluation interval cannot earn a score.
                    continue
                entry_candle = visible_candles[entry_idx]
                exit_candle = visible_candles[mature_idx]
                raw_move_pct = ((exit_candle.close / entry_candle.open) - 1.0) * 100.0
                if sig.action == "BUY":
                    net_return_pct = raw_move_pct - roundtrip_cost_pct
                else:
                    # EXIT signal avoids drawdown / captures inverse move
                    net_return_pct = (-raw_move_pct) - (roundtrip_cost_pct * 0.5)

                was_helpful = net_return_pct > 0.0
                outcome = ShadowSignalOutcome(
                    signalId=sig.id,
                    strategyId=sig.strategyId,
                    issuedAtIndex=sig.candleIndex,
                    maturedAtIndex=mature_idx,
                    observedAt=sig.observedAt,
                    maturedAt=exit_candle.observedAt,
                    action=sig.action,
                    strength=sig.strength,
                    entryPrice=entry_candle.open,
                    exitPrice=exit_candle.close,
                    netReturnPct=round(net_return_pct, 4),
                    wasHelpful=was_helpful,
                )
                self.matured_outcomes.append(outcome)
                newly_matured.append(outcome)

                strat = sig.strategyId
                prev_ewma = self.trailing_ewma[strat]
                count = self.matured_counts[strat]
                alpha = 0.30 if count > 0 else 1.0
                self.trailing_ewma[strat] = round(alpha * net_return_pct + (1.0 - alpha) * prev_ewma, 4)
                self.matured_counts[strat] = count + 1
                if was_helpful:
                    self.helpful_counts[strat] += 1
            else:
                still_pending.append(sig)

        self.pending_signals = still_pending
        return newly_matured


class AdaptationEngine:
    """Detects strategy drift from matured shadow outcomes, proposes bounded changes, and validates against past-only data."""

    def __init__(
        self,
        min_matured_samples: int = 6,
        cooldown_bars: int = 18,
        drift_threshold_pct: float = 0.42,
    ) -> None:
        self.min_matured_samples = min_matured_samples
        self.cooldown_bars = cooldown_bars
        self.drift_threshold_pct = drift_threshold_pct
        self.last_accepted_bar: int = -999
        self.last_proposal_bar: int = -999

    def validate_proposal(
        self,
        current_idx: int,
        old_weights: list[float],
        proposed_weights: list[float],
        matured_outcomes: list[ShadowSignalOutcome],
        evidence_ids: list[str],
        cooldown_respected: bool,
        broker_validation=None,
    ) -> ValidationGateResult:
        """Hard deterministic validation on a past-only segment available at replay time t."""
        w_mom, w_rev = proposed_weights[0], proposed_weights[1]
        weights_in_bounds = (
            MIN_WEIGHT <= w_mom <= MAX_WEIGHT
            and MIN_WEIGHT <= w_rev <= MAX_WEIGHT
            and w_mom >= 0.0
            and w_rev >= 0.0
            and abs((w_mom + w_rev) - 1.0) <= 1e-3
            and abs(w_mom - old_weights[0]) <= MAX_STEP_DELTA + 1e-4
        )
        sample_ok = len(matured_outcomes) >= self.min_matured_samples

        # Verify no future leakage: every matured outcome must have maturedAtIndex <= current_idx
        no_leakage = all(o.maturedAtIndex <= current_idx and o.issuedAtIndex < current_idx for o in matured_outcomes)
        evidence_ok = len(evidence_ids) > 0

        # Validation uses a separate chronological segment, never shadow utility
        # averages (EXIT utility is not investable portfolio return).
        evidence_set = {f"ev_mat_{o.strategyId}_{o.issuedAtIndex}_to_{o.maturedAtIndex}:{o.netReturnPct:+.2f}%" for o in matured_outcomes}
        evidence_ok = bool(evidence_ids) and set(evidence_ids) <= evidence_set
        result = broker_validation(old_weights, proposed_weights) if broker_validation else None
        baseline_ret, candidate_ret, window_bars = result if result else (0.0, 0.0, 0)
        delta_pct = candidate_ret - baseline_ret
        outperforms_past = window_bars >= 24 and delta_pct >= 0.06

        passed = (
            weights_in_bounds
            and sample_ok
            and no_leakage
            and cooldown_respected
            and evidence_ok
            and outperforms_past
        )

        reasons = []
        if not weights_in_bounds:
            reasons.append("Proposed weights violate [0.15, 0.85] bounds, normalization, or max step delta (0.25).")
        if not sample_ok:
            reasons.append(f"Insufficient matured shadow signals ({len(matured_outcomes)} < {self.min_matured_samples}).")
        if not no_leakage:
            reasons.append("Temporal causality check failed: future outcome detected.")
        if not cooldown_respected:
            reasons.append(f"Cooldown gate active (< {self.cooldown_bars} bars since last accepted adaptation).")
        if not outperforms_past:
            reasons.append(
                f"Independent broker validation delta ({delta_pct:+.3f}%) "
                "below required promotion threshold (+0.06%); baseline retained to prevent overfitting noise."
            )

        summary = (
            f"PASSED: Candidate weights ({int(w_mom*100)}/{int(w_rev*100)}) beat baseline ({int(old_weights[0]*100)}/{int(old_weights[1]*100)}) "
            f"by {delta_pct:+.3f}% after costs on {window_bars} separate validation bars."
            if passed
            else "REJECTED: " + " ".join(reasons)
        )

        return ValidationGateResult(
            passed=passed,
            weightsInBounds=weights_in_bounds,
            sampleSizeSufficient=sample_ok,
            noFutureLeakage=no_leakage,
            cooldownRespected=cooldown_respected,
            evidenceVerified=evidence_ok,
            pastSegmentCandidateReturnPct=round(candidate_ret, 4),
            pastSegmentBaselineReturnPct=round(baseline_ret, 4),
            pastSegmentDeltaPct=round(delta_pct, 4),
            validationWindowBars=window_bars,
            summary=summary,
        )

    def check_and_propose(
        self,
        run_id: str,
        dataset_name: str,
        current_candle: Candle,
        active_version: str,
        version_counter: int,
        active_weights: dict[str, float],
        tracker: FeedbackTracker,
        serv_analyst: SERVAnalyst,
        broker_validation=None,
    ) -> Optional[AdaptationEvent]:
        """Check matured outcomes at replay index t and emit an AdaptationEvent if drift trigger fires."""
        idx = current_candle.index
        # Reserve the latest 24 bars for validation. Selection outcomes must
        # fully mature before that window begins (purges overlapping horizons).
        selection = [o for o in tracker.matured_outcomes if o.maturedAtIndex < idx - 23]
        total_matured = len(selection)
        if total_matured < self.min_matured_samples:
            return None
        if idx - self.last_proposal_bar < 14:
            return None

        scores = {"momentum": 0.0, "reversal": 0.0}
        for outcome in selection:
            scores[outcome.strategyId] = .3 * outcome.netReturnPct + .7 * scores[outcome.strategyId]
        mom_score, rev_score = scores["momentum"], scores["reversal"]
        divergence = rev_score - mom_score  # positive means Reversal leads Momentum

        if abs(divergence) < self.drift_threshold_pct:
            return None

        old_w = [round(active_weights["momentum"], 4), round(active_weights["reversal"], 4)]
        # Shift weight toward the outperforming strategy, bounded by MAX_STEP_DELTA
        shift = max(-MAX_STEP_DELTA, min(MAX_STEP_DELTA, divergence * 0.22))
        # Positive divergence -> increase reversal, decrease momentum
        raw_new_mom = old_w[0] - shift
        raw_new_rev = old_w[1] + shift
        cand_mom, cand_rev = normalize_and_bound_weights(raw_new_mom, raw_new_rev)

        if abs(cand_mom - old_w[0]) < 0.05:
            return None

        self.last_proposal_bar = idx
        candidate_w = [cand_mom, cand_rev]
        recent_outcomes = selection[-6:]
        evidence_ids = [
            f"ev_mat_{o.strategyId}_{o.issuedAtIndex}_to_{o.maturedAtIndex}:{o.netReturnPct:+.2f}%"
            for o in recent_outcomes
        ]

        cooldown_ok = (idx - self.last_accepted_bar) >= self.cooldown_bars

        serv_proposal = SERVAnalyst(api_key="").generate_proposal(
            observed_at=current_candle.observedAt,
            dataset_name=dataset_name,
            old_weights=old_w,
            candidate_weights=candidate_w,
            momentum_score=mom_score,
            reversal_score=rev_score,
            matured_count=total_matured,
            allowed_evidence_ids=evidence_ids,
        )

        # Use validated weights from SERVProposal (already checked against [0.15, 0.85] and sum=1)
        prop_mom, prop_rev = normalize_and_bound_weights(
            serv_proposal.suggestedWeights["momentum"],
            serv_proposal.suggestedWeights["reversal"],
        )
        # Enforce max step delta hard constraint
        if abs(prop_mom - old_w[0]) > MAX_STEP_DELTA:
            prop_mom, prop_rev = candidate_w[0], candidate_w[1]
        proposed_w = [prop_mom, prop_rev]

        val_result = self.validate_proposal(
            current_idx=idx,
            old_weights=old_w,
            proposed_weights=proposed_w,
            matured_outcomes=selection,
            evidence_ids=evidence_ids,
            cooldown_respected=cooldown_ok,
            broker_validation=broker_validation,
        )

        event_id = f"adapt_{run_id}_{idx}"
        next_version = f"v1.{version_counter}.0"
        badges = ["DETERMINISTIC", "HISTORICAL"]
        if serv_proposal.provenance == "SERV_GENERATED":
            badges.append("SERV GENERATED")

        if val_result.passed:
            self.last_accepted_bar = idx
            return AdaptationEvent(
                id=event_id,
                runId=run_id,
                detectedAt=current_candle.observedAt,
                candleIndex=idx,
                mechanism="FAST_MATHEMATICAL_SHIFT",
                status="ACCEPTED",
                fromVersion=active_version,
                proposedVersion=next_version,
                oldWeights=old_w,
                proposedWeights=proposed_w,
                triggerMetric=f"EWMA divergence {divergence:+.2f}% (Mom {mom_score:+.2f}% vs Rev {rev_score:+.2f}%)",
                maturedSampleCount=total_matured,
                momentumTrailingScore=mom_score,
                reversalTrailingScore=rev_score,
                evidenceIds=evidence_ids,
                rationale=serv_proposal.hypothesis,
                servProposal=serv_proposal,
                validationResult=val_result,
                activatedAt=current_candle.observedAt,
                provenanceBadges=badges,
            )
        else:
            return AdaptationEvent(
                id=event_id,
                runId=run_id,
                detectedAt=current_candle.observedAt,
                candleIndex=idx,
                mechanism="FAST_MATHEMATICAL_SHIFT",
                status="REJECTED",
                fromVersion=active_version,
                proposedVersion=next_version,
                oldWeights=old_w,
                proposedWeights=proposed_w,
                triggerMetric=f"EWMA divergence {divergence:+.2f}% (Mom {mom_score:+.2f}% vs Rev {rev_score:+.2f}%)",
                maturedSampleCount=total_matured,
                momentumTrailingScore=mom_score,
                reversalTrailingScore=rev_score,
                evidenceIds=evidence_ids,
                rationale=serv_proposal.hypothesis,
                servProposal=serv_proposal,
                validationResult=val_result,
                rejectionReason=val_result.summary,
                activatedAt=None,
                provenanceBadges=badges,
            )


class AdaptiveSupervisor:
    """Combines strategy signals under active weights and applies RiskGuardian hard constraints."""

    @staticmethod
    def decide(
        run_id: str,
        current_candle: Candle,
        config_version: str,
        weights: dict[str, float],
        mom_signal: Signal,
        rev_signal: Signal,
        guardian: RiskGuardianAssessment,
        has_open_position: bool,
    ) -> SupervisorDecision:
        idx = current_candle.index
        dec_id = f"dec_{run_id}_{idx}"
        w_mom = weights["momentum"]
        w_rev = weights["reversal"]

        action_map = {"BUY": 1.0, "WAIT": 0.0, "EXIT": -1.0}
        mom_signed = action_map[mom_signal.action] * mom_signal.strength
        rev_signed = action_map[rev_signal.action] * rev_signal.strength
        combined_score = round(w_mom * mom_signed + w_rev * rev_signed, 4)

        evidence_ids = list(mom_signal.evidence[:2]) + list(rev_signal.evidence[:2]) + list(guardian.evidenceIds[:2])

        # Hard constraint: RiskGuardian BLOCK prevents any new BUY position
        if guardian.status == "BLOCK":
            if has_open_position and combined_score < -0.15:
                return SupervisorDecision(
                    id=dec_id,
                    runId=run_id,
                    observedAt=current_candle.observedAt,
                    candleIndex=idx,
                    configVersion=config_version,
                    action="EXIT",
                    weights={"momentum": w_mom, "reversal": w_rev},
                    guardian="BLOCK",
                    guardianReasons=guardian.reasons,
                    combinedScore=combined_score,
                    evidenceIds=evidence_ids,
                    reason=(
                        f"Risk Guardian BLOCK active ({guardian.reasons[0]}); exiting open paper position on negative score ({combined_score:+.2f})."
                    ),
                )
            return SupervisorDecision(
                id=dec_id,
                runId=run_id,
                observedAt=current_candle.observedAt,
                candleIndex=idx,
                configVersion=config_version,
                action="AVOID",
                weights={"momentum": w_mom, "reversal": w_rev},
                guardian="BLOCK",
                guardianReasons=guardian.reasons,
                combinedScore=combined_score,
                evidenceIds=evidence_ids,
                reason=f"Risk Guardian enforced BLOCK: {guardian.reasons[0]} New paper positions prohibited.",
            )

        buy_threshold = 0.21 if guardian.status == "ALLOW" else 0.29
        exit_threshold = -0.18

        if combined_score >= buy_threshold and not has_open_position:
            caution_note = " (reduced sizing under CAUTION)" if guardian.status == "CAUTION" else ""
            return SupervisorDecision(
                id=dec_id,
                runId=run_id,
                observedAt=current_candle.observedAt,
                candleIndex=idx,
                configVersion=config_version,
                action="BUY",
                weights={"momentum": w_mom, "reversal": w_rev},
                guardian=guardian.status,
                guardianReasons=guardian.reasons,
                combinedScore=combined_score,
                evidenceIds=evidence_ids,
                reason=(
                    f"Weighted score {combined_score:+.2f} >= +{buy_threshold:.2f} under {config_version} "
                    f"(Mom {int(w_mom*100)}%={mom_signal.action}, Rev {int(w_rev*100)}%={rev_signal.action}){caution_note}."
                ),
            )

        if combined_score <= exit_threshold and has_open_position:
            return SupervisorDecision(
                id=dec_id,
                runId=run_id,
                observedAt=current_candle.observedAt,
                candleIndex=idx,
                configVersion=config_version,
                action="EXIT",
                weights={"momentum": w_mom, "reversal": w_rev},
                guardian=guardian.status,
                guardianReasons=guardian.reasons,
                combinedScore=combined_score,
                evidenceIds=evidence_ids,
                reason=(
                    f"Weighted score {combined_score:+.2f} <= {exit_threshold:.2f} under {config_version}; "
                    f"closing paper position on next bar open."
                ),
            )

        return SupervisorDecision(
            id=dec_id,
            runId=run_id,
            observedAt=current_candle.observedAt,
            candleIndex=idx,
            configVersion=config_version,
            action="WAIT",
            weights={"momentum": w_mom, "reversal": w_rev},
            guardian=guardian.status,
            guardianReasons=guardian.reasons,
            combinedScore=combined_score,
            evidenceIds=evidence_ids,
            reason=(
                f"Hold/Abstain: combined score {combined_score:+.2f} within neutral band "
                f"[{exit_threshold:.2f}, +{buy_threshold:.2f}] (Mom={mom_signal.action}, Rev={rev_signal.action})."
            ),
        )
