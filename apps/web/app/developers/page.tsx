"use client";

import Link from "next/link";
import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { Page } from "@/components/x/Shell";
import { revise } from "@/lib/proof";

const REQUEST = `curl -X POST /api/v1/supervise \\
  -H "Content-Type: application/json" \\
  -d '{
    "agentName": "your-bot",
    "datasetId": "momentum-breakdown",
    "currentWeights":  { "momentum": 0.60, "reversal": 0.40 },
    "proposedWeights": { "momentum": 0.05, "reversal": 0.95 },
    "maxRevisions": 2,
    "runReppoReview": false
  }'`;

const RESPONSE = revise?.rounds
  ? JSON.stringify({
      decision: revise.decision,
      rounds: revise.rounds.map((r) => ({ round: r.round, weights: r.weights, pastWindowDeltaPct: r.pastWindowDeltaPct, verdict: r.verdict })),
      improvement: { first: revise.improvement?.firstPastWindowDeltaPct, final: revise.improvement?.finalPastWindowDeltaPct },
      serv: { provenance: revise.serv.provenance, responseId: revise.serv.responseId },
    }, null, 2)
  : "";

const ENDPOINTS: [string, string, string][] = [
  ["POST", "/api/v1/supervise", "Check a change"],
  ["GET", "/api/agent/manifest", "Capabilities and pricing"],
  ["GET", "/api/proof", "Recorded live receipts"],
  ["GET", "/api/evaluation", "Replay results"],
  ["GET", "/api/proof/candles/{id}", "Raw candles + hash"],
];

function Code({ title, body }: { title: string; body: string }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try { await navigator.clipboard.writeText(body); setCopied(true); setTimeout(() => setCopied(false), 1400); } catch {}
  };
  return (
    <div className="x-card">
      <div className="a-side-title">
        <span>{title}</span>
        <button className="x-btn ghost sm" onClick={copy} aria-label={`Copy ${title}`}>{copied ? <Check size={14} /> : <Copy size={14} />}{copied ? "Copied" : "Copy"}</button>
      </div>
      <pre className="x-code" style={{ borderRadius: 0, margin: 0 }}>{body}</pre>
    </div>
  );
}

export default function DevelopersPage() {
  return (
    <Page>
      <div className="a-head">
        <div><h1>API</h1></div>
        <div className="a-head-actions"><Link href="/judge" className="x-btn">Try it</Link></div>
      </div>
      <div className="a-detail">
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div className="x-card">
            {ENDPOINTS.map(([m, path, what]) => (
              <div key={path} className="a-check a-endpoint" style={{ gridTemplateColumns: "56px minmax(0,1fr) auto" }}>
                <span className={`a-dot ${m === "POST" ? "pass" : "skip"}`} style={{ justifyContent: "center" }}>{m}</span>
                <code className="x-mono" style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{path}</code>
                <span className="det x-mute" style={{ fontWeight: 500 }}>{what}</span>
              </div>
            ))}
          </div>
          <Code title="Request" body={REQUEST} />
          {RESPONSE && <Code title="Response · recorded" body={RESPONSE} />}
        </div>
        <aside className="a-side">
          <div className="x-card">
            <div className="a-side-title"><span>Pricing</span><span className="x-pill neutral">proposed</span></div>
            <div className="a-check" style={{ gridTemplateColumns: "1fr auto" }}><span><b>Check</b><small>math gate</small></span><span className="det">Free</span></div>
            <div className="a-check" style={{ gridTemplateColumns: "1fr auto" }}><span><b>Reason</b><small>+ SERV revisions</small></span><span className="det">$0.05</span></div>
            <div className="a-check" style={{ gridTemplateColumns: "1fr auto" }}><span><b>Reviewed</b><small>+ Reppo</small></span><span className="det">$0.49</span></div>
          </div>
          <div className="x-card">
            <div className="a-side-title"><span>Limits</span></div>
            <div className="a-check" style={{ gridTemplateColumns: "1fr auto" }}><span><b>Requests</b></span><span className="det">6 / min</span></div>
            <div className="a-check" style={{ gridTemplateColumns: "1fr auto" }}><span><b>Revisions</b></span><span className="det">0–2</span></div>
            <div className="a-check" style={{ gridTemplateColumns: "1fr auto" }}><span><b>Reppo on public hosts</b></span><span className="det">admin key</span></div>
          </div>
          <div className="x-card">
            <div className="a-side-title"><span>For agents</span></div>
            <a className="a-check" style={{ gridTemplateColumns: "1fr auto" }} href="/llms.txt"><span><b>llms.txt</b></span><span className="det x-mute">text</span></a>
            <a className="a-check" style={{ gridTemplateColumns: "1fr auto" }} href="/api/agent/manifest"><span><b>Manifest</b></span><span className="det x-mute">JSON</span></a>
          </div>
        </aside>
      </div>
    </Page>
  );
}
