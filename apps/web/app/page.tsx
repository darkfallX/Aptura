"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { MixBar, Page, StatusIcon } from "@/components/x/Shell";
import { evaluation } from "@/lib/proof";
import { requests, stateTone, verdictLabel, verdictTone, type ChangeRequest } from "@/lib/requests";
import { RequestRow } from "@/components/x/RequestRow";

/** A request whose checks run one by one, then resolve into a verdict. Cycles through the live calls. */
function LiveRequest() {
  const shown = requests.filter((r) => r.id === "rogue" || r.id === "bounded");
  const [k, setK] = useState(0);
  const [step, setStep] = useState(0);
  const r: ChangeRequest = shown[k % shown.length];
  useEffect(() => {
    setStep(0);
    const ts = [1200, 2300, 3400, 4500].map((ms, i) => setTimeout(() => setStep(i + 1), ms));
    const next = setTimeout(() => setK((x) => x + 1), 10000);
    return () => { ts.forEach(clearTimeout); clearTimeout(next); };
  }, [k]);
  return (
    <div className="a-stack" aria-live="polite">
      <div className="x-card">
        <div className="a-req-head">
          <div>
            <b>{r.bot} wants to change its mix</b>
            <small>#{r.number} · {r.market}</small>
          </div>
          <span className={`x-pill ${step >= 4 ? verdictTone(r.verdict) : "neutral"} a-fade`}>{step >= 4 ? verdictLabel(r.verdict) : "Checking"}</span>
        </div>
        <div className="a-diff" style={{ borderBottom: ".8px solid var(--line-soft)" }}>
          <div className="a-mix">
            <MixBar key={`f${k}`} label="Today" mix={r.from} />
            <MixBar key={`t${k}`} label="Wants" mix={r.to} />
          </div>
        </div>
        {r.checks.map((c, i) => (
          <div className="a-check" key={c.gate}>
            {step > i ? <StatusIcon tone={stateTone(c.state)} /> : <span className="a-spin" aria-hidden />}
            <span><b>{c.name}</b></span>
            <span className={`det a-fade ${step > i ? "" : "hide"}`} style={{ color: c.state === "fail" ? "var(--red-ink)" : c.state === "pass" ? "var(--green-ink)" : "var(--mute)" }}>{c.detail}</span>
          </div>
        ))}
        <div style={{ padding: 12 }}>
          <div className={`a-final ${verdictTone(r.verdict)} a-fade ${step >= 4 ? "" : "hide"}`}>
            {verdictLabel(r.verdict)}
            <span>{r.id === "bounded" ? "Reppo said ship. Math said no." : "Outside the limit."}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function LandingPage() {
  const s = evaluation.summary;
  return (
    <Page>
      <section className="a-land-hero">
        <div>
          <span className="x-eyebrow">Supervision for self-tuning trading bots</span>
          <h1>Your bot wants to change its own rules.<span className="o">Review it first<i>.</i></span></h1>
          <p className="a-land-sub">Every self-update becomes a request. Bad ones never ship.</p>
          <div className="a-land-cta">
            <Link href="/requests" className="x-btn lg">See the requests</Link>
            <Link href="/judge" className="x-btn lg ghost">Open one yourself</Link>
          </div>
        </div>
        <LiveRequest />
      </section>

      <div className="a-score">
        <div style={{ ["--i" as string]: 0 }}><span>Changes blocked</span><b className="num">{s.adaptationsRejected} of {s.adaptationsProposed}</b></div>
        <div style={{ ["--i" as string]: 1 }}><span>Beat fixed weights</span><b className="num">{s.adaptiveBeatFixedOnReal} of {s.realDatasets}</b></div>
        <div style={{ ["--i" as string]: 2 }}><span>Beat holding cash</span><b className="num x-down">{s.datasets - s.cashBeatAdaptive} of {s.datasets}</b></div>
        <div style={{ ["--i" as string]: 3 }}><span>Live requests shipped</span><b className="num">0 of {requests.length}</b></div>
      </div>

      <section className="a-sec">
        <div className="a-sec-head"><h2>How a request is reviewed</h2></div>
        <div className="a-flow">
          <div><span className="n"><em>1</em>The bot opens a request</span><p>Today&apos;s mix, the new one, and why.</p><span className="x-pill neutral">Paper only</span></div>
          <div><span className="n"><em>2</em>SERV reasons</span><p>Past data only. Bounded proposal.</p><span className="x-pill ok">Proposes</span></div>
          <div><span className="n"><em>3</em>Math gate replays</span><p>Past 24h with fees. +0.06% or no.</p><span className="x-pill no">Final say</span></div>
          <div><span className="n"><em>4</em>Reppo reviews</span><p>Scores the reasoning. Never approves alone.</p><span className="x-pill warn">Advisory</span></div>
        </div>
      </section>

      <section className="a-sec">
        <div className="a-sec-head">
          <h2>Recent requests</h2>
          <Link href="/requests" className="x-btn sm ghost">All requests</Link>
        </div>
        <div className="a-list" style={{ marginBottom: 0 }}>
          <div className="a-rows">{requests.map((r, i) => <RequestRow key={r.id} r={r} i={i} />)}</div>
        </div>
      </section>
    </Page>
  );
}

