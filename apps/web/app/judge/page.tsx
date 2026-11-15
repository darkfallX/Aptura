"use client";

import Link from "next/link";
import { useState } from "react";
import { ArrowDown, Flag } from "lucide-react";
import { MixBar, Page, StatusIcon } from "@/components/x/Shell";
import { signed } from "@/lib/proof";

const PATHS = [
  { min: 2, h: "Watch a change get blocked", href: "/terminal?scenario=momentum-breakdown&autorun=1" },
  { min: 1, h: "Read a request end to end", href: "/requests/revise" },
  { min: 1, h: "Verify the receipts", href: "/proof" },
  { min: 1, h: "See where it loses", href: "/evaluation" },
];

type Round = { round: number; weights: { momentum: number; reversal: number }; verdict: string; pastWindowDeltaPct: number; gatePassed: boolean; hypothesis: string };
type Resp = { requestId: string; decision: "SHIP" | "REVIEW" | "BLOCK"; servProposal: { provenance: string; responseId?: string | null }; deterministicGate: { passed: boolean; pastSegmentDeltaPct: number }; rounds: Round[]; improvement?: { chosenRound?: number } };
type Phase = "idle" | "running" | "done" | "error";

export default function TryItPage() {
  const [mom, setMom] = useState(5);
  const [phase, setPhase] = useState<Phase>("idle");
  const [res, setRes] = useState<Resp | null>(null);
  const [err, setErr] = useState("");
  const inside = mom >= 15 && mom <= 85;
  const step = Math.abs(mom - 60);
  async function send() {
    setPhase("running"); setRes(null); setErr("");
    try {
      const r = await fetch("/api/v1/supervise", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ agentName: "judge-bot", datasetId: "momentum-breakdown", currentWeights: { momentum: 0.6, reversal: 0.4 }, proposedWeights: { momentum: mom / 100, reversal: 1 - mom / 100 }, runReppoReview: false, maxRevisions: 2 }),
      });
      if (r.status === 429) { setErr("Limit: 6 per minute."); setPhase("error"); return; }
      if (!r.ok) throw new Error(String(r.status));
      setRes(await r.json()); setPhase("done");
    } catch {
      setErr("API offline. Run docker compose up."); setPhase("error");
    }
  }
  const first = res?.rounds?.[0];
  const servOk = res?.servProposal.provenance === "SERV_GENERATED";
  const checks: { name: string; tone: "ok" | "no" | "warn" | "idle"; note: string; det: string }[] = [
    { name: "SERV reasoning", tone: !res ? "idle" : servOk ? "ok" : "warn", note: !res ? "" : servOk ? "live" : "off", det: res && servOk ? (res.servProposal.responseId ?? "").slice(0, 12) + "…" : "" },
    { name: "Math gate", tone: !first ? "idle" : first.gatePassed ? "ok" : "no", note: !first ? "" : "needs +0.06%", det: first ? signed(first.pastWindowDeltaPct, 3) : "" },
    { name: "Reppo review", tone: "idle", note: "off here", det: "" },
  ];
  const tone = res?.decision === "SHIP" ? "ok" : res?.decision === "REVIEW" ? "warn" : "no";
  return (
    <Page>
      <div className="a-head">
        <div>
          <h1>Open a request</h1>
        </div>
      </div>
      <div className="a-compose">
        <div>
          <div className="x-card">
            <div className="a-req-head">
              <div><b>judge-bot wants to change its mix</b><small>BONK / SOL</small></div>
              <span className={`x-pill ${res ? tone : "neutral"}`}>{res ? (res.decision === "BLOCK" ? "Blocked" : res.decision === "REVIEW" ? "Needs review" : "Shipped") : phase === "running" ? "Checking" : "Draft"}</span>
            </div>
            <div className="a-diff a-mix">
              <MixBar large label="Today" mix={{ momentum: 0.6, reversal: 0.4 }} animate={false} />
              <MixBar large label="Wants" mix={{ momentum: mom / 100, reversal: 1 - mom / 100 }} animate={false} />
            </div>
            <div className="x-card-pad" style={{ borderTop: ".8px solid var(--line-soft)" }}>
              <input aria-label="Momentum share you want" className="x-range" type="range" min={0} max={100} step={5} value={mom} onChange={(e) => setMom(Number(e.target.value))} />
            </div>
            <div className="x-card-foot" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
              <span style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                <span className={`x-pill ${inside ? "ok" : "no"}`}>{inside ? "Inside 15–85%" : "Outside 15–85%"}</span>
                <span className={`x-pill ${step <= 25 ? "ok" : "no"}`}>Step {step} pts</span>
              </span>
              <button className="x-btn sm" onClick={send} disabled={phase === "running"}>{phase === "running" ? "Checking…" : "Send request"}</button>
            </div>
          </div>
          {err && <p className="x-down" role="alert" style={{ marginTop: 12, fontSize: 14 }}>{err}</p>}
          {res && (
            <div className="a-tl" style={{ marginTop: 28 }}>
              {res.rounds.map((r, i) => (
                <div key={i} className="a-ev" style={{ ["--i" as string]: i * 2 }}>
                  <span className={`a-ev-icon ${r.gatePassed ? "ok" : "no"}`}>{i === 0 ? "1" : <ArrowDown />}</span>
                  <div className="a-ev-head"><b>{i === 0 ? "Your ask" : `SERV revision ${i}`}</b><span className="x-mute">{Math.round(r.weights.momentum * 100)} / {Math.round(r.weights.reversal * 100)}</span><span className={r.gatePassed ? "x-up" : "x-down"}>{signed(r.pastWindowDeltaPct, 3)}</span></div>
                  <div className="a-ev-body"><p style={{ color: "var(--ink-2)" }}>{r.hypothesis}</p></div>
                </div>
              ))}
              <div className="a-ev" style={{ ["--i" as string]: res.rounds.length * 2 }}>
                <span className={`a-ev-icon ${tone}`}><Flag /></span>
                <div className="a-ev-head"><b>Verdict</b></div>
                <div className="a-ev-body"><div className={`a-final ${tone}`}>{res.decision === "BLOCK" ? "Blocked" : res.decision === "REVIEW" ? "Needs review" : "Shipped"}</div></div>
              </div>
            </div>
          )}
        </div>
        <aside className="a-side">
          <div className="x-card">
            <div className="a-side-title"><span>Checks</span><span className="x-mute" style={{ fontWeight: 500, fontSize: 13 }}>{phase === "running" ? "running" : res ? "done" : ""}</span></div>
            {checks.map((c, i) => (
              <div className="a-check" key={c.name}>
                {phase === "running" && i < 2 ? <span className="a-spin" aria-hidden /> : <StatusIcon tone={c.tone} />}
                <span><b>{c.name}</b>{c.note && phase !== "running" && <small>{c.note}</small>}</span>
                <span className="det" style={{ color: c.tone === "no" ? "var(--red-ink)" : c.tone === "ok" ? "var(--green-ink)" : "var(--mute)" }}>{c.det}</span>
              </div>
            ))}
          </div>
          <div className="x-card">
            <div className="a-side-title"><span>Judge path</span></div>
            {PATHS.map((p) => (
              <Link key={p.h} href={p.href} className="a-check" style={{ gridTemplateColumns: "1fr auto" }}>
                <span><b>{p.h}</b></span><span className="det x-mute">{p.min} min</span>
              </Link>
            ))}
          </div>
        </aside>
      </div>
    </Page>
  );
}
