"""Regression checks for independent gates, reviewed activation and market recording."""
import copy
import json
import httpx
import pytest
from fastapi.testclient import TestClient
from app.data.loader import DatasetCatalog, DataIntegrityError
from app.data.market import MarketRecorder
from app.evaluation.clients import SERVAnalyst, ReppoClient
from app.evaluation.workflow import new_job, process_job
from app.main import create_app
from app.replay.simulator import ReplaySession
from app.replay.comparisons import validate_weights
from app.storage.repository import SQLiteRepository


def session():
    meta, candles = DatasetCatalog().get_dataset('momentum-breakdown')
    return ReplaySession('regression', meta, candles, serv_analyst=SERVAnalyst(api_key=''))


def test_selection_excludes_validation_and_gate_requires_broker():
    run = session()
    run.advance(198)
    for event in run.adaptation_events:
        for evidence in event.evidenceIds:
            matured = int(evidence.split('_to_')[1].split(':')[0])
            assert matured < event.candleIndex - 23
        assert event.validationResult.validationWindowBars == 24
        if event.status == 'ACCEPTED':
            assert event.validationResult.pastSegmentDeltaPct >= .06
    gate = run.adaptation_engine.validate_proposal(run.cursor, [.6,.4], [.4,.6],
        run.tracker.matured_outcomes, ['unknown'], True)
    assert not gate.passed and not gate.evidenceVerified


def test_validation_never_uses_unseen_candles():
    run = session()
    run.advance(95)
    before = validate_weights(run, [.6,.4], [.4,.6])
    for candle in run._all_candles[96:]:
        candle.open *= 100
        candle.close *= 100
    assert validate_weights(run, [.6,.4], [.4,.6]) == before


@pytest.mark.parametrize('raw', ['{}', '[]', '{"hypothesis":1}', json.dumps({
    'hypothesis':'test','evidenceIds':['ok'],'suggestedWeights':{'momentum':True,'reversal':False},
    'assumptions':['a'],'uncertainties':['u']})])
def test_serv_missing_and_wrong_types_rejected(raw):
    with pytest.raises(ValueError):
        SERVAnalyst.validate_and_parse_response(raw,['ok'],[.6,.4],'2026-01-01T00:00:00Z','test')


def test_gap_cancels_pending_fill_and_observation_time_is_close():
    run = session()
    broker = run.brokers['adaptive']
    candle = run._all_candles[0]
    from datetime import datetime
    assert datetime.fromisoformat(candle.observedAt.replace('Z','+00:00')).timestamp() == candle.timestamp + 3600
    broker.queue_intent(0,candle.observedAt,'BUY',.6,'v1','test')
    run._all_candles[1].timestamp += 3600
    run.advance(1)
    assert not broker.orders
    assert run.snapshot().latestGuardian.status == 'BLOCK'


def test_recording_filters_open_candles_preserves_raw_and_restores(tmp_path):
    run = session()
    rows = [[c.timestamp,c.open,c.high,c.low,c.close,c.volume] for c in run._all_candles[:45]]
    transport = httpx.MockTransport(lambda req: httpx.Response(200,json={'data':{'attributes':{'ohlcv_list':rows}}}))
    recorder = MarketRecorder(tmp_path)
    now = rows[-1][0] + 120
    meta, candles, status = recorder.capture(run.dataset,now=now,transport=transport)
    assert len(candles) == 44 and status['status'] == 'FRESH'
    assert meta.priceCurrency == 'USD'
    assert list(tmp_path.glob('*.raw.json'))
    catalog = DatasetCatalog()
    recorder.restore(catalog)
    assert catalog.get_dataset(meta.id)[1] == candles
    _,_,stale = recorder.capture(run.dataset,now=now+10000,transport=transport)
    assert stale['status'] == 'STALE'


