"""Durable external review state machine. Provider verdicts never bypass local gates."""
from datetime import datetime, timezone
import time
import uuid
from app.domain.models import AdaptationEvent, ReppoEvaluationRecord
from app.replay.comparisons import validate_weights


def new_job(session, event, configured):
    return {'id': 'review_' + uuid.uuid4().hex, 'runId': session.run_id,
            'state': 'QUEUED' if configured else 'UNCONFIGURED',
            'sourceEventId': event.id, 'event': event.model_dump(),
            'baseVersion': session.config_version, 'requestedCursor': session.cursor,
            'createdAt': datetime.now(timezone.utc).isoformat(), 'nextAttemptAt': 0,
            'message': 'Awaiting analyst' if configured else 'Configure SERV and Reppo server credentials to request a review.'}


def process_job(job, session, repo, serv, reppo, finalize=None):
    """One bounded transition per worker tick; persisted before external submission.

    SUBMITTING on recovery is ambiguous: never repeat a potentially paid POST.
    Users can reconcile the external account before explicitly requesting again.
    """
    state = job['state']
    event = AdaptationEvent.model_validate(job['event'])
    if state == 'SCHEDULED':
        applied = next((e for e in session.adaptation_events if e.id == job['id']), None)
        if applied:
            job.update(state='ACTIVATED' if applied.status == 'ACCEPTED' else 'REJECTED',
                       message='Reviewed configuration activated and persisted in the run history.' if applied.status == 'ACCEPTED' else applied.rejectionReason)
            repo.save_job(job)
        return
    if state == 'QUEUED':
        proposal = serv.generate_proposal(event.detectedAt, session.dataset.name,
            event.oldWeights, event.proposedWeights, event.momentumTrailingScore,
            event.reversalTrailingScore, event.maturedSampleCount, event.evidenceIds)
        event.id = job['id']
        event.mechanism = 'REVIEWED_PROPOSAL'
        event.servProposal = proposal
        event.proposedWeights = [proposal.suggestedWeights['momentum'], proposal.suggestedWeights['reversal']]
        event.status = 'PROPOSED'
        event.activatedAt = None
        event.evaluationId = None
        event.reppoStatus = None
        event.provenanceBadges = ['SERV GENERATED', 'LIVE OBSERVATIONS' if getattr(session,'is_live',False) else 'HISTORICAL']
        job['event'] = event.model_dump()
        if not proposal.schemaValid or proposal.provenance != 'SERV_GENERATED':
            job.update(state='REJECTED', message='No valid SERV proposal; deterministic fallback cannot enter external promotion.')
        else:
            job.update(state='READY_TO_SUBMIT', message='Validated analyst output; awaiting review slot.')
        repo.save_job(job)
        return
    if state == 'READY_TO_SUBMIT':
        job.update(state='SUBMITTING', message='Submitting to Reppo Eval Router; ambiguous delivery is never automatically repeated.')
        repo.save_job(job)
        record = reppo.submit_evaluation(event, session.dataset.name)
        repo.save_evaluation(record)
        job['evaluation'] = record.model_dump()
        event.evaluationId, event.reppoStatus = record.evalId, record.status
        job['event'] = event.model_dump()
        job['state'] = 'PENDING_REVIEW' if record.status in ('PENDING', 'SETTLED') else 'SUBMISSION_UNKNOWN' if record.status == 'FAILED' else record.status
        job['message'] = record.critique or 'External reasoning review queued on Reppo (30–90s); weights unchanged.'
        job['nextAttemptAt'] = time.time() + 5
        repo.save_job(job)
        return
    if state == 'SUBMITTING':
        job.update(state='SUBMISSION_UNKNOWN', message='Worker restarted during submission. Reconcile provider account before retrying.')
        repo.save_job(job)
        return
    if state != 'PENDING_REVIEW' or time.time() < job.get('nextAttemptAt', 0):
        return
    record = reppo.poll_evaluation(ReppoEvaluationRecord.model_validate(job['evaluation']))
    repo.save_evaluation(record)
    job['evaluation'] = record.model_dump()
    job['nextAttemptAt'] = time.time() + 5
    if record.status == 'PENDING':
        pstatus = record.providerStatus or 'PENDING'
        job['message'] = f'Reppo evaluation {pstatus} (usually 30–90s); replay can continue.'
        repo.save_job(job)
        return
    if finalize is not None:
        return finalize(job)
    if record.status != 'SETTLED' or record.decision != 'accept' or record.route not in ('ship', None):
        route_note = f' (route={record.route})' if record.route else ''
        job.update(state='REJECTED', message=f'Reppo review did not route to ship{route_note}; weights unchanged.')
        repo.save_job(job)
        return
    # A review is a new prospective intervention, never a retroactive rewrite.
    live = getattr(session, 'is_live', False)
    stale = session.config_version != job['baseVersion'] or session.cursor - job['requestedCursor'] > (120 if live else 24)
    stale = stale or (live and time.time() - session._all_candles[-1].timestamp > 90)
    if stale or (not live and session.cursor >= len(session._all_candles) - 1):
        job.update(state='EXPIRED', message='Run moved beyond this proposal or ended. Request a new review.')
        repo.save_job(job)
        return
    old = [session.active_weights['momentum'], session.active_weights['reversal']]
    selection = [o for o in session.tracker.matured_outcomes if o.maturedAtIndex < session.cursor - 23]
    gate = session.adaptation_engine.validate_proposal(session.cursor, old, event.proposedWeights,
        selection, event.servProposal.evidenceIds,
        session.cursor - session.adaptation_engine.last_accepted_bar >= session.adaptation_engine.cooldown_bars,
        lambda baseline, candidate: validate_weights(session, baseline, candidate))
    event.validationResult = gate
    job['event'] = event.model_dump()
    if not gate.passed:
        job.update(state='REJECTED', message='External review accepted; independent local validation rejected: ' + gate.summary)
    elif any(c['candleIndex'] == session.cursor + 1 for c in session.activation_commands):
        job.update(state='EXPIRED', message='Another configuration is already scheduled for the next bar.')
    else:
        event.status = 'ACCEPTED'
        event.fromVersion = session.config_version
        event.proposedVersion = f'v1.{session.version_counter}.0'
        event.oldWeights = old
        event.candleIndex = session.cursor + 1
        # Timestamp describes the last available observation, not an unseen bar.
        event.activatedAt = session.snapshot().currentObservedAt
        event.reppoStatus = 'SETTLED'
        event.provenanceBadges = ['SERV GENERATED', 'REPPO REVIEWED', 'LOCAL GATES PASSED']
        command = {'id': job['id'], 'runId': session.run_id, 'candleIndex': session.cursor + 1, 'event': event.model_dump()}
        repo.save_activation(command)
        session.activation_commands.append(command)
        job.update(state='SCHEDULED', event=event.model_dump(), message='Passed both gates; scheduled for the next replay decision.')
    repo.save_job(job)
