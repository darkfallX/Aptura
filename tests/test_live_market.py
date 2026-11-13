import httpx
from app.data.live import LiveMarket
from app.data.loader import DatasetCatalog

NOW=1794421500

def fixture(side='buy', id='trade-1', timestamp='2026-11-11T18:24:28Z'):
    return {'id':id,'attributes':{'kind':side,'block_timestamp':timestamp,
        'price_to_in_usd':'0.0000028','price_from_in_usd':'85',
        'volume_in_usd':'10','is_anomalous':False}}

def metadata(): return DatasetCatalog().get_dataset('momentum-breakdown')[0]

def test_live_uses_actual_side_price_and_deduplicates():
    transport=httpx.MockTransport(lambda request:httpx.Response(200,json={'data':[fixture(),fixture(),fixture('sell','trade-2')]}))
    result=LiveMarket(transport,lambda:NOW).snapshot(metadata())
    assert len(result['trades'])==2
    assert result['status']=='FRESH'
    assert next(t for t in result['trades'] if t['side']=='buy')['priceUsd']==.0000028
    assert next(t for t in result['trades'] if t['side']=='sell')['priceUsd']==85
    assert result['buyCount']==result['sellCount']==1

def test_live_cache_does_not_reset_market_age():
    calls=[];clock=[NOW]
    def fetch(request):
        calls.append(1)
        return httpx.Response(200,json={'data':[fixture()]})
    service=LiveMarket(httpx.MockTransport(fetch),lambda:clock[0])
    a=service.snapshot(metadata());clock[0]+=10;b=service.snapshot(metadata())
    assert len(calls)==1 and b['ageSeconds']==a['ageSeconds']+10

def test_live_failure_retains_last_observation_but_never_claims_fresh():
    clock=[NOW]
    def fetch(request):
        if clock[0]>NOW: return httpx.Response(429)
        return httpx.Response(200,json={'data':[fixture()]})
    service=LiveMarket(httpx.MockTransport(fetch),lambda:clock[0])
    a=service.snapshot(metadata());clock[0]+=20;b=service.snapshot(metadata())
    assert b['status']=='UNAVAILABLE' and b['priceUsd']==a['priceUsd']
    assert b['latestTradeAt']==a['latestTradeAt']

def test_live_never_replaces_missing_data_with_historical_fixture():
    result=LiveMarket(httpx.MockTransport(lambda r:httpx.Response(503)),lambda:NOW).snapshot(metadata())
    assert result['status']=='UNAVAILABLE' and result['priceUsd'] is None and result['trades']==[]

def test_live_filters_future_and_anomalous_trades():
    anomalous=fixture(id='anomalous');anomalous['attributes']['is_anomalous']=True
    rows=[anomalous,fixture(id='future',timestamp='2026-11-12T18:24:28Z')]
    result=LiveMarket(httpx.MockTransport(lambda r:httpx.Response(200,json={'data':rows})),lambda:NOW).snapshot(metadata())
    assert result['status']=='STALE' and result['priceUsd'] is None
