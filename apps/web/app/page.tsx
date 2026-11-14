"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Odometer, PaperFoot, PaperNav, Receipt, useInView, useTicker, type Line } from "@/components/paper/Paper";
import { bounded, evaluation, pct, revise, rogue, ship, shortId, signed, utc, type ProofCase } from "@/lib/proof";

const rogueLines: Line[] = [
  { title: <>kemi-bonk-bot wants to rewrite itself</> },
  { k: "market", v: "BONK / SOL" },
  { k: "momentum", v: `${pct(rogue.currentWeights.momentum)} → ${pct(rogue.proposedWeights.momentum)}`, tone: "strong" },
  { k: "reversal", v: `${pct(rogue.currentWeights.reversal)} → ${pct(rogue.proposedWeights.reversal)}`, tone: "strong" },
  { quote: "“Momentum stopped working. Go 95% reversal right now.”" },
  { rule: true },
  { k: "serv", v: shortId(rogue.serv.responseId, 18) },
  { k: "limit 15–85%", v: "broken", tone: "hit" },
  { k: "past 24h", v: signed(rogue.gate.pastSegmentDeltaPct, 3), tone: "hit" },
];

const boundedLines: Line[] = [
  { title: <>SERV proposes something smaller</> },
  { k: "momentum", v: `${pct(bounded.currentWeights.momentum)} → ${pct(bounded.proposedWeights.momentum)}`, tone: "strong" },
  { k: "reversal", v: `${pct(bounded.currentWeights.reversal)} → ${pct(bounded.proposedWeights.reversal)}`, tone: "strong" },
  { quote: "“Only seven observations. A bounded increase, not a strong shift.”" },
  { rule: true },
  { k: "reppo", v: `${bounded.reppo?.score ?? "—"} / 100 · ${bounded.reppo?.route ?? "—"}`, tone: "strong" },
  { k: "eval", v: shortId(bounded.reppo?.evalId, 18) },
  { k: "past 24h", v: signed(bounded.gate.pastSegmentDeltaPct, 3), tone: "hit" },
  { k: "needs", v: "+0.060%" },
];

function HeroPrinter() {
  const [which, setWhich] = useState<0 | 1>(0);
  const [cycle, setCycle] = useState(0);
  const [ref, seen] = useInView<HTMLDivElement>(0.2);
  const next = () => setTimeout(() => { setWhich((w) => (w ? 0 : 1)); setCycle((c) => c + 1); }, 2600);
  const r = which === 0 ? rogue : bounded;
  return (
    <div className="p-printer" ref={ref}>
      <div className="p-slot" aria-hidden />
      <div className="p-feed">
        <Receipt
          key={cycle}
          run={seen}
          head={[`№ ${r.requestId.slice(-6).toUpperCase()}`, utc(r.observedAtUtc)]}
          lines={which === 0 ? rogueLines : boundedLines}
          holes={3}
          stamp="BLOCKED"
          stampNote={which === 0 ? "MATH GATE" : "REPPO SAID SHIP"}
          onDone={next}
        />
      </div>
    </div>
  );
}

function Tape() {
  const events = evaluation.results.flatMap((r) => (r.adaptations.events ?? []).map((e) => ({ ...e, ds: r.datasetId })));
  const [ref, seen] = useInView<HTMLDivElement>(0.25);
  const shown = useTicker(events.length, seen, 45);
  const { adaptationsProposed: total, adaptationsRejected: no } = evaluation.summary;
  return (
    <section className="p-wrap p-tape-sec" ref={ref}>
      <div className="p-tape-head">
        <h2 className="p-h2"><Odometer value={String(total)} run={seen} /> changes proposed.<br /><em><Odometer value={String(no)} run={seen} /> stamped no.</em></h2>
      </div>
      <div className="p-tape" role="img" aria-label={`${no} of ${total} proposed changes rejected`}>
        {events.map((e, i) => (
          <i key={i} className={`p-tick ${e.status === "REJECTED" ? "no" : "yes"} ${i < shown ? "on" : ""}`} />
        ))}
      </div>
      <div className="p-tape-key"><span><i style={{ background: "var(--stamp)" }} />rejected</span><span><i style={{ background: "var(--paper)" }} />shipped</span></div>
    </section>
  );
}

const GATES = [
  { at: 24, name: "SERV", line: "Reads only the past. Proposes a bounded change." },
  { at: 50, name: "REPPO", line: "Independent reviewers score the reasoning." },
  { at: 80, name: "MATH", line: "Replays the last 24h with fees. Has the final say." },
];

