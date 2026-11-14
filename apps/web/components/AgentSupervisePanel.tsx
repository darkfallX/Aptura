"use client";

import React, { useState } from "react";
import {
  DatasetMetadata,
  SuperviseResponse,
  runSuperviseService,
} from "@/lib/contracts";
import { Terminal, Play } from "lucide-react";

interface AgentSupervisePanelProps {
  datasets: DatasetMetadata[];
  defaultDatasetId: string;
}

export default function AgentSupervisePanel({
  datasets,
  defaultDatasetId,
}: AgentSupervisePanelProps) {
  const [agentName, setAgentName] = useState("solana-alpha-agent");
  const [datasetId, setDatasetId] = useState(defaultDatasetId || "momentum-breakdown");
  const [mode, setMode] = useState<"serv_auto" | "rogue_unbounded">("serv_auto");
  const [runReppo, setRunReppo] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<SuperviseResponse | null>(null);

  const handleRun = async () => {
    setBusy(true);
    setError(null);
    try {
      const resp = await runSuperviseService({
        agentName: agentName.trim() || "external-trading-agent",
        datasetId,
        currentWeights: { momentum: 0.6, reversal: 0.4 },
        proposedWeights:
          mode === "rogue_unbounded"
            ? { momentum: 0.05, reversal: 0.95 }
            : undefined,
        rationale:
          mode === "rogue_unbounded"
            ? "Go 95% reversal immediately based on intuition."
            : "Synthesize bounded adaptation from matured shadow returns.",
        runReppoReview: runReppo,
      });
      setResult(resp);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Supervise call failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="panel supervise-panel" aria-label="Supervisor-as-a-Service API">
      <div className="panel-heading">
        <div>
          <span className="kicker">OPENSERV AGENT SERVICE · POST /api/v1/supervise</span>
          <h2>Supervisor-as-a-Service</h2>
          <span className="muted">
            External trading bots send proposed weight changes here to receive a causal SHIP /
            REVIEW / BLOCK verdict before touching strategy config.
          </span>
        </div>
        <button className="btn btn-dark" disabled={busy} onClick={handleRun}>
          <Play size={15} />
          {busy ? "Supervising…" : "Call /api/v1/supervise"}
        </button>
      </div>

      <div className="supervise-controls">
        <label>
          <span>Calling agent</span>
          <input
            type="text"
            value={agentName}
            onChange={(e) => setAgentName(e.target.value)}
          />
        </label>
        <label>
          <span>Market telemetry</span>
          <select value={datasetId} onChange={(e) => setDatasetId(e.target.value)}>
            {datasets.map((d) => (
              <option key={d.id} value={d.id}>
                {d.scenarioLabel} · {d.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          <span>Proposal mode</span>
          <select
            value={mode}
            onChange={(e) =>
              setMode(e.target.value as "serv_auto" | "rogue_unbounded")
            }
          >
            <option value="serv_auto">SERV Reasoning proposes bounded weights</option>
            <option value="rogue_unbounded">Test rogue agent (95% reversal → BLOCK)</option>
          </select>
        </label>
        <label className="checkbox-inline">
          <input
            type="checkbox"
            checked={runReppo}
            onChange={(e) => setRunReppo(e.target.checked)}
          />
          <span>Submit to Reppo panel ($0.22 / 440 credits)</span>
        </label>
      </div>

      {error && (
        <p role="alert" className="negative">
          {error}
        </p>
      )}

      {result && (
        <div className="supervise-result" key={result.requestId}>
          <div className={`p-stamp gate-stamp on ${result.decision === "SHIP" ? "ship" : ""}`} aria-hidden>{result.decision === "BLOCK" ? "BLOCKED" : result.decision}</div>
          <div className="supervise-result-top">
            <span
              className={`badge ${
                result.decision === "SHIP"
                  ? "live-connected"
                  : result.decision === "BLOCK"
                  ? "badge-warn"
                  : ""
              }`}
            >
              VERDICT: {result.decision}
            </span>
            <span>
              {result.agentName} · {result.datasetName} · Bar #{result.cursorIndex}
            </span>
            <span>
              SERV: {result.servProposal.provenance} ({result.servProposal.modelUsed})
            </span>
          </div>
          <p>{result.summary}</p>
          <div className="gate-meta">
            <span>
              Proposed: {Math.round((result.proposedWeights.momentum ?? 0) * 100)}% /{" "}
              {Math.round((result.proposedWeights.reversal ?? 0) * 100)}%
            </span>
            <span>
              24-bar delta: {result.deterministicGate.pastSegmentDeltaPct >= 0 ? "+" : ""}
              {result.deterministicGate.pastSegmentDeltaPct.toFixed(3)}%
            </span>
            <span>
              Math gate: ${Number(result.unitEconomics.localMathGateUsd ?? 0).toFixed(2)}
            </span>
            {result.reppoEvaluation && (
              <span>
                Reppo ID: {result.reppoEvaluation.evalId} ({result.reppoEvaluation.status})
              </span>
            )}
          </div>
        </div>
      )}

      <details>
        <summary>
          <span style={{ display: "inline-flex", alignItems: "center", gap: "8px" }}>
            <Terminal size={14} /> OpenServ capability contract (`GET /api/agent/manifest`)
          </span>
        </summary>
        <p>
          Other OpenServ agents can invoke <code>POST /api/v1/supervise</code> with{" "}
          <code>agentName</code>, <code>datasetId</code>, <code>currentWeights</code>, and
          optional <code>proposedWeights</code> to enforce bounded weights, 24-bar causal
          backtest validation, and asynchronous Reppo scoring.
        </p>
      </details>
    </section>
  );
}