def test_duplicate_market_candles_rejected(tmp_path):
    run = session()
    rows = [[c.timestamp,c.open,c.high,c.low,c.close,c.volume] for c in run._all_candles[:40]]
    rows.append(rows[1])
    transport = httpx.MockTransport(lambda req:httpx.Response(200,json={'data':{'attributes':{'ohlcv_list':rows}}}))
    with pytest.raises(DataIntegrityError,match='Duplicate'):
        MarketRecorder(tmp_path).capture(run.dataset,now=rows[-2][0]+4000,transport=transport)
    assert not list(tmp_path.glob('capture_*.json'))


def test_review_unconfigured_durable_and_audit_complete(tmp_path):
    repo=SQLiteRepository(tmp_path/'audit.db')
    app=create_app(repo=repo,serv_analyst=SERVAnalyst(api_key=''),reppo_client=ReppoClient(api_key=''))
    client=TestClient(app)
    run=client.post('/api/replays',json={'datasetId':'momentum-breakdown'}).json()
    path='/api/replays/'+run['runId']
    advanced=client.post(path+'/advance',json={'steps':80}).json()
    event=advanced['adaptationEvents'][0]
    job=client.post('/api/adaptations/'+event['id']+'/review').json()
    assert job['state']=='UNCONFIGURED'
    other=TestClient(create_app(repo=repo))
    assert other.get(path+'/reviews').json()[0]['id']==job['id']
    audit=other.get(path+'/audit').json()['audit']
    assert len(audit['decisions'])==81
    assert len(audit['signals'])==162
    assert audit['reviewTransitions']


def test_ambiguous_submission_is_not_repeated(tmp_path):
    run=session();run.advance(80)
    repo=SQLiteRepository(tmp_path/'review.db')
    job=new_job(run,run.adaptation_events[0],True)
    job['state']='SUBMITTING'
    process_job(job,run,repo,SERVAnalyst(api_key=''),ReppoClient(api_key=''))
    assert job['state']=='SUBMISSION_UNKNOWN'
    assert not run.activation_commands


def test_reviewed_activation_replays_identically_after_restart(tmp_path):
    # Exercise persisted commands independently of external providers; the command
    # fixture is explicitly test-only, not a seeded provider verdict.
    run=session();run.advance(80)
    event=run.adaptation_events[0].model_copy(deep=True)
    event.id='test_review_command';event.mechanism='REVIEWED_PROPOSAL'
    event.status='ACCEPTED';event.candleIndex=81;event.fromVersion=run.config_version
    event.proposedVersion=f'v1.{run.version_counter}.0';event.proposedWeights=[.4,.6]
    command={'id':event.id,'runId':run.run_id,'candleIndex':81,'event':event.model_dump()}
    run.activation_commands.append(command)
    run.advance(10)
    restored=ReplaySession(run.run_id,run.dataset,run._all_candles,activation_commands=[command])
    restored.advance(90)
    assert run.snapshot().equityCurve==restored.snapshot().equityCurve
    assert run.snapshot().configHistory==restored.snapshot().configHistory


def test_two_apps_serialize_and_refresh_same_run(tmp_path):
    repo=SQLiteRepository(tmp_path/'shared.db')
    a,b=TestClient(create_app(repo=repo)),TestClient(create_app(repo=repo))
    run=a.post('/api/replays',json={'datasetId':'momentum-breakdown'}).json()
    path='/api/replays/'+run['runId']
    assert b.get(path).json()['cursor']==0
    a.post(path+'/advance',json={'steps':10})
    assert b.post(path+'/advance',json={'steps':5}).json()['cursor']==15
    assert a.get(path).json()['cursor']==15