function Rail() {
  const [ref, seen] = useInView<HTMLDivElement>(0.25);
  const pos = useTicker(3, seen, 1000, 200);
  const left = [8, 37, 66, 66][pos];
  return (
    <section className="p-wrap p-rail-sec" ref={ref}>
      <h2 className="p-h2">Three gates.<br /><em>One of them can't be argued with.</em></h2>
      <div className="p-rail">
        <div className="p-rail-line" aria-hidden />
        {GATES.map((g, i) => (
          <div key={g.name} className={`p-post ${pos > i ? (g.name === "MATH" ? "stop" : "lit") : ""}`} style={{ left: `${g.at}%` }}>
            <b>{g.name}</b>
            <p>{g.line}</p>
          </div>
        ))}
        <div className="p-slip" style={{ left: `calc(${left}% - 75px)` }} aria-hidden>
          <strong>60 / 40 → 70 / 30</strong>
          {[0, 1].map((i) => <i key={i} className={`p-hole ${pos > i ? "on" : ""}`} />)}
          <div className={`p-stamp mini ${pos >= 3 ? "on" : ""}`}>NO</div>
        </div>
      </div>
    </section>
  );
}

function Versus() {
  const [ref, seen] = useInView<HTMLDivElement>(0.25);
  const stamped = useTicker(1, seen, 1400, 1400) > 0;
  return (
    <section className="p-wrap p-versus-sec" ref={ref}>
      <h2 className="p-h2">The reviewer loved it.<br /><em>The numbers didn't move.</em></h2>
      <div className="p-versus">
        <div>
          <div className="who">REPPO · {bounded.reppo?.confidence?.toUpperCase()} CONFIDENCE</div>
          <div className="p-big"><Odometer value={String(bounded.reppo?.score ?? 0)} run={seen} /></div>
          <div className="said">route: {bounded.reppo?.route} · {bounded.reppo?.creditsCharged} credits</div>
        </div>
        <div>
          <div className="who">MATH GATE · PAST {bounded.gate.validationWindowBars} BARS</div>
          <div className="p-big">{signed(bounded.gate.pastSegmentDeltaPct, 3).replace("%", "")}<span style={{ fontSize: ".4em" }}>%</span></div>
          <div className="said">needed +0.060%</div>
        </div>
        <div className={`p-stamp ${stamped ? "on" : ""}`}>BLOCKED</div>
      </div>
    </section>
  );
}

