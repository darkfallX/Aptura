"""Adaptive supervision over append-only observations received from the live feed.

An observation is one newly reported trade price, NOT an OHLCV candle. No older
trades are backfilled into a running portfolio. Receipt times govern decisions;
a fill requires a source trade strictly later than the decision receipt time.
"""
from datetime import datetime, timezone
import hashlib
import json
from app.domain.models import Candle
from app.replay.simulator import ReplaySession
from app.supervisor.engine import FeedbackTracker, RiskGuardian


def utc(timestamp):
    return datetime.fromtimestamp(timestamp, timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


class LiveFeedback(FeedbackTracker):
    def __init__(self, source_times, interruptions, **kwargs):
        super().__init__(**kwargs)
        self.source_times, self.interruptions = source_times, interruptions

    def execution_indices(self, signal, visible):
        issued = visible[signal.candleIndex].timestamp
        entry = next((i for i in range(signal.candleIndex + 1, len(visible))
                      if self.source_times[i] > issued and visible[i].timestamp-issued <= 90), None)
        return (entry, entry + self.horizon_bars) if entry is not None else None

    def mature_eligible_signals(self, visible):
        if visible:
            self.pending_signals = [s for s in self.pending_signals
                if self.execution_indices(s, visible) is not None
                or visible[-1].timestamp - visible[s.candleIndex].timestamp <= 90]
        return super().mature_eligible_signals(visible)

    def valid_segment(self, segment):
        return (all(0 < b.timestamp-a.timestamp <= 90 for a,b in zip(segment,segment[1:]))
                and not any(self.interruptions[c.index] for c in segment[1:]))


class LiveSession(ReplaySession):
    def __init__(self, run_id, metadata, observations, activation_commands=None):
        if not observations:
            raise ValueError('A live session needs its first real observation')
        self.is_live = True
        self.observations = observations
        self.source_times = [o['sourceTimestamp'] for o in observations]
        self.interruptions = [o.get('interrupted',False) for o in observations]
        candles = [self.to_candle(o, i, metadata) for i,o in enumerate(observations)]
        meta = metadata.model_copy(deep=True)
        meta.id = run_id
        meta.name = metadata.baseAsset + ' live observations'
        meta.source = 'GeckoTerminal received trade-price samples (not OHLCV)'
        meta.timeframe = 'observed-trade'
        meta.startTimeUtc = candles[0].observedAt
        meta.endTimeUtc = candles[-1].observedAt
        meta.candleCount = len(candles)
        meta.sha256Hash = self.observation_hash()
        meta.sourceUrl = f'https://api.geckoterminal.com/api/v2/networks/solana/pools/{metadata.poolAddress}/trades'
        meta.scenarioLabel = 'Live supervision'
        meta.description = 'Append-only received price observations with simulated execution.'
        meta.regimeSummary = 'Unclassified live market'
        meta.fetchedAtUtc = candles[-1].observedAt
        meta.recommended = False
        super().__init__(run_id, meta, candles, activation_commands=activation_commands)
        for broker in self.brokers.values():
            broker.preserve_pending = True
            broker.annualization_factor = 1
        # Reconstruct through received observations only; never request a provider.
        while self.cursor < len(candles)-1:
            self._step_one_bar()
        self.status = 'RUNNING'

    def observation_hash(self):
        return hashlib.sha256(json.dumps(self.observations,sort_keys=True,separators=(',',':')).encode()).hexdigest()

    @staticmethod
    def to_candle(observation, index, metadata):
        price = observation['priceUsd']
        return Candle(index=index,timestamp=observation['receivedTimestamp'],
            observedAt=utc(observation['receivedTimestamp']),open=price,high=price,low=price,close=price,
            volume=0,poolId=metadata.poolAddress,source='Received trade-price sample, not OHLCV',
            timeframe='observed-trade',isClosed=True)

    def make_tracker(self, **kwargs):
        return LiveFeedback(self.source_times,self.interruptions,**kwargs)

    def append(self, observation):
        if observation['sourceTimestamp'] <= self.source_times[-1] or observation['receivedTimestamp'] <= self._all_candles[-1].timestamp:
            return False
        self.observations.append(observation)
        self.source_times.append(observation['sourceTimestamp'])
        self.interruptions.append(observation.get('interrupted',False))
        self._all_candles.append(self.to_candle(observation,len(self._all_candles),self.dataset))
        self.dataset.sha256Hash = self.observation_hash()
        self.dataset.fetchedAtUtc = utc(observation["receivedTimestamp"])
        self.dataset.candleCount = len(self._all_candles)
        self.dataset.endTimeUtc = self._all_candles[-1].observedAt
        self._step_one_bar()
        self.status = 'RUNNING'
        return True

    def execute_broker(self, broker, index):
        candle = self._all_candles[index]
        broker.preserve_pending = True
        if self.interruptions[index] or (index and candle.timestamp-self._all_candles[index-1].timestamp>90):
            broker.pending_intent = None
        intent = broker.pending_intent
        if intent:
            decision_time = datetime.fromisoformat(intent.decision_observed_at.replace('Z','+00:00')).timestamp()
            if candle.timestamp-decision_time>90:
                broker.pending_intent = None
                return None
            if self.source_times[index] <= decision_time:
                return None
        return broker.execute_pending_at_open(self.run_id,candle)

    def strategy_window(self, visible):
        start = 0
        for i in range(1,len(visible)):
            if self.interruptions[i] or visible[i].timestamp-visible[i-1].timestamp>90:
                start = i
        return visible[start:]

    def assess_risk(self, visible, broker):
        assessment = RiskGuardian.assess(visible,broker.current_exposure_pct(visible[-1].close),
                                         self.risk_profile,expected_interval_sec=None)
        assessment.evidenceIds = [e for e in assessment.evidenceIds if 'vratio' not in e and 'range' not in e]
        if self.interruptions[visible[-1].index]:
            assessment.status = 'BLOCK'
            assessment.dataCompletenessOk = False
            assessment.reasons = ['Live feed interruption: pending orders cancelled; wait for fresh continuous observations.']
        elif len(self.strategy_window(visible)) < self.warmup_bars:
            assessment.status = 'BLOCK'
            assessment.reasons = ['Learning from fresh observations before risking simulated money.']
        elif assessment.status == 'ALLOW':
            assessment.reasons = ['Recent observed price variation is within limits. Liquidity and complete interval volume are not measured.']
        return assessment
