"""Deterministic, zero-look-ahead Momentum Scout and Reversal Scout modules."""

from __future__ import annotations

import math
from app.domain.models import Candle, Signal


def _ema(values: list[float], period: int) -> float:
    if not values:
        return 0.0
    alpha = 2.0 / (period + 1.0)
    ema_val = values[0]
    for v in values[1:]:
        ema_val = alpha * v + (1.0 - alpha) * ema_val
    return ema_val


def _rsi(closes: list[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    deltas = [closes[i] - closes[i - 1] for i in range(-period, 0)]
    gains = [d if d > 0 else 0.0 for d in deltas]
    losses = [-d if d < 0 else 0.0 for d in deltas]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


class MomentumScout:
    """Rules-based trend-following strategy operating strictly on closed candles <= t."""

    strategy_id = "momentum"

    @classmethod
    def evaluate(
        cls,
        visible_candles: list[Candle],
        warmup_bars: int = 20,
        run_id: str = "run",
    ) -> Signal:
        if not visible_candles:
            raise ValueError("visible_candles cannot be empty")
        current = visible_candles[-1]
        idx = current.index
        sig_id = f"sig_mom_{idx}_{current.timestamp}"

        if len(visible_candles) < warmup_bars:
            return Signal(
                id=sig_id,
                strategyId="momentum",
                observedAt=current.observedAt,
                candleIndex=idx,
                action="WAIT",
                strength=0.0,
                indicators={"warmupProgress": round(len(visible_candles) / max(1, warmup_bars), 3)},
                evidence=[
                    f"ev_mom_warmup_{idx}:bars={len(visible_candles)}/{warmup_bars}",
                    f"ev_candle_{idx}:ts={current.observedAt}",
                ],
                rationale=f"Warm-up window ({len(visible_candles)}/{warmup_bars} closed bars); no premature signal emitted.",
            )

        closes = [c.close for c in visible_candles[-24:]]
        volumes = [c.volume for c in visible_candles[-16:]]
        ema_fast = _ema(closes, 6)
        ema_slow = _ema(closes, 18)
        ema_spread_pct = ((ema_fast / ema_slow) - 1.0) * 100.0 if ema_slow > 0 else 0.0
        roc_6_pct = ((closes[-1] / closes[-7]) - 1.0) * 100.0 if len(closes) >= 7 and closes[-7] > 0 else 0.0
        roc_3_pct = ((closes[-1] / closes[-4]) - 1.0) * 100.0 if len(closes) >= 4 and closes[-4] > 0 else 0.0
        avg_vol = sum(volumes[:-1]) / max(1, len(volumes) - 1)
        vol_ratio = volumes[-1] / avg_vol if avg_vol > 0 else 1.0
        if current.timeframe == "observed-trade":
            vol_ratio = 1.0  # No liquidity inference from a sampled trade price.

        indicators = {
            "emaFast6": round(ema_fast, 8),
            "emaSlow18": round(ema_slow, 8),
            "emaSpreadPct": round(ema_spread_pct, 4),
            "roc6Pct": round(roc_6_pct, 4),
            "roc3Pct": round(roc_3_pct, 4),
            "volumeRatio": round(vol_ratio, 3),
        }

        evidence = [
            f"ev_mom_ema_{idx}:spread={ema_spread_pct:+.2f}%",
            f"ev_mom_roc6_{idx}:roc6={roc_6_pct:+.2f}%",
            f"ev_mom_vol_{idx}:not_measured" if current.timeframe == "observed-trade" else f"ev_mom_vol_{idx}:vol_ratio={vol_ratio:.2f}x",
            f"ev_candle_{idx}:ts={current.observedAt}",
        ]

        if ema_spread_pct > 0.12 and (roc_6_pct > 0.55 or roc_3_pct > 0.45):
            raw_strength = min(1.0, max(0.35, ( abs(roc_6_pct) / 3.2 ) * 0.65 + min(1.5, vol_ratio) * 0.25))
            return Signal(
                id=sig_id,
                strategyId="momentum",
                observedAt=current.observedAt,
                candleIndex=idx,
                action="BUY",
                strength=round(raw_strength, 3),
                indicators=indicators,
                evidence=evidence,
                rationale=f"Fast EMA leads slow EMA by {ema_spread_pct:+.2f}% with {roc_6_pct:+.2f}% 6-bar momentum.",
            )

        if ema_spread_pct < -0.12 or roc_6_pct < -0.75:
            raw_strength = min(1.0, max(0.35, abs(roc_6_pct) / 3.0))
            return Signal(
                id=sig_id,
                strategyId="momentum",
                observedAt=current.observedAt,
                candleIndex=idx,
                action="EXIT",
                strength=round(raw_strength, 3),
                indicators=indicators,
                evidence=evidence,
                rationale=f"Momentum breakdown detected: 6-bar ROC {roc_6_pct:+.2f}%, EMA spread {ema_spread_pct:+.2f}%.",
            )

        return Signal(
            id=sig_id,
            strategyId="momentum",
            observedAt=current.observedAt,
            candleIndex=idx,
            action="WAIT",
            strength=round(min(0.3, abs(ema_spread_pct) / 1.5), 3),
            indicators=indicators,
            evidence=evidence,
            rationale=f"No clear trend impulse (EMA spread {ema_spread_pct:+.2f}%, 6-bar ROC {roc_6_pct:+.2f}%).",
        )


class ReversalScout:
    """Rules-based mean-reversion strategy operating strictly on closed candles <= t."""

    strategy_id = "reversal"

    @classmethod
    def evaluate(
        cls,
        visible_candles: list[Candle],
        warmup_bars: int = 20,
        run_id: str = "run",
    ) -> Signal:
        if not visible_candles:
            raise ValueError("visible_candles cannot be empty")
        current = visible_candles[-1]
        idx = current.index
        sig_id = f"sig_rev_{idx}_{current.timestamp}"

        if len(visible_candles) < warmup_bars:
            return Signal(
                id=sig_id,
                strategyId="reversal",
                observedAt=current.observedAt,
                candleIndex=idx,
                action="WAIT",
                strength=0.0,
                indicators={"warmupProgress": round(len(visible_candles) / max(1, warmup_bars), 3)},
                evidence=[
                    f"ev_rev_warmup_{idx}:bars={len(visible_candles)}/{warmup_bars}",
                    f"ev_candle_{idx}:ts={current.observedAt}",
                ],
                rationale=f"Warm-up window ({len(visible_candles)}/{warmup_bars} closed bars); no premature signal emitted.",
            )

        closes = [c.close for c in visible_candles[-20:]]
        window = closes[-16:]
        mean_p = sum(window) / len(window)
        variance = sum((p - mean_p) ** 2 for p in window) / len(window)
        std_p = math.sqrt(variance) if variance > 0 else 1e-9
        z_score = (closes[-1] - mean_p) / std_p
        rsi_14 = _rsi(closes, 14)
        bar_return_pct = ((closes[-1] / closes[-2]) - 1.0) * 100.0 if len(closes) >= 2 and closes[-2] > 0 else 0.0

        indicators = {
            "zScore16": round(z_score, 4),
            "rsi14": round(rsi_14, 2),
            "sma16": round(mean_p, 8),
            "barReturnPct": round(bar_return_pct, 4),
        }

        evidence = [
            f"ev_rev_z_{idx}:z16={z_score:+.2f}",
            f"ev_rev_rsi_{idx}:rsi14={rsi_14:.1f}",
            f"ev_rev_ret1_{idx}:bar={bar_return_pct:+.2f}%",
            f"ev_candle_{idx}:ts={current.observedAt}",
        ]

        if z_score < -0.75 or rsi_14 < 39.0:
            raw_strength = min(1.0, max(0.38, (abs(z_score) / 2.2) * 0.7 + ((45.0 - min(45.0, rsi_14)) / 25.0) * 0.3))
            return Signal(
                id=sig_id,
                strategyId="reversal",
                observedAt=current.observedAt,
                candleIndex=idx,
                action="BUY",
                strength=round(raw_strength, 3),
                indicators=indicators,
                evidence=evidence,
                rationale=f"Mean-reversion dip entry: Z-score {z_score:+.2f}σ below 16-bar mean (RSI {rsi_14:.1f}).",
            )

        if z_score > 0.80 or rsi_14 > 61.0:
            raw_strength = min(1.0, max(0.38, (abs(z_score) / 2.2) * 0.7 + ((max(55.0, rsi_14) - 55.0) / 25.0) * 0.3))
            return Signal(
                id=sig_id,
                strategyId="reversal",
                observedAt=current.observedAt,
                candleIndex=idx,
                action="EXIT",
                strength=round(raw_strength, 3),
                indicators=indicators,
                evidence=evidence,
                rationale=f"Overbought reversion exit: Z-score {z_score:+.2f}σ above 16-bar mean (RSI {rsi_14:.1f}).",
            )

        return Signal(
            id=sig_id,
            strategyId="reversal",
            observedAt=current.observedAt,
            candleIndex=idx,
            action="WAIT",
            strength=round(min(0.28, abs(z_score) / 2.5), 3),
            indicators=indicators,
            evidence=evidence,
            rationale=f"Price near equilibrium (Z-score {z_score:+.2f}σ, RSI {rsi_14:.1f}).",
        )
