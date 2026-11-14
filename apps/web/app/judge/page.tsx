"use client";

import Link from "next/link";
import { useState } from "react";
import { PaperFoot, PaperNav, Receipt, type Line } from "@/components/paper/Paper";
import { pct, shortId, signed, utc } from "@/lib/proof";

const STUBS = [
  { min: 2, l: "A", h: "Watch a change get blocked", href: "/terminal?scenario=momentum-breakdown&autorun=1", code: "/terminal?scenario=momentum-breakdown&autorun=1" },
  { min: 1, l: "B", h: "Check the receipts yourself", href: "/proof", code: "/proof" },
  { min: 2, l: "C", h: "Be the bot", href: "#be-the-bot", code: "POST /api/v1/supervise" },
  { min: 1, l: "D", h: "See where we lose", href: "/evaluation", code: "/evaluation" },
];

type Resp = {
  requestId: string; observedAtUtc: string; decision: "SHIP" | "REVIEW" | "BLOCK"; datasetName: string;
  currentWeights: Record<string, number>; proposedWeights: Record<string, number>;
  servProposal: { provenance: string; responseId?: string | null };
  deterministicGate: { weightsInBounds: boolean; pastSegmentDeltaPct: number; cooldownRespected: boolean };
  rounds: { round: number; source: string; weights: Record<string, number>; verdict: string; pastWindowDeltaPct: number; gatePassed: boolean }[];
};

function BeTheBot() {
  const [mom, setMom] = useState(5);
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<Resp | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [n, setN] = useState(0);
  async function send() {
    setBusy(true); setErr(null); setRes(null);
    try {
      const r = await fetch("/api/v1/supervise", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ agentName: "judge-bot", datasetId: "momentum-breakdown", currentWeights: { momentum: 0.6, reversal: 0.4 }, proposedWeights: { momentum: mom / 100, reversal: 1 - mom / 100 }, runReppoReview: false, maxRevisions: 2 }),
      });
      if (r.status === 429) { setErr("Slow down: 6 sends per minute."); return; }
      if (!r.ok) throw new Error(`API answered ${r.status}`);
      setRes(await r.json()); setN((x) => x + 1);
    } catch {
      setErr("The API isn't reachable from this deployment. Run it locally: docker compose up");
    } finally { setBusy(false); }
  }
  const lines: Line[] = res ? [
    { title: <>judge-bot wants to rewrite itself</> },
    { k: "today", v: `${pct(res.currentWeights.momentum)} / ${pct(res.currentWeights.reversal)}` },
    { k: "serv", v: res.servProposal.provenance === "SERV_GENERATED" ? shortId(res.servProposal.responseId, 18) : "not configured" },
    ...res.rounds.flatMap((r): Line[] => [
      { rule: true },
      { k: r.round === 0 ? "you ask" : `revision ${r.round}`, v: `${pct(r.weights.momentum)} / ${pct(r.weights.reversal)}`, tone: "strong" },
      { k: "past 24h", v: `${signed(r.pastWindowDeltaPct, 3)} · ${r.verdict === "SHIP" ? "ship" : r.gatePassed ? r.verdict.toLowerCase() : "no"}`, tone: r.gatePassed ? undefined : "hit" },
    ]),
    { rule: true },
    { k: "needs", v: "+0.060% · 15–85% · step ≤ 25" },
  ] : [];
  return (
    <section id="be-the-bot" className="p-proof-grid" style={{ marginTop: 0 }}>
      <div>
        <h2 className="p-h2">Be the bot.<br /><em>Pick your panic.</em></h2>
        <div style={{ margin: "44px 0 30px" }}>
          <div className="p-mono" style={{ display: "flex", justifyContent: "space-between", fontSize: 13, color: "var(--desk-dim)", marginBottom: 14 }}>
            <span>momentum {mom}%</span><span>reversal {100 - mom}%</span>
          </div>
          <input aria-label="Proposed momentum weight" className="p-range" type="range" min={0} max={100} step={5} value={mom} onChange={(e) => setMom(Number(e.target.value))} />
          <div className="p-mono" style={{ fontSize: 12, color: "var(--desk-dim)", marginTop: 12 }}>today: 60% / 40%</div>
        </div>
        <button className="p-key" onClick={send} disabled={busy}>{busy ? "SERV is revising…" : "Send to Aptura"} <span className="arrow">→</span></button>
        {err && <p className="p-mono" role="alert" style={{ color: "var(--stamp)", marginTop: 22, fontSize: 13 }}>{err}</p>}
      </div>
      <div className="p-printer">
        <div className="p-slot" aria-hidden />
        <div className="p-feed" style={{ minHeight: 120 }}>
          {res && (
            <Receipt key={n} run head={[`№ ${res.requestId.slice(-6).toUpperCase()}`, utc(res.observedAtUtc)]} lines={lines} holes={2}
              stamp={res.decision === "BLOCK" ? "BLOCKED" : res.decision} stampNote={res.decision === "BLOCK" ? "MATH GATE" : undefined} beatMs={120} />
          )}
        </div>
      </div>
    </section>
  );
}

export default function JudgePage() {
  return (
    <div className="p-page">
      <PaperNav />
      <main className="p-wrap">
        <h1 className="p-display" style={{ marginTop: 50 }}>Six minutes.<br /><em>No sign-in.</em></h1>
        <div className="p-stubs">
          {STUBS.map((s) => (
            <Link key={s.l} href={s.href} className="p-stub">
              <div className="t"><b>{s.min}</b><span>MIN</span></div>
              <div className="b"><span className="l">PATH {s.l}</span><h3>{s.h}</h3><code>{s.code}</code></div>
            </Link>
          ))}
        </div>
        <BeTheBot />
      </main>
      <div style={{ height: 100 }} />
      <PaperFoot />
    </div>
  );
}
