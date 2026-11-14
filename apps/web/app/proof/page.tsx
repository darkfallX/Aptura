"use client";

import { useState } from "react";
import { PaperFoot, PaperNav, Receipt, useInView, type Line } from "@/components/paper/Paper";
import { bounded, evaluation, pct, proof, rogue, shortId, signed, utc, type ProofCase } from "@/lib/proof";

function full(c: ProofCase): Line[] {
  const r = c.reppo;
  const out: Line[] = [
    { title: c.title },
    { k: "agent", v: c.agentName },
    { k: "market", v: c.dataset },
    { k: "momentum", v: `${pct(c.currentWeights.momentum)} → ${pct(c.proposedWeights.momentum)}`, tone: "strong" },
    { k: "reversal", v: `${pct(c.currentWeights.reversal)} → ${pct(c.proposedWeights.reversal)}`, tone: "strong" },
    { rule: true },
    { k: "serv", v: c.serv.provenance },
    { k: "model", v: c.serv.model },
    { k: "response", v: c.serv.responseId ?? "—" },
    { k: "latency", v: `${((c.serv.latencyMs ?? 0) / 1000).toFixed(1)} s` },
    { k: "regime", v: c.serv.regime ?? "—" },
    { k: "serv suggests", v: `${pct(c.serv.suggestedWeights.momentum)} / ${pct(c.serv.suggestedWeights.reversal)}`, tone: "strong" },
    { quote: `“${c.serv.hypothesis}”` },
    { rule: true },
    { k: "limit 15–85%", v: c.gate.weightsInBounds ? "ok" : "broken", tone: c.gate.weightsInBounds ? undefined : "hit" },
    { k: "no look-ahead", v: c.gate.noFutureLeakage ? "ok" : "failed" },
    { k: `past ${c.gate.validationWindowBars}h`, v: signed(c.gate.pastSegmentDeltaPct, 3), tone: "hit" },
    { k: "needs", v: "+0.060%" },
  ];
  if (c.rounds && c.rounds.length > 1) {
    for (const rd of c.rounds) out.push(
      { rule: true },
      { k: rd.round === 0 ? "round 0 · asked" : `round ${rd.round} · revised`, v: `${pct(rd.weights.momentum)} / ${pct(rd.weights.reversal)}`, tone: "strong" },
      { k: "  past 24h", v: signed(rd.pastWindowDeltaPct, 3), tone: rd.gatePassed ? undefined : "hit" },
      ...(rd.reppoEvalId ? [{ k: "  reppo", v: `${rd.reppoScore ?? "—"} · ${rd.reppoRoute ?? "—"} · ${shortId(rd.reppoEvalId, 10)}` }] : []),
      { k: "  verdict", v: rd.verdict, tone: rd.verdict === "SHIP" ? "strong" : "hit" },
    );
  }
  if (r) out.push(
    { rule: true },
    { k: "reppo eval", v: r.evalId },
    { k: "status", v: `${r.status} · ${r.provenance}` },
    { k: "score", v: `${r.score} / 100`, tone: "strong" },
    ...Object.entries(r.rubricScores).map(([k, v]) => ({ k: `  ${k}`, v: String(v) })),
    { k: "route", v: `${r.route} · ${r.confidence}` },
    { k: "credits", v: String(r.creditsCharged) },
    { k: "settled", v: r.settledAt ? utc(r.settledAt) : "—" },
  );
  return out;
}

type Check = { label: string; detail: string; ok: boolean | null };

