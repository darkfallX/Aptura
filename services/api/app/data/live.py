"""Current on-chain trades, refreshed on demand; never substitute replay fixtures."""
from datetime import datetime, timezone
from copy import deepcopy
import math
import threading
import time
import httpx

class LiveMarket:
    def __init__(self, transport=None, clock=time.time):
        self.transport, self.clock = transport, clock
        self.cache = {}
        self.retry_after = {}
        self.lock = threading.Lock()

    def snapshot(self, metadata):
        with self.lock:
            now = self.clock()
            cached = self.cache.get(metadata.id)
            if cached and now - cached['fetchedTimestamp'] < 15:
                return self.present(cached, now)
            if now < self.retry_after.get(metadata.id, 0):
                return self.present(cached, now, True) if cached else self.empty(metadata, now)
            try:
                url = f'https://api.geckoterminal.com/api/v2/networks/solana/pools/{metadata.poolAddress}/trades'
                with httpx.Client(timeout=12, transport=self.transport) as client:
                    response = client.get(url, params={'token':'base'})
                    response.raise_for_status()
                rows = response.json()['data']
                trades, seen = [], set()
                for row in rows:
                    a = row['attributes']
                    if row['id'] in seen or a.get('is_anomalous') or a['kind'] not in ('buy','sell'):
                        continue
                    timestamp = datetime.fromisoformat(a['block_timestamp'].replace('Z','+00:00')).timestamp()
                    price = float(a['price_to_in_usd'] if a['kind']=='buy' else a['price_from_in_usd'])
                    volume = float(a['volume_in_usd'])
                    if timestamp > now + 5 or not all(math.isfinite(x) and x > 0 for x in (price, volume)):
                        continue
                    seen.add(row['id'])
                    trades.append({'id':row['id'],'timestamp':timestamp,'observedAt':a['block_timestamp'],
                        'side':a['kind'],'priceUsd':price,'valueUsd':volume})
                trades.sort(key=lambda t:(t['timestamp'],t['id']), reverse=True)
                result = {'marketId':metadata.id,'name':metadata.baseAsset,'pool':metadata.poolAddress,
                    'source':'GeckoTerminal','sourceUrl':url,'fetchedTimestamp':now,
                    'trades':trades[:100], 'refreshSeconds':15,'currency':'USD'}
                self.cache[metadata.id] = result
                return self.present(result, now)
            except (httpx.HTTPError, ValueError, KeyError, TypeError):
                self.retry_after[metadata.id] = now + 30
                return self.present(cached, now, True) if cached else self.empty(metadata, now)

    def empty(self, metadata, now):
        return {'marketId':metadata.id,'name':metadata.baseAsset,'status':'UNAVAILABLE',
            'priceUsd':None,'trades':[],'latestTradeAt':None,'ageSeconds':None,
            'fetchedAt':None,'refreshSeconds':30,'currency':'USD','source':'GeckoTerminal',
            'buyCount':0,'sellCount':0,'sampleCount':0,'priceChangePct':None}

    def present(self, cached, now, failed=False):
        result = deepcopy(cached)
        trades = result['trades']
        age = max(0, now-trades[0]['timestamp']) if trades else None
        recent = [t for t in trades if 0 <= now-t['timestamp'] <= 300]
        result.update(status='UNAVAILABLE' if failed else 'FRESH' if age is not None and age <= 90 else 'STALE',
            priceUsd=trades[0]['priceUsd'] if trades else None,
            latestTradeAt=trades[0]['observedAt'] if trades else None,
            ageSeconds=round(age) if age is not None else None,
            fetchedAt=datetime.fromtimestamp(result.pop('fetchedTimestamp'),timezone.utc).isoformat(),
            buyCount=sum(t['side']=='buy' for t in recent),sellCount=sum(t['side']=='sell' for t in recent),
            sampleCount=len(recent),priceChangePct=((recent[0]['priceUsd']/recent[-1]['priceUsd']-1)*100) if len(recent)>1 else None)
        return result
