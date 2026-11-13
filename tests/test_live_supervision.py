"""Synthetic streamed observations exercise causality; never seeded into production."""
from app.data.loader import DatasetCatalog
from app.replay.live_session import LiveSession, utc
from app.storage.repository import SQLiteRepository
from app.supervisor.live import LiveSupervisors
from app.evaluation.clients import SERVAnalyst, ReppoClient
from app.replay.comparisons import validate_weights
from app.domain.models import Signal

START=1800000000

def fixtures():
    meta,candles=DatasetCatalog().get_dataset('momentum-breakdown')
    observations=[{'sequence':i,'sourceId':f'test-only-{i}','sourceTimestamp':START+i*15-1,
        'receivedTimestamp':START+i*15,'priceUsd':c.close,'interrupted':False} for i,c in enumerate(candles)]
    return meta,observations


def test_live_starts_empty_of_history_and_warms_up_from_new_observations():
    meta,observations=fixtures()
    run=LiveSession('live-test',meta,observations[:1])
    assert run.cursor==0 and not run.brokers['adaptive'].orders
    assert run.snapshot().latestDecision.action in ('WAIT','AVOID')
    for observation in observations[1:19]:run.append(observation)
    assert not run.brokers['adaptive'].orders
    assert all(s.action=='WAIT' for s in run.snapshot().latestSignals.values())


def test_streamed_adaptation_and_restart_are_identical():
    meta,observations=fixtures()
    run=LiveSession('live-test',meta,observations[:1])
    for observation in observations[1:]:run.append(observation)
    assert run.adaptation_events
    assert any(e.status=='ACCEPTED' for e in run.adaptation_events)
    assert any(e.status=='REJECTED' for e in run.adaptation_events)
    assert all('HISTORICAL' not in e.provenanceBadges for e in run.adaptation_events)
    for order in run.snapshot().paperOrders:
        assert observations[order.fillCandleIndex]['sourceTimestamp'] > observations[order.decisionCandleIndex]['receivedTimestamp']
    restored=LiveSession('live-test',meta,observations)
    assert restored.snapshot().equityCurve==run.snapshot().equityCurve
    assert restored.snapshot().configHistory==run.snapshot().configHistory
    assert restored.dataset.sha256Hash==run.dataset.sha256Hash


def test_source_trade_must_occur_after_decision_not_just_arrive_later():
    meta,observations=fixtures();run=LiveSession('causal',meta,observations[:1])
    broker=run.brokers['adaptive']
    broker.queue_intent(0,utc(START),'BUY',.6,'v1','test')
    late=dict(observations[1],sourceTimestamp=START)
    run.observations.append(late);run.source_times.append(START);run.interruptions.append(False)
    run._all_candles.append(run.to_candle(late,1,meta))
    run.execute_broker(broker,1)
    assert not broker.orders
    later=dict(observations[2],sourceTimestamp=START+1)
    run.observations.append(later);run.source_times.append(START+1);run.interruptions.append(False)
    run._all_candles.append(run.to_candle(later,2,meta))
    run.execute_broker(broker,2)
    assert len(broker.orders)==1


def test_feed_interruption_cancels_orders_and_restarts_learning():
    meta,observations=fixtures();run=LiveSession('gap',meta,observations[:30])
    broker=run.brokers['cash']
    broker.queue_intent(run.cursor,utc(observations[29]['receivedTimestamp']),'BUY',.6,'v1','test')
    run.append(dict(observations[30],interrupted=True))
    assert not broker.orders
    assert run.snapshot().latestGuardian.status=='BLOCK'
    assert all(s.action=='WAIT' for s in run.snapshot().latestSignals.values())
    assert validate_weights(run,[.6,.4],[.4,.6]) is None


