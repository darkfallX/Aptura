"use client";

import React, { useEffect } from "react";
import {
  AdaptationEvent,
  ReppoEvaluationRecord,
  formatUtcShort,
} from "@/lib/contracts";
import { Cpu, ShieldCheck, Scale, Sparkles, RefreshCw } from "lucide-react";

interface ThreeGatePipelineProps {
  event: AdaptationEvent;
  evalRecord: ReppoEvaluationRecord | null;
  busy: boolean;
  onTriggerAudit: (adaptationId: string) => void;
  onPollEval: (evalId: string) => void;
  onSeekCandle: (candleIndex: number) => void;
}

export default function ThreeGatePipeline({
  event,
  evalRecord,
  busy,
  onTriggerAudit,
  onPollEval,
  onSeekCandle,
}: ThreeGatePipelineProps) {
  const isPending = evalRecord?.status === "PENDING";

  useEffect(() => {
    if (!isPending || !evalRecord?.evalId) return;
    const timer = setInterval(() => {
      onPollEval(evalRecord.evalId);
    }, 4500);
    return () => clearInterval(timer);
  }, [isPending, evalRecord?.evalId, onPollEval]);

  const serv = event.servProposal;
  const val = event.validationResult;
  const servLive = serv?.provenance === "SERV_GENERATED";

  const oldMix = event.oldWeights.map((w) => `${Math.round(w * 100)}%`).join(" / ");
  const newMix = event.proposedWeights
    ? event.proposedWeights.map((w) => `${Math.round(w * 100)}%`).join(" / ")
    : "No change";

  const rubricEntries = evalRecord?.rubricScores
    ? Object.entries(evalRecord.rubricScores)
    : [];

  return (
    <section className="panel three-gate-panel" aria-label="Three-gate adaptation audit">
      <div className="panel-heading">
        <div>
          <span className="kicker">CAUSAL AUDIT PIPELINE</span>
          <h2>Three-Gate Adaptation Check</h2>
          <span className="muted">
            {event.fromVersion} → {event.proposedVersion || "Retained"} · Detected{" "}
            {formatUtcShort(event.detectedAt)}
          </span>
        </div>
        <div className="detail-actions" style={{ margin: 0 }}>
          <button className="btn" onClick={() => onSeekCandle(event.candleIndex)}>
            Go to candle #{event.candleIndex}
          </button>
          <button
            className="btn btn-dark"
            disabled={busy}
            onClick={() => onTriggerAudit(event.id)}
          >
            <Sparkles size={15} />
            {busy ? "Running audit…" : "Run Live SERV + Reppo Audit"}
          </button>
        </div>
      </div>

      <div className="gate-grid">
        {/* Gate 1: OpenServ SERV Reasoning */}
        <article className="gate-card">
          <div className="gate-header">
            <span className="gate-title">
              <Cpu size={16} /> Gate 1 · SERV Reasoning
            </span>
            <span className={`badge ${servLive ? "live-connected" : ""}`}>
              {servLive ? "SERV GENERATED" : "DETERMINISTIC FALLBACK"}
            </span>
          </div>
          <p className="gate-body">
            {serv?.hypothesis || event.rationale}
          </p>
          <div className="gate-meta">
            <span>Model: {serv?.modelUsed || "local"}</span>
            {serv?.regimeDiagnosis && <span>Regime: {serv.regimeDiagnosis}</span>}
            {serv?.latencyMs != null && <span>{serv.latencyMs} ms</span>}
          </div>
          <details>
            <summary>Evidence &amp; uncertainties ({event.evidenceIds.length})</summary>
            <small>Cited IDs: {event.evidenceIds.join(", ")}</small>
            {serv?.assumptions?.map((a, idx) => (
              <p key={idx}>Assumption: {a}</p>
            ))}
            {serv?.uncertainties?.map((u, idx) => (
              <p key={idx}>Uncertainty: {u}</p>
            ))}
          </details>
        </article>

        {/* Gate 2: Deterministic Math & Risk Validation */}
        <article className="gate-card">
          <div className="gate-header">
            <span className="gate-title">
              <ShieldCheck size={16} /> Gate 2 · Causal Math Gate
            </span>
            <span className={`badge ${val?.passed ? "live-connected" : "badge-warn"}`}>
              {val?.passed ? "PASSED" : "REJECTED"}
            </span>
          </div>
          <p className="gate-body">
            Mix: <strong>{oldMix}</strong> → <strong>{newMix}</strong>
            {val && (
              <>
                {" "}
                ({val.pastSegmentDeltaPct >= 0 ? "+" : ""}
                {val.pastSegmentDeltaPct.toFixed(3)}% vs baseline over {val.validationWindowBars}{" "}
                past-only bars)
              </>
            )}
          </p>
          <div className="gate-meta">
            <span>Bounds [15–85%]: {val?.weightsInBounds ? "OK" : "FAIL"}</span>
            <span>Zero look-ahead: {val?.noFutureLeakage ? "OK" : "FAIL"}</span>
            <span>Cooldown: {val?.cooldownRespected ? "OK" : "WAIT"}</span>
          </div>
          <details>
            <summary>Validation summary</summary>
            <p>{val?.summary || event.rejectionReason || "Deterministic gate telemetry."}</p>
          </details>
          {val && <div key={event.id} className={`p-stamp gate-stamp on ${val.passed ? "ship" : ""}`} aria-hidden>{val.passed ? "PASSED" : "BLOCKED"}</div>}
        </article>

        {/* Gate 3: Reppo Eval Router */}
        <article className="gate-card">
          <div className="gate-header">
            <span className="gate-title">
              <Scale size={16} /> Gate 3 · Reppo Eval Panel
            </span>
            <span
              className={`badge ${
                evalRecord?.status === "SETTLED" && evalRecord?.route === "ship"
                  ? "live-connected"
                  : ""
              }`}
            >
              {evalRecord
                ? evalRecord.providerStatus || evalRecord.status
                : "NOT SUBMITTED"}
            </span>
          </div>
          {evalRecord ? (
            <>
              <p className="gate-body">
                {evalRecord.status === "PENDING"
                  ? "Queued on Reppo Eval Router (typically settles in 30–90s). Auto-polling…"
                  : evalRecord.critique || "No critique returned."}
              </p>
              <div className="gate-meta">
                <span>ID: {evalRecord.evalId}</span>
                {evalRecord.score != null && <span>Score: {evalRecord.score}/100</span>}
                {evalRecord.route && <span>Route: {evalRecord.route.toUpperCase()}</span>}
                {evalRecord.creditsCharged != null && (
                  <span>{evalRecord.creditsCharged} credits</span>
                )}
              </div>
              {rubricEntries.length > 0 && (
                <div className="rubric-list">
                  {rubricEntries.map(([k, v]) => (
                    <div key={k} className="rubric-row">
                      <span>{k}</span>
                      <strong>{v}</strong>
                    </div>
                  ))}
                </div>
              )}
              {evalRecord.status === "PENDING" && (
                <button
                  className="btn"
                  style={{ marginTop: "10px" }}
                  disabled={busy}
                  onClick={() => onPollEval(evalRecord.evalId)}
                >
                  <RefreshCw size={14} /> Refresh Reppo status
                </button>
              )}
            </>
          ) : (
            <p className="gate-body">
              Click <strong>Run Live SERV + Reppo Audit</strong> to send this adaptation’s
              sanitized telemetry to OpenServ SERV Reasoning and the Reppo evaluator panel.
            </p>
          )}
        </article>
      </div>
    </section>
  );
}
