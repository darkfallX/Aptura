"""Persistent live supervisor registry. Caller serializes state mutations."""
import time
import uuid
from app.replay.live_session import LiveSession, utc
from app.evaluation.workflow import new_job

class LiveSupervisors:
    def __init__(self, repo, catalog, serv, reppo):
        self.repo,self.catalog,self.serv,self.reppo = repo,catalog,serv,reppo
        self.sessions = {}

    def state_for(self, market_id=None, run_id=None):
        return next((s for s in self.repo.list_live_supervisors()
                     if (market_id and s['marketId']==market_id) or (run_id and s['runId']==run_id)),None)

    def resolve(self, run_id):
        state = self.state_for(run_id=run_id)
        if not state: return None
        observations = self.repo.live_observations(run_id)
        if not observations: return None
        session = self.sessions.get(run_id)
        commands = self.repo.list_activations(run_id)
        if session is None or session.cursor+1 != len(observations):
            metadata,_ = self.catalog.get_dataset(state['marketId'])
            session = LiveSession(run_id,metadata,observations,commands)
            saved = self.repo.get_snapshot(run_id)
            if saved and saved.cursor == session.cursor and (saved.equityCurve != session.snapshot().equityCurve or saved.dataset.sha256Hash != session.dataset.sha256Hash):
                raise ValueError('Live algorithm changed; cannot silently rewrite this run')
            self.sessions[run_id] = session
            self.repo.restore_outcomes(run_id,session.tracker.matured_outcomes)
        session.activation_commands = commands
        return session

    def observe(self, metadata, feed, now=None):
        now = int(time.time() if now is None else now)
        state = self.state_for(market_id=metadata.id)
        if state is None:
            state = {'marketId':metadata.id,'runId':'live_'+uuid.uuid4().hex,'enabled':True,
                     'startedAt':utc(now),'hadInterruption':False,'feedStatus':'WAITING'}
        state['lastPollAt'] = utc(now)
        state['feedStatus'] = feed['status']
        if not state['enabled']:
            self.repo.save_live_supervisor(state)
            return self.summary(state,now)
        if feed['status'] != 'FRESH' or not feed['trades'] or now-feed['trades'][0]['timestamp']>90 or feed['trades'][0]['timestamp']>now:
            state['hadInterruption'] = True
            if state['feedStatus'] == 'FRESH':
                state['feedStatus'] = 'STALE'
            self.repo.save_live_supervisor(state)
            return self.summary(state,now)
        trade = feed['trades'][0]
        observations = self.repo.live_observations(state['runId'])
        if observations and (trade['timestamp']<=observations[-1]['sourceTimestamp'] or now<=observations[-1]['receivedTimestamp']):
            self.repo.save_live_supervisor(state)
            return self.summary(state,now)
        observation = {'sequence':len(observations),'sourceId':trade['id'],
                       'sourceTimestamp':int(trade['timestamp']),'receivedTimestamp':now,
                       'priceUsd':trade['priceUsd'],'interrupted':state['hadInterruption']}
        state['hadInterruption'] = False
        self.repo.save_live_supervisor(state)
        # Journal before calculation: a crash can reconstruct exactly what was received.
        self.repo.add_live_observation(state['runId'],observation)
        session = self.sessions.get(state['runId'])
        if session and session.cursor+1==len(observations):
            session.activation_commands = self.repo.list_activations(state['runId'])
            session.append(observation)
        else:
            session = self.resolve(state['runId'])
        self.repo.save_snapshot(session.snapshot())
        existing = self.repo.list_jobs(session.run_id)
        for event in session.adaptation_events:
            if event.mechanism != 'FAST_MATHEMATICAL_SHIFT' or any(j['sourceEventId']==event.id for j in existing):
                continue
            candidate = event.model_copy(deep=True)
            candidate.oldWeights = [session.active_weights['momentum'],session.active_weights['reversal']]
            candidate.fromVersion = session.config_version
            job = new_job(session,candidate,self.serv.is_configured())
            job['live'] = True
            self.repo.save_job(job)
            existing.append(job)
        return self.summary(state,now)

    def summary(self, state, now=None):
        now = int(time.time() if now is None else now)
        session = self.resolve(state['runId'])
        jobs = self.repo.list_jobs(state['runId'])
        base = {'runId':state['runId'],'enabled':state['enabled'],'startedAt':state['startedAt'],
                'aiConfigured':self.serv.is_configured(),'reviewConfigured':self.reppo.is_configured(),
                'reviews':[{'id':j['id'],'state':j['state'],'message':j['message'],
                            'proposal':j['event'].get('servProposal'),'evaluation':j.get('evaluation')} for j in jobs[-5:]],
                'mode':'LIVE_PAPER_SUPERVISION','requiredObservations':20,
                'methodology':'Newly received trade-price samples only. Simulated fills require a source trade after the decision receipt time; 20 bps fee and 15 bps slippage per side. Samples are not complete OHLCV or an executable quote.'}
        if session is None:
            return dict(base,status='WAITING_FOR_DATA',observations=0,warmupProgress=0,
                        action='WAIT',reason='Waiting for a fresh market observation.',weights={'momentum':.6,'reversal':.4},
                        simulatedBalance=1000,simulatedReturnPct=0,tradeCount=0,maturedOutcomes=0,
                        events=[],strategies=[],lastDecisionAt=None,configVersion='v1.0.0')
        snapshot = session.snapshot()
        learning = len(session.strategy_window(session._all_candles))<20
        paused = not state['enabled'] or state['feedStatus']!='FRESH' or now-session._all_candles[-1].timestamp>90
        status = 'PAUSED' if paused else 'LEARNING' if learning else 'SUPERVISING'
        reason = 'Feed paused or delayed. No new simulated fills.' if paused else 'Learning from fresh price updates before taking a position.' if learning else snapshot.latestDecision.reason
        metrics = snapshot.metricsComparison['adaptive']
        return dict(base,status=status,observations=session.cursor+1,
            warmupProgress=min(20,len(session.strategy_window(session._all_candles))),
            action='WAIT' if paused or learning else snapshot.latestDecision.action,reason=reason,
            weights=snapshot.activeWeights,simulatedBalance=metrics.finalEquityUsd,
            simulatedReturnPct=metrics.netReturnPct,tradeCount=metrics.tradeCount,
            maturedOutcomes=len(session.tracker.matured_outcomes),
            events=[e.model_dump() for e in snapshot.adaptationEvents[-8:]],
            strategies=[{'id':k,'action':v.action,'reason':v.rationale,'weight':snapshot.activeWeights[k],
                         'evaluatedSignals':session.tracker.matured_counts[k],
                         'shadowUtilityPct':session.tracker.trailing_ewma[k]} for k,v in snapshot.latestSignals.items()],
            lastDecisionAt=snapshot.currentObservedAt,configVersion=snapshot.configVersion,
            sourceTime=utc(session.source_times[-1]))