def test_feedback_waits_for_forward_entry_and_maturity():
    meta,observations=fixtures();run=LiveSession('feedback',meta,observations[:1])
    run.tracker.record_shadow_signal(Signal(id='test-signal',strategyId='momentum',observedAt=utc(START),
        candleIndex=0,action='BUY',strength=.8,indicators={},evidence=['test'],rationale='test'))
    for observation in observations[1:5]:run.append(observation)
    assert not run.tracker.matured_outcomes
    run.append(observations[5])
    assert run.tracker.matured_outcomes[0].maturedAtIndex==5


def test_live_registry_deduplication_restart_and_stale_pause(tmp_path):
    meta,observations=fixtures();catalog=DatasetCatalog();repo=SQLiteRepository(tmp_path/'live.db')
    registry=LiveSupervisors(repo,catalog,SERVAnalyst(api_key=''),ReppoClient(api_key=''))
    def feed(o):return {'status':'FRESH','trades':[{'id':o['sourceId'],'timestamp':o['sourceTimestamp'],'priceUsd':o['priceUsd']}]}
    for o in observations[:65]:registry.observe(meta,feed(o),o['receivedTimestamp'])
    state=registry.state_for(market_id=meta.id);run_id=state['runId']
    before=registry.resolve(run_id).snapshot()
    result=registry.observe(meta,feed(observations[64]),observations[64]['receivedTimestamp']+2)
    assert result['observations']==65
    assert result['maturedOutcomes']>0 and result['reviews']
    assert all(j['state']=='UNCONFIGURED' for j in result['reviews'])
    recovered=LiveSupervisors(repo,catalog,SERVAnalyst(api_key=''),ReppoClient(api_key=''))
    assert recovered.resolve(run_id).snapshot().equityCurve==before.equityCurve
    unavailable=registry.observe(meta,{'status':'UNAVAILABLE','trades':[]},observations[64]['receivedTimestamp']+10)
    assert unavailable['status']=='PAUSED' and unavailable['action']=='WAIT'
    assert len(repo.live_observations(run_id))==65
    assert len(repo.audit_trail(run_id)['decisions'])==65


def test_live_future_observations_do_not_change_validation():
    meta,observations=fixtures();run=LiveSession('future',meta,observations[:85])
    before=validate_weights(run,[.6,.4],[.4,.6])
    run._all_candles.extend([run.to_candle(dict(o,priceUsd=o['priceUsd']*10),i,meta)
                            for i,o in enumerate(observations[85:],85)])
    assert validate_weights(run,[.6,.4],[.4,.6])==before

def test_reviewed_live_change_activates_on_a_later_observation(tmp_path,monkeypatch):
    from app.evaluation.workflow import new_job,process_job
    import app.evaluation.workflow as workflow
    meta,observations=fixtures()
    reference=LiveSession('live-reference',meta,observations)
    accepted=next(e for e in reference.adaptation_events if e.status=='ACCEPTED')
    index=accepted.candleIndex
    run=LiveSession('live-reviewed',meta,observations[:index])
    original=run.adaptation_engine.check_and_propose
    run.adaptation_engine.check_and_propose=lambda **kwargs:None
    run.append(observations[index]);run.adaptation_engine.check_and_propose=original
    event=accepted.model_copy(update={'runId':run.run_id})
    repo=SQLiteRepository(tmp_path/'review.db')
    job=new_job(run,event,True);repo.save_job(job)
    class Analyst:
        def generate_proposal(self,*args):return event.servProposal.model_copy(update={'provenance':'SERV_GENERATED'})
    class Reviewer:
        def submit_evaluation(self,event,name):return ReppoClient(api_key='').submit_evaluation(event,name).model_copy(update={'status':'PENDING','provenance':'REPPO_LIVE','evalId':'explicit-test-review'})
        def poll_evaluation(self,record):return record.model_copy(update={'status':'SETTLED','decision':'accept','score':90})
    monkeypatch.setattr(workflow.time,'time',lambda:observations[index]['receivedTimestamp'])
    process_job(job,run,repo,Analyst(),Reviewer())
    process_job(job,run,repo,Analyst(),Reviewer())
    job['nextAttemptAt']=0
    previous=run.config_version
    process_job(job,run,repo,Analyst(),Reviewer())
    assert job['state']=='SCHEDULED',job['message']
    assert run.config_version==previous
    run.append(observations[index+1])
    assert run.config_version!=previous
    process_job(job,run,repo,Analyst(),Reviewer())
    assert job['state']=='ACTIVATED'


