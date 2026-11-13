"""Prepare and validate canonical historical Solana pool datasets for Aptura."""

from __future__ import annotations

import datetime
import hashlib
import json
import math
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent


def iso_utc(ts: int) -> str:
    return datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_and_validate_gecko(
    raw_file: Path,
    dataset_id: str,
    name: str,
    scenario_label: str,
    description: str,
    regime_summary: str,
    pool_address: str,
    base_asset: str,
    quote_asset: str,
    recommended: bool = False,
) -> dict:
    raw_bytes = raw_file.read_bytes()
    raw_json = json.loads(raw_bytes.decode("utf-8"))
    ohlcv_raw = raw_json["data"]["attributes"]["ohlcv_list"]
    # Sort ascending by timestamp and drop the final in-progress candle
    ohlcv_sorted = sorted(ohlcv_raw, key=lambda row: int(row[0]))[:-1]

    # Deduplicate by timestamp if any
    deduped = []
    seen_ts = set()
    for row in ohlcv_sorted:
        ts = int(row[0])
        if ts not in seen_ts:
            seen_ts.add(ts)
            deduped.append(row)

    candles = []
    gaps = 0
    for idx, row in enumerate(deduped):
        ts = int(row[0])
        o, h, l, c, v = float(row[1]), float(row[2]), float(row[3]), float(row[4]), float(row[5])
        if any(math.isnan(x) or math.isinf(x) for x in (o, h, l, c, v)):
            raise ValueError(f"NaN/Inf in candle at {ts}")
        if l <= 0 or o <= 0 or h <= 0 or c <= 0 or h < max(o, c, l) or l > min(o, c, h):
            raise ValueError(f"Invalid OHLC bounds at {ts}: {row}")
        if idx > 0 and (ts - int(deduped[idx - 1][0])) != 3600:
            gaps += 1
        candles.append(
            {
                "index": idx,
                "timestamp": ts,
                "observedAt": iso_utc(ts + 3600),
                "open": round(o, 10),
                "high": round(h, 10),
                "low": round(l, 10),
                "close": round(c, 10),
                "volume": round(v, 4),
                "poolId": f"solana_{pool_address}",
                "source": "GeckoTerminal Solana Pool OHLCV API v2",
                "timeframe": "1h",
                "isClosed": True,
            }
        )

    canonical_candles_bytes = json.dumps(candles, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sha256_hash = hashlib.sha256(canonical_candles_bytes).hexdigest()

    metadata = {
        "id": dataset_id,
        "name": name,
        "scenarioLabel": scenario_label,
        "description": description,
        "regimeSummary": regime_summary,
        "poolAddress": pool_address,
        "chain": "solana",
        "baseAsset": base_asset,
        "quoteAsset": quote_asset,
        "priceCurrency": "USD",
        "source": "GeckoTerminal Solana Pool OHLCV API v2",
        "sourceUrl": f"https://api.geckoterminal.com/api/v2/networks/solana/pools/{pool_address}/ohlcv/hour?aggregate=1&limit=200",
        "timeframe": "1h",
        "candleCount": len(candles),
        "startTimeUtc": candles[0]["observedAt"],
        "endTimeUtc": candles[-1]["observedAt"],
        "fetchedAtUtc": "2026-11-09T03:08:50Z",
        "sha256Hash": sha256_hash,
        "completenessScore": round(1.0 - (gaps / max(1, len(candles))), 4),
        "gapCount": gaps,
        "isSynthetic": False,
        "recommended": recommended,
    }
    return {"metadata": metadata, "candles": candles}


def build_synthetic_guardrail_dataset() -> dict:
    """Explicitly labeled synthetic tutorial dataset designed to test noise-rejection & guardian blocks."""
    base_ts = 1793476800  # 2026-10-31T20:00:00Z
    price = 1.0000
    candles = []
    for idx in range(120):
        ts = base_ts + idx * 3600
        # Phase 1 (0..45): gentle trend up; Phase 2 (45..80): violent whipsaw spike to trigger guardian & rejected noisy proposal; Phase 3 (80..120): mean reversion
        if idx < 45:
            delta = 0.008 * math.sin(idx * 0.35) + 0.0035
            vol = 42000.0 + 5000.0 * math.cos(idx * 0.4)
        elif idx < 80:
            delta = (0.042 if idx % 2 == 0 else -0.044) + 0.005 * math.sin(idx)
            vol = 185000.0 + 25000.0 * (idx % 3)
        else:
            delta = -0.015 * math.sin((idx - 80) * 0.6) - 0.001
            vol = 55000.0
        open_p = price
        close_p = max(0.20, open_p * (1.0 + delta))
        high_p = max(open_p, close_p) * (1.0 + (0.025 if 45 <= idx < 80 else 0.007))
        low_p = min(open_p, close_p) * (1.0 - (0.025 if 45 <= idx < 80 else 0.007))
        price = close_p
        candles.append(
            {
                "index": idx,
                "timestamp": ts,
                "observedAt": iso_utc(ts + 3600),
                "open": round(open_p, 6),
                "high": round(high_p, 6),
                "low": round(low_p, 6),
                "close": round(close_p, 6),
                "volume": round(vol, 2),
                "poolId": "synthetic_guardrail_pool",
                "source": "Aptura Synthetic Adversarial Generator v1 (Tutorial)",
                "timeframe": "1h",
                "isClosed": True,
            }
        )

    canonical_bytes = json.dumps(candles, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sha256_hash = hashlib.sha256(canonical_bytes).hexdigest()
    metadata = {
        "id": "synthetic-noise-guard",
        "name": "SYNTH-MEME / SOL (Synthetic Guardrail)",
        "scenarioLabel": "Synthetic Demonstration — Adversarial Whipsaw",
        "description": "Explicitly synthetic stress-test regime built to verify Risk Guardian volatility blocks and deterministic rejection of overfitted adaptation proposals.",
        "regimeSummary": "Controlled trend followed by extreme +/-4.4% hourly whipsaw spikes and mean-reversion.",
        "poolAddress": "SYNTHETIC_NO_POOL_ADDRESS",
        "chain": "solana",
        "baseAsset": "SYNTH",
        "quoteAsset": "SOL",
        "source": "Aptura Synthetic Adversarial Generator v1 (Tutorial)",
        "sourceUrl": "local://synthetic-noise-guard",
        "timeframe": "1h",
        "candleCount": len(candles),
        "startTimeUtc": candles[0]["observedAt"],
        "endTimeUtc": candles[-1]["observedAt"],
        "fetchedAtUtc": "2026-11-09T03:08:50Z",
        "sha256Hash": sha256_hash,
        "completenessScore": 1.0,
        "gapCount": 0,
        "isSynthetic": True,
        "recommended": False,
    }
    return {"metadata": metadata, "candles": candles}


def main() -> None:
    datasets = [
        load_and_validate_gecko(
            raw_file=DATA_DIR / "raw_bonk_sol_1h.json",
            dataset_id="momentum-breakdown",
            name="BONK / SOL",
            scenario_label="Momentum Breakdown",
            description="Verified Raydium/Orca Solana pool history where a +8.56% Q2 breakout rally reverses into a -7.21% Q3 breakdown, exposing static momentum chasing.",
            regime_summary="Breakout rally (+8.56%) followed by sharp trend exhaustion (-7.21%) and mean-reverting stabilization.",
            pool_address="5zpyutJu9ee6jFymDGoK7F6S5Kczqtc9FomP3ueKuyA9",
            base_asset="BONK",
            quote_asset="SOL",
            recommended=True,
        ),
        load_and_validate_gecko(
            raw_file=DATA_DIR / "raw_popcat_sol_1h.json",
            dataset_id="choppy-market",
            name="POPCAT / SOL",
            scenario_label="Choppy Market",
            description="Verified Solana pool exhibiting negative lag-1 serial correlation (AC1 = -0.138) and frequent intraday reversals that penalize late trend entries.",
            regime_summary="High-dispersion mean-reverting chop with persistent fade-the-spike dynamics across 199 hourly bars.",
            pool_address="FRhB8L7Y9Qq41qZXYLtC2nw8An1RJfLLxRF2x9RwLLMo",
            base_asset="POPCAT",
            quote_asset="SOL",
            recommended=False,
        ),
        load_and_validate_gecko(
            raw_file=DATA_DIR / "raw_sol_usdc_1h.json",
            dataset_id="steady-trend",
            name="SOL / USDC",
            scenario_label="Steady Trend & Pullback",
            description="High-liquidity Solana reference pool across 199 contiguous hourly candles with structured directional legs and lower microstructure noise.",
            regime_summary="Ordered multi-day trend waves (-3.84% -> +3.96% -> -5.57%) with clean momentum continuation phases.",
            pool_address="Czfq3xZZDmsdGdUyrNLtRhGc47cXcZtLG4crryfu44zE",
            base_asset="SOL",
            quote_asset="USDC",
            recommended=False,
        ),
        build_synthetic_guardrail_dataset(),
    ]

    out_path = DATA_DIR / "datasets.json"
    out_path.write_text(json.dumps({"datasets": datasets}, indent=2), encoding="utf-8")
    print(f"Wrote {len(datasets)} validated datasets to {out_path}")
    for d in datasets:
        m = d["metadata"]
        print(f" - {m['id']}: {m['name']} ({m['candleCount']} bars, gaps={m['gapCount']}, synthetic={m['isSynthetic']}, sha256={m['sha256Hash'][:12]}...)")


if __name__ == "__main__":
    main()
