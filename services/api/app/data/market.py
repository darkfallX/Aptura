"""Closed-hour market captures. No tick-level or live-execution claims."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
import httpx
from app.data.loader import DatasetCatalog, DataIntegrityError, validate_candle_series
from app.domain.models import Candle
from app.storage.locking import process_lock


def iso(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


class MarketRecorder:
    def __init__(self, directory: Path):
        self.directory = directory
        directory.mkdir(parents=True, exist_ok=True)

    def capture(self, metadata, now=None, transport=None):
        now = time.time() if now is None else now
        url = f'https://api.geckoterminal.com/api/v2/networks/solana/pools/{metadata.poolAddress}/ohlcv/hour'
        params = {'aggregate': 1, 'limit': 1000, 'currency': 'usd', 'token': 'base', 'include_empty_intervals': 'false'}
        with httpx.Client(timeout=15, transport=transport) as client:
            response = client.get(url, params=params, headers={'Accept': 'application/json'})
            response.raise_for_status()
        raw = response.content
        raw_hash = hashlib.sha256(raw).hexdigest()
        raw_path = self.directory / (raw_hash + '.raw.json')
        if not raw_path.exists():
            raw_path.write_bytes(raw)
        rows = response.json()['data']['attributes']['ohlcv_list']
        candles = []
        for row in sorted(rows, key=lambda r: r[0]):
            timestamp = int(row[0])
            if timestamp + 3600 > now:
                continue
            candles.append(Candle(index=len(candles), timestamp=timestamp,
                observedAt=iso(timestamp + 3600), open=row[1], high=row[2], low=row[3],
                close=row[4], volume=row[5], poolId='solana_' + metadata.poolAddress,
                source='GeckoTerminal Solana Pool OHLCV API v2', timeframe='1h', isClosed=True))
        gaps, completeness = validate_candle_series(candles)
        digest = DatasetCatalog.compute_candles_hash(candles)
        meta = metadata.model_copy(deep=True)
        meta.id = 'capture_' + digest[:24]
        meta.name = metadata.name.split(' · recorded market')[0] + ' · recorded market'
        meta.scenarioLabel = 'Recorded closed-hour market data'
        meta.description = 'Immutable market capture for reproducible paper replay. No live orders.'
        meta.regimeSummary = 'Unclassified; no future regime labels.'
        meta.sourceUrl = str(response.request.url)
        meta.priceCurrency = 'USD'
        meta.fetchedAtUtc = iso(now)
        meta.startTimeUtc, meta.endTimeUtc = candles[0].observedAt, candles[-1].observedAt
        meta.candleCount, meta.gapCount, meta.completenessScore = len(candles), gaps, completeness
        meta.sha256Hash, meta.isSynthetic, meta.recommended = digest, False, False
        document = {'metadata': meta.model_dump(), 'candles': [c.model_dump() for c in candles],
                    'rawResponseHash': raw_hash, 'rawResponseFile': raw_path.name}
        destination = self.directory / (meta.id + '.json')
        with process_lock(self.directory / '.capture.lock'):
            if not destination.exists():
                temporary = destination.with_suffix('.tmp')
                temporary.write_text(json.dumps(document, sort_keys=True), encoding='utf-8')
                temporary.replace(destination)
        age = max(0, now - (candles[-1].timestamp + 3600))
        return meta, candles, {'datasetId': meta.id, 'lastClosedAt': meta.endTimeUtc,
            'fetchedAt': meta.fetchedAtUtc, 'ageSeconds': round(age), 'gapCount': gaps,
            'status': 'GAPPED' if gaps else 'STALE' if age > 3900 else 'FRESH',
            'mode': 'CLOSED_HOURLY_CANDLES', 'priceCurrency': 'USD',
            'rawResponseHash': raw_hash, 'paperOnly': True}

    def restore(self, catalog):
        for path in self.directory.glob('capture_*.json'):
            document = json.loads(path.read_text(encoding='utf-8'))
            from app.domain.models import DatasetMetadata
            meta = DatasetMetadata.model_validate(document['metadata'])
            candles = [Candle.model_validate(c) for c in document['candles']]
            if DatasetCatalog.compute_candles_hash(candles) != meta.sha256Hash:
                raise DataIntegrityError('Recorded capture hash mismatch')
            validate_candle_series(candles)
            catalog.register(meta, candles)