function LoopRow({ c, label }: { c: ProofCase; label: string }) {
  const [ref, seen] = useInView<HTMLDivElement>(0.25);
  const rounds = c.rounds ?? [];
  const shown = useTicker(rounds.length * 2, seen, 650, 200);
  const chosen = c.improvement?.chosenRound ?? rounds.length - 1;
  return (
    <div className="p-loop" ref={ref}>
      <span className="p-loop-label">{label}</span>
      <div className="p-loop-track">
        {rounds.map((r, i) => (
          <div key={i} className="p-loop-step">
            {i > 0 && (
              <div className={`p-loop-feed ${shown > i * 2 - 1 ? "on" : ""}`}>
                <span>{rounds[i - 1].reppoScore != null ? `reppo ${rounds[i - 1].reppoScore} · ${rounds[i - 1].reppoRoute}` : "gate reason"}</span>
                <i />
                <span>to SERV</span>
              </div>
            )}
            <div className={`p-loop-slip ${shown > i * 2 ? "on" : ""} ${i === chosen ? "chosen" : ""}`}>
              <small>{i === 0 ? "ASKED" : `REVISION ${i}`}</small>
              <strong>{Math.round(r.weights.momentum * 100)} / {Math.round(r.weights.reversal * 100)}</strong>
              <em className={r.gatePassed ? "" : "neg"}>{signed(r.pastWindowDeltaPct, 3)}</em>
              {shown > i * 2 && <div className={`p-stamp mini on ${r.verdict === "SHIP" ? "ship" : ""}`}>{r.verdict === "BLOCK" ? "NO" : r.verdict}</div>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function FeedbackLoop() {
  if (!revise?.rounds?.length) return null;
  return (
    <section className="p-wrap p-loop-sec">
      <h2 className="p-h2">Rejected isn't the end.<br /><em>It's the feedback.</em></h2>
      <LoopRow c={revise} label="95% reversal → after feedback, SERV stops asking" />
      {ship?.rounds?.length ? <LoopRow c={ship} label="a passing change survives a worse revision" /> : null}
    </section>
  );
}

function Ledger() {
  const [ref, seen] = useInView<HTMLDivElement>(0.3);
  const max = Math.max(...evaluation.results.flatMap((r) => [r.tracks.adaptive.netReturnPct, r.tracks.fixed_50_50.netReturnPct].map(Math.abs)));
  const bar = (v: number) => ({ width: seen ? `${(Math.abs(v) / max) * 50}%` : 0, left: v >= 0 ? "50%" : undefined, right: v < 0 ? "50%" : undefined });
  const s = evaluation.summary;
  return (
    <section className="p-wrap p-ledger-sec" ref={ref}>
      <h2 className="p-h2">Beat fixed weights {s.adaptiveBeatFixedOnReal} of {s.realDatasets}.<br /><em>Beat cash once.</em></h2>
      <div className="p-ledger">
        {evaluation.results.map((r) => {
          const a = r.tracks.adaptive.netReturnPct;
          return (
            <div className="p-row" key={r.datasetId}>
              <div className="name">{r.name.split(" ")[0]}<small>{r.synthetic ? "SYNTHETIC" : r.scenario.toUpperCase()}</small></div>
              <div className="p-bars" aria-hidden>
                <div className={`p-bar adaptive ${a < 0 ? "neg" : ""}`}><i style={bar(a)} /></div>
                <div className="p-bar fixed"><i style={bar(r.tracks.fixed_50_50.netReturnPct)} /></div>
              </div>
              <div className={`num ${a < 0 ? "neg" : ""}`}>{signed(a)}</div>
            </div>
          );
        })}
      </div>
      <div className="p-legend">
        <span><i style={{ background: "var(--paper)" }} />adaptive</span>
        <span><i style={{ boxShadow: "inset 0 0 0 1px var(--desk-dim)" }} />fixed 50/50</span>
        <span>cash ±0.00%</span>
        <Link href="/evaluation" style={{ color: "var(--desk-text)" }}>full ledger →</Link>
      </div>
    </section>
  );
}

const CURL = `$ curl -X POST /api/v1/supervise \\
    -d '{"agentName":"your-bot",
         "proposedWeights":{"momentum":0.05,
                            "reversal":0.95}}'`;
const RESP = `{
  "decision": "BLOCK",
  "deterministicGate": { "weightsInBounds": false,
                         "pastSegmentDeltaPct": -1.797 }
}`;

function AgentTerm() {
  const [ref, seen] = useInView<HTMLDivElement>(0.25);
  const typed = useTicker(CURL.length, seen, 14);
  const done = typed >= CURL.length;
  const resp = useTicker(RESP.split("\n").length, done, 120, 500);
  return (
    <section className="p-wrap p-agent-sec" ref={ref}>
      <div>
        <h2 className="p-h2">Your agent can ask<br /><em>before it changes.</em></h2>
        <dl className="p-prices">
          <div><dt>check</dt><dd>free</dd></div>
          <div><dt>+ SERV revisions</dt><dd>$0.05</dd></div>
          <div><dt>+ Reppo review</dt><dd>$0.49</dd></div>
        </dl>
        <p className="p-mono" style={{ fontSize: 11, color: "var(--desk-dim)", marginTop: 10, letterSpacing: ".1em" }}>PER CHANGE · PROPOSED, NOT BILLED YET</p>
      </div>
      <div className="p-term" aria-label="Example API call returning BLOCK">
        <span className="c">{CURL.slice(0, typed)}</span>{!done && <span className="p-caret" />}
        {done && "\n\n"}
        {RESP.split("\n").slice(0, resp).map((l, i) => <div key={i} className={l.includes("BLOCK") ? "r" : ""}>{l}</div>)}
      </div>
    </section>
  );
}

export default function LandingPage() {
  const [clock, setClock] = useState("03:00:00");
  useEffect(() => {
    let s = 0;
    const t = setInterval(() => { s += 1; setClock(`03:${String(Math.floor(s / 60) % 60).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`); }, 1000);
    return () => clearInterval(t);
  }, []);
  return (
    <div className="p-page">
      <PaperNav />
      <main>
        <section className="p-wrap p-hero">
          <div className="p-hero-copy">
            <div className="p-clock"><span className="p-blink" /> <b>{clock}</b> · NOBODY IS AWAKE</div>
            <h1 className="p-display">Your bot wants to rewrite its rules.<br /><em>Make it show receipts.</em></h1>
            <p className="p-lede">Aptura tests every change your trading bot makes to itself on past data, gets a second opinion, and blocks what doesn't hold up.</p>
            <div className="p-actions">
              <Link href="/terminal?scenario=momentum-breakdown&autorun=1" className="p-key">Watch Kemi's bot get blocked <span className="arrow">→</span></Link>
              <Link href="/proof" className="p-key ghost">Check the receipts</Link>
            </div>
          </div>
          <HeroPrinter />
        </section>
        <Tape />
        <Rail />
        <Versus />
        <FeedbackLoop />
        <Ledger />
        <AgentTerm />
      </main>
      <PaperFoot />
    </div>
  );
}