async function sha256(buf: ArrayBuffer) {
  const h = await crypto.subtle.digest("SHA-256", buf);
  return Array.from(new Uint8Array(h)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

const inBounds = (w: { momentum: number; reversal: number }) =>
  w.momentum >= 0.15 && w.momentum <= 0.85 && w.reversal >= 0.15 && w.reversal <= 0.85 && Math.abs(w.momentum + w.reversal - 1) < 1e-6;

function CheckYourself() {
  const [checks, setChecks] = useState<Check[]>([]);
  const [running, setRunning] = useState(false);
  const pause = () => new Promise((r) => setTimeout(r, 380));
  async function run() {
    setRunning(true);
    const out: Check[] = [];
    const push = async (c: Check) => { out.push(c); setChecks([...out]); await pause(); };
    setChecks([]);
    try {
      const buf = await (await fetch("/proof/candles/momentum-breakdown.csv", { cache: "no-store" })).arrayBuffer();
      const got = await sha256(buf);
      const want = evaluation.candleFiles["momentum-breakdown"].sha256;
      await push({ label: "Candles are the ones we replayed", detail: `sha256 ${got.slice(0, 16)}…`, ok: got === want });
      const rows = new TextDecoder().decode(buf).trim().split("\n").slice(1).map((l) => l.split(","));
      const idx = rows.findIndex((r) => r[1] === bounded.observedAtUtc);
      await push({ label: "At least 24 closed hours before the decision", detail: `decision at candle #${idx} of ${rows.length}`, ok: idx >= 24 });
      const later = rows.slice(idx + 1).length;
      await push({ label: "The decision is earlier than the rest of the data", detail: `${later} later candles not used`, ok: idx >= 0 && later > 0 && bounded.gate.noFutureLeakage });
    } catch {
      await push({ label: "Candles are the ones we replayed", detail: "couldn't load the file", ok: false });
    }
    await push({ label: "95% reversal breaks the 15–85% limit", detail: `${pct(rogue.proposedWeights.reversal)} reversal`, ok: !inBounds(rogue.proposedWeights) && rogue.decision === "BLOCK" });
    const step = Math.abs(bounded.proposedWeights.momentum - bounded.currentWeights.momentum);
    await push({ label: "SERV's change stays within limits", detail: `${pct(bounded.proposedWeights.momentum)} / ${pct(bounded.proposedWeights.reversal)}, step ${Math.round(step * 100)} pts`, ok: inBounds(bounded.proposedWeights) && step <= 0.25 + 1e-9 });
    await push({ label: "+0.000% is below the +0.06% bar, so it's blocked", detail: `${signed(bounded.gate.pastSegmentDeltaPct, 3)} → ${bounded.decision}`, ok: bounded.gate.pastSegmentDeltaPct < 0.06 && bounded.decision === "BLOCK" });
    await push({ label: "Reppo review settled with a real ID", detail: bounded.reppo?.evalId ?? "—", ok: bounded.reppo?.status === "SETTLED" && bounded.reppo.provenance === "REPPO_LIVE" });
    setRunning(false);
  }
  return (
    <section className="p-check">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "end", gap: 20, flexWrap: "wrap" }}>
        <h2 className="p-h2">Don't trust us.<br /><em>Recheck it here.</em></h2>
        <button className="p-key" onClick={run} disabled={running}>{running ? "Checking…" : checks.length ? "Run again" : "Run 7 checks in your browser"}</button>
      </div>
      <ol className="p-check-list">
        {checks.map((c, i) => (
          <li key={i}>
            <span className={`p-mark-box ${c.ok === null ? "run" : c.ok ? "ok" : "bad"}`}>{c.ok ? "✓" : "✕"}</span>
            <span>{c.label}</span>
            <code>{c.detail}</code>
          </li>
        ))}
      </ol>
    </section>
  );
}

function stampNote(c: ProofCase) {
  if (c.decision === "SHIP") return c.reppo ? `REPPO ${c.reppo.score} + MATH` : "MATH GATE";
  if (c.case === "bounded") return "DESPITE REPPO 100";
  if (c.rounds && c.rounds.length > 1) return `AFTER ${c.rounds.length - 1} REVISIONS`;
  return "MATH GATE";
}

function Printed({ c }: { c: ProofCase }) {
  const [ref, seen] = useInView<HTMLDivElement>(0.15);
  return (
    <div className="p-printer" ref={ref}>
      <div className="p-slot" aria-hidden />
      <div className="p-feed">
        <Receipt run={seen} beatMs={70} head={[`№ ${c.requestId.toUpperCase()}`, utc(c.observedAtUtc)]} lines={full(c)} holes={c.reppo ? 3 : 2}
          stamp={c.decision === "BLOCK" ? "BLOCKED" : c.decision} stampNote={stampNote(c)} />
      </div>
    </div>
  );
}

export default function ProofPage() {
  return (
    <div className="p-page">
      <PaperNav />
      <main className="p-wrap">
        <h1 className="p-display" style={{ marginTop: 50 }}>{proof.cases.length} real calls.<br /><em>{proof.cases.length} receipts.</em></h1>
        <p className="p-lede" style={{ marginTop: 26 }}>Recorded {utc(proof.recordedAtUtc)} against live OpenServ SERV and Reppo.</p>
        <div className="p-proof-grid">
          {proof.cases.map((c) => <Printed key={c.case} c={c} />)}
        </div>
        <CheckYourself />
      </main>
      <PaperFoot />
    </div>
  );
}