def test_external_acceptance_cannot_bypass_local_gate(tmp_path):
    run=session();run.advance(80)
    repo=SQLiteRepository(tmp_path/'gates.db')
    event=run.adaptation_events[0]
    job=new_job(run,event,True)
    record=ReppoClient(api_key='').submit_evaluation(event,run.dataset.name)
    record.status='SETTLED';record.decision='accept';record.score=100
    job.update(state='PENDING_REVIEW',evaluation=record.model_dump(),nextAttemptAt=0)
    # Force a malicious candidate to violate the hard bounds.
    job['event']['proposedWeights']=[1.0,0.0]
    class Accepted:
        def poll_evaluation(self, record): return record
    process_job(job,run,repo,None,Accepted())
    assert job['state']=='REJECTED'
    assert not run.activation_commands


def test_full_review_workflow_promotes_only_after_both_gates(tmp_path):
    reference=session();reference.advance(198)
    accepted=next(e for e in reference.adaptation_events if e.status=='ACCEPTED')
    run=session();run.advance(accepted.candleIndex-1)
    # Suppress the automatic change on this bar so the exact same candidate
    # can travel through the independent, mocked external-review route instead.
    original=run.adaptation_engine.check_and_propose
    run.adaptation_engine.check_and_propose=lambda **kwargs:None
    run.advance(1)
    run.adaptation_engine.check_and_propose=original
    repo=SQLiteRepository(tmp_path/'promote.db')
    job=new_job(run,accepted,True)
    repo.save_job(job)
    class Analyst:
        def generate_proposal(self,*args):
            return accepted.servProposal.model_copy(update={'provenance':'SERV_GENERATED'})
    class Reviewer:
        def submit_evaluation(self,event,name):
            return ReppoClient(api_key='').submit_evaluation(event,name).model_copy(update={
                'status':'PENDING','provenance':'REPPO_LIVE','evalId':'test-only-provider-id'})
        def poll_evaluation(self,record):
            return record.model_copy(update={'status':'SETTLED','decision':'accept','score':90})
    process_job(job,run,repo,Analyst(),Reviewer())
    assert job['state']=='READY_TO_SUBMIT'
    process_job(job,run,repo,Analyst(),Reviewer())
    assert job['state']=='PENDING_REVIEW'
    assert not run.activation_commands
    job['nextAttemptAt']=0
    process_job(job,run,repo,Analyst(),Reviewer())
    assert job['state']=='SCHEDULED',job['message']
    assert len(repo.list_activations(run.run_id))==1
    before=run.config_version
    run.advance(1)
    assert run.config_version!=before
    process_job(job,run,repo,Analyst(),Reviewer())
    assert job['state']=='ACTIVATED'


def test_market_watch_backoff_survives_restart(tmp_path,monkeypatch):
    def unavailable(*args,**kwargs): raise httpx.ConnectError('offline')
    monkeypatch.setattr(MarketRecorder,'capture',unavailable)
    repo=SQLiteRepository(tmp_path/'watch.db')
    app=create_app(repo=repo);client=TestClient(app)
    result=client.post('/api/market/momentum-breakdown/watch',json={'enabled':True})
    assert result.status_code==200
    app.state.market_tick()
    watch=client.get('/api/market/watches').json()[0]
    assert watch['status']=='UNAVAILABLE' and watch['failures']==1 and watch['nextAttemptAt']>0
    other=TestClient(create_app(repo=repo))
    assert other.get('/api/market/watches').json()[0]==watch
    stopped=other.post('/api/market/momentum-breakdown/watch',json={'enabled':False}).json()
    assert not stopped['enabled']


def test_shadow_outcomes_isolated_between_repeated_runs(tmp_path):
    repo=SQLiteRepository(tmp_path/'outcomes.db')
    client=TestClient(create_app(repo=repo))
    counts=[]
    for _ in range(2):
        run=client.post('/api/replays',json={'datasetId':'momentum-breakdown'}).json()
        path='/api/replays/'+run['runId']
        client.post(path+'/advance',json={'steps':60})
        outcomes=client.get(path+'/audit').json()['audit']['maturedOutcomes']
        counts.append(len(outcomes))
    assert counts[0]>0 and counts[0]==counts[1]