def test_live_activation_commands_reconstruct_and_cancel_on_interruption(tmp_path):
    meta,observations=fixtures();run=LiveSession('command',meta,observations[:80])
    event=run.adaptation_events[0].model_copy(deep=True)
    event.id='test-command';event.status='ACCEPTED';event.mechanism='REVIEWED_PROPOSAL'
    event.fromVersion=run.config_version;event.proposedVersion=f'v1.{run.version_counter}.0'
    event.candleIndex=80;event.proposedWeights=[.4,.6]
    command={'id':event.id,'runId':run.run_id,'candleIndex':80,'event':event.model_dump()}
    run.activation_commands.append(command);run.append(observations[80])
    restored=LiveSession('command',meta,observations[:81],[command])
    assert restored.snapshot().equityCurve==run.snapshot().equityCurve
    assert restored.snapshot().configHistory==run.snapshot().configHistory
    interrupted=LiveSession('command',meta,observations[:80],[command])
    previous=interrupted.config_version
    interrupted.append(dict(observations[80],interrupted=True))
    assert interrupted.config_version==previous
    assert interrupted.adaptation_events[-1].status=='REJECTED'

def test_live_api_and_background_tick_share_the_same_supervisor(tmp_path,monkeypatch):
    import app.main as main
    from fastapi.testclient import TestClient
    meta,observations=fixtures();index=[0]
    monkeypatch.setattr(main.time,'time',lambda:observations[index[0]]['receivedTimestamp'])
    def feed(self,metadata):
        o=observations[index[0]]
        return {'status':'FRESH','name':metadata.baseAsset,'trades':[{'id':o['sourceId'],
            'timestamp':o['sourceTimestamp'],'priceUsd':o['priceUsd']}], 'priceUsd':o['priceUsd']}
    monkeypatch.setattr(main.LiveMarket,'snapshot',feed)
    repo=SQLiteRepository(tmp_path/'api-live.db');app=main.create_app(repo=repo)
    client=TestClient(app)
    first=client.get('/api/live/momentum-breakdown').json()['supervisor']
    assert first['observations']==1 and first['status']=='LEARNING'
    index[0]=1;app.state.supervision_tick()
    second=client.get('/api/live/momentum-breakdown').json()['supervisor']
    assert second['observations']==2 and second['runId']==first['runId']
    paused=client.post('/api/live/momentum-breakdown/supervision',json={'enabled':False}).json()
    assert paused['status']=='PAUSED'
    index[0]=2;app.state.supervision_tick()
    assert client.get('/api/live/momentum-breakdown').json()['supervisor']['observations']==2
    assert client.post('/api/replays/'+first['runId']+'/advance',json={'steps':1}).status_code==409
    client.post('/api/live/momentum-breakdown/supervision',json={'enabled':True})
    index[0]=3;app.state.supervision_tick()
    state=client.get('/api/live/momentum-breakdown').json()['supervisor']
    assert state['observations']==3 and state['warmupProgress']==1
    audit=client.get('/api/replays/'+state['runId']+'/audit').json()
    assert len(audit['audit']['liveObservations'])==3


def test_supervisor_rejects_future_source_timestamp_even_with_fresh_label(tmp_path):
    meta,observations=fixtures()
    repo=SQLiteRepository(tmp_path/'future-source.db')
    registry=LiveSupervisors(repo,DatasetCatalog(),SERVAnalyst(api_key=''),ReppoClient(api_key=''))
    state=registry.observe(meta,{'status':'FRESH','trades':[{'id':'future','timestamp':START+3,'priceUsd':.01}]},START)
    assert state['observations']==0 and state['action']=='WAIT'
    assert not repo.live_observations(state['runId'])
