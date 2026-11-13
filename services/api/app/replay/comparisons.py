"""Causal fixed-policy branches. Every branch uses the same broker and risk rules."""
from copy import deepcopy
from app.supervisor.engine import AdaptiveSupervisor, RiskGuardian


def advance_policy(session, broker, weights, index):
    visible = session._all_candles[:index + 1]
    candle = visible[-1]
    if session.is_live:
        broker.preserve_pending = True
        broker.annualization_factor = 1
    session.execute_broker(broker, index)
    signals = session.signals_by_bar[index]
    guardian = session.assess_risk(visible, broker)
    decision = AdaptiveSupervisor.decide(session.run_id, candle, 'comparison', weights,
        signals['momentum'], signals['reversal'], guardian, broker.has_open_position())
    if session.is_live and decision.action not in ('BUY', 'EXIT'):
        broker.pending_intent = None
    if decision.action in ('BUY', 'EXIT'):
        sizing = session.POSITION_SIZING[session.risk_profile]
        broker.queue_intent(index, candle.observedAt, 'BUY' if decision.action == 'BUY' else 'SELL',
            sizing['allow'] if guardian.status == 'ALLOW' else sizing['caution'], 'comparison', decision.reason)
    broker.mark_to_market(candle.close)


def report(session):
    from app.replay.simulator import PaperBroker
    matched = PaperBroker('fixed_50_50', 'Frozen initial 60/40', session.initial_capital_usd, session.fee_bps, session.slippage_bps)
    for index in range(session.cursor + 1):
        advance_policy(session, matched, {'momentum': .6, 'reversal': .4}, index)
    interventions = []
    for branch in session.intervention_branches:
        old, new = deepcopy(branch['old']), deepcopy(branch['new'])
        event = branch['event']
        # State was captured after the current open fill, before the current decision.
        # Clear copied pending intents: each frozen policy makes its own decision.
        old.pending_intent = new.pending_intent = None
        for index in range(event.candleIndex, session.cursor + 1):
            advance_policy(session, old, dict(zip(('momentum', 'reversal'), event.oldWeights)), index)
            advance_policy(session, new, dict(zip(('momentum', 'reversal'), event.proposedWeights)), index)
        delta = new.equity_history[-1] - old.equity_history[-1]
        elapsed = session.cursor - event.candleIndex
        interventions.append({'eventId': event.id, 'activatedAt': event.activatedAt,
            'observedBars': elapsed, 'oldPolicyEquity': old.equity_history[-1],
            'newPolicyEquity': new.equity_history[-1], 'differenceUsd': round(delta, 4),
            'outcome': 'INSUFFICIENT_DATA' if elapsed < session.evaluation_horizon_bars else
                ('HELPED' if delta > .01 else 'HURT' if delta < -.01 else 'NO_DIFFERENCE'),
            'interpretation': 'Frozen old and new policies from identical state; later adaptations excluded.'})
    return {'runId': session.run_id, 'asOf': session.snapshot().currentObservedAt,
        'matchedBaseline': matched.compute_metrics().model_dump(),
        'interventions': interventions, 'strategyHealth': session.snapshot().strategyPerformance}


def validate_weights(session, old_weights, candidate_weights):
    """Paired cash-start portfolios on reserved bars; pre-window history warms indicators only."""
    from app.replay.simulator import PaperBroker
    start = session.cursor - 23
    if session.is_live and not session.tracker.valid_segment(session._all_candles[max(0,start):session.cursor+1]):
        return None
    if start < session.warmup_bars:
        return None
    returns = []
    for weights in (old_weights, candidate_weights):
        broker = PaperBroker('fixed_50_50', 'Validation', session.initial_capital_usd,
                             session.fee_bps, session.slippage_bps)
        for index in range(start, session.cursor + 1):
            advance_policy(session, broker, dict(zip(('momentum', 'reversal'), weights)), index)
        # Liquidation friction included for an open ending position; no future bar read.
        equity = broker.current_equity(session._all_candles[session.cursor].close)
        if broker.has_open_position():
            value = broker.position_qty * session._all_candles[session.cursor].close
            equity -= value * (1 - (1 - session.slippage_bps / 10000) * (1 - session.fee_bps / 10000))
        returns.append((equity / session.initial_capital_usd - 1) * 100)
    return returns[0], returns[1], 24
