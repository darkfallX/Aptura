"""Dataset loader and strict OHLCV temporal/integrity validator for Aptura."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
import math
import os
from pathlib import Path
from typing import Tuple

from app.domain.models import Candle, DatasetMetadata


DEFAULT_DATA_FILE = Path(os.environ.get("APTURA_DATA_DIR", str(Path(__file__).resolve().parents[4] / "data"))) / "datasets.json"


class DataIntegrityError(ValueError):
    """Raised when a candle series fails temporal or numerical integrity validation."""


def validate_candle_series(candles: list[Candle], expected_interval_sec: int = 3600) -> Tuple[int, float]:
    """Validate OHLCV bounds, monotonic timestamps, closed status, and gap count.

    Never silently fills gaps with invented candles.
    """
    if len(candles) < 30:
        raise DataIntegrityError(f"Dataset has too few candles ({len(candles)} < 30)")

    seen_timestamps: set[int] = set()
    gaps = 0

    for idx, c in enumerate(candles):
        if c.index != idx:
            raise DataIntegrityError(f"Non-contiguous candle index at {idx}")
        if not c.isClosed:
            raise DataIntegrityError(f"Candle at index {idx} ({c.observedAt}) is not closed")
        if any(math.isnan(v) or math.isinf(v) for v in (c.open, c.high, c.low, c.close, c.volume)):
            raise DataIntegrityError(f"NaN or Inf value in candle at index {idx}")
        if c.open <= 0 or c.high <= 0 or c.low <= 0 or c.close <= 0 or c.volume < 0:
            raise DataIntegrityError(f"Non-positive price or negative volume at index {idx}")
        if c.high < max(c.open, c.close, c.low) or c.low > min(c.open, c.close, c.high):
            raise DataIntegrityError(f"Invalid OHLC envelope at index {idx}")
        if c.timestamp in seen_timestamps:
            raise DataIntegrityError(f"Duplicate candle timestamp {c.timestamp} at index {idx}")
        seen_timestamps.add(c.timestamp)

        if datetime.fromisoformat(c.observedAt.replace("Z", "+00:00")).timestamp() < c.timestamp + expected_interval_sec:
            raise DataIntegrityError(f"Candle observed before closure at {idx}")
        if idx > 0:
            prev_ts = candles[idx - 1].timestamp
            if c.timestamp <= prev_ts:
                raise DataIntegrityError(
                    f"Non-monotonic timestamps at index {idx}: {c.timestamp} <= {prev_ts}"
                )
            diff = c.timestamp - prev_ts
            if diff != expected_interval_sec:
                gaps += 1

    completeness = round(max(0.0, 1.0 - (gaps / len(candles))), 4)
    return gaps, completeness


class DatasetCatalog:
    """Loads and serves verified historical Solana pool datasets."""

    def __init__(self, data_file: Path = DEFAULT_DATA_FILE) -> None:
        self.data_file = data_file
        self._datasets: dict[str, tuple[DatasetMetadata, list[Candle]]] = {}
        self.reload()

    def reload(self) -> None:
        if not self.data_file.exists():
            raise FileNotFoundError(f"Dataset file not found: {self.data_file}")
        raw = json.loads(self.data_file.read_text(encoding="utf-8"))
        loaded: dict[str, tuple[DatasetMetadata, list[Candle]]] = {}
        for item in raw.get("datasets", []):
            meta = DatasetMetadata.model_validate(item["metadata"])
            candles = [Candle.model_validate(c) for c in item["candles"]]
            if self.compute_candles_hash(candles) != meta.sha256Hash:
                raise DataIntegrityError(f"Dataset hash mismatch: {meta.id}")
            gaps, completeness = validate_candle_series(candles)
            if gaps != meta.gapCount:
                meta.gapCount = gaps
                meta.completenessScore = completeness
            loaded[meta.id] = (meta, candles)
        self._datasets = loaded

    def register(self, meta, candles):
        self._datasets[meta.id] = (meta.model_copy(deep=True), [c.model_copy(deep=True) for c in candles])

    def list_metadata(self) -> list[DatasetMetadata]:
        return [pair[0] for pair in self._datasets.values()]

    def get_dataset(self, dataset_id: str) -> tuple[DatasetMetadata, list[Candle]]:
        if dataset_id not in self._datasets:
            raise KeyError(f"Unknown dataset '{dataset_id}'")
        meta, candles = self._datasets[dataset_id]
        return meta.model_copy(deep=True), [c.model_copy(deep=True) for c in candles]

    @staticmethod
    def compute_candles_hash(candles: list[Candle]) -> str:
        raw_list = [c.model_dump() for c in candles]
        payload = json.dumps(raw_list, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()
