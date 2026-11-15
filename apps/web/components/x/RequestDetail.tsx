"use client";
import Link from "next/link";
import { useState } from "react";
import { Bot, Brain, Calculator, CornerDownRight, Flag, Users } from "lucide-react";
import { MixBar, Page, StatusIcon } from "@/components/x/Shell";
import { pct, signed, utc } from "@/lib/proof";
import { inLimits, stateTone, verdictLabel, verdictTone, type ChangeRequest } from "@/lib/requests";

type Step = { weights: { momentum: number; reversal: number }; delta: number; passed: boolean; summary: string; hypothesis: string; servId: string | null; score: number | null; route: string | null; critique: string | null };

function steps(r: ChangeRequest): Step[] {
  const c = r.source;
  if (c.rounds?.length) {
    return c.rounds.map((x) => ({ weights: x.weights, delta: x.pastWindowDeltaPct, passed: x.gatePassed, summary: x.gateSummary, hypothesis: x.hypothesis, servId: x.servResponseId, score: x.reppoScore, route: x.reppoRoute, critique: x.reppoCritique }));
  }
  return [{ weights: c.proposedWeights, delta: c.gate.pastSegmentDeltaPct, passed: c.gate.passed, summary: c.gate.summary, hypothesis: c.serv.hypothesis, servId: c.serv.responseId, score: c.reppo?.score ?? null, route: c.reppo?.route ?? null, critique: c.reppo?.critique ?? null }];
}

function Ev({ i, tone, icon, head, children }: { i: number; tone: string; icon: React.ReactNode; head: React.ReactNode; children?: React.ReactNode }) {
  return (
    <div className="a-ev" style={{ ["--i" as string]: i }}>
      <span className={`a-ev-icon ${tone}`}>{icon}</span>
      <div className="a-ev-head">{head}</div>
      {children && <div className="a-ev-body">{children}</div>}
    </div>
  );
}

function Timeline({ r }: { r: ChangeRequest }) {
  const st = steps(r);
  const chosen = r.source.improvement?.chosenRound ?? st.length - 1;
  let n = 0;
  const out: React.ReactNode[] = [];
  out.push(
    <Ev key="open" i={n++} tone="ink" icon={<Bot />} head={<><b>{r.bot}</b><span className="x-mute">opened</span></>}>
      <p>“{r.rationale}”</p>
    </Ev>,
  );
  st.forEach((s, k) => {
    const last = k === st.length - 1;
    out.push(
      <Ev key={`s${k}`} i={n++} tone="" icon={<Brain />} head={<><b>SERV</b><span className="x-mute">{k === 0 ? "" : `revised to ${pct(s.weights.momentum)} / ${pct(s.weights.reversal)}`}</span></>}>
        <p style={{ color: "var(--ink-2)" }}>{s.hypothesis}</p>
      </Ev>,
    );
    out.push(
      <Ev key={`g${k}`} i={n++} tone={s.passed ? "ok" : "no"} icon={<Calculator />} head={<><b>Math gate</b><span className={s.passed ? "x-up" : "x-down"}>{s.passed ? "passed" : "failed"}</span></>}>
        <div className="x-card">
          <div className="x-cells" style={{ borderTop: 0 }}>
            <div><span>Past 24 hours</span><b className={`num ${s.delta >= 0.06 ? "x-up" : "x-down"}`}>{signed(s.delta, 3)}</b></div>
            <div><span>Needed</span><b className="num">+0.060%</b></div>
          </div>
          <div className="x-cells">
            <div><span>15–85% limit</span><b>{inLimits(s.weights) ? "Inside" : "Outside"}</b></div>
            <div><span>Step from today</span><b className="num">{Math.round(Math.abs(s.weights.momentum - r.from.momentum) * 100)} pts</b></div>
          </div>
        </div>
      </Ev>,
    );
    if (s.score != null) {
      const tone = s.route === "ship" ? "ok" : s.route === "review" ? "warn" : "no";
      out.push(
        <Ev key={`p${k}`} i={n++} tone={tone} icon={<Users />} head={<><b>Reppo</b><span className="x-mute">{s.score} · {s.route}</span></>}>
          {s.critique && <div className="x-card"><p className="x-card-text" style={{ padding: "12px 14px", color: "var(--ink-2)" }}>{s.critique}</p>
            {last && r.source.reppo?.rubricScores && Object.keys(r.source.reppo.rubricScores).length > 0 && (
              <div className="x-cells" style={{ gridTemplateColumns: `repeat(${Object.keys(r.source.reppo.rubricScores).length},1fr)` }}>
                {Object.entries(r.source.reppo.rubricScores).map(([k2, v]) => <div key={k2}><span style={{ textTransform: "capitalize" }}>{k2}</span><b className="num">{v}</b></div>)}
              </div>
            )}
          </div>}
        </Ev>,
      );
    }
    if (!last) {
      out.push(
        <Ev key={`f${k}`} i={n++} tone="" icon={<CornerDownRight />} head={<><b>Sent back to SERV</b></>} />,
      );
    }
  });
  const msg = r.verdict === "BLOCK"
    ? (r.source.rounds && r.source.rounds.length > 1 ? "No revision passed." : r.id === "bounded" ? "Reppo said ship. Math said no." : "Outside the limit.")
    : `Round ${chosen} kept.`;
  out.push(
    <Ev key="v" i={n++} tone={verdictTone(r.verdict)} icon={<Flag />} head={<b>Verdict</b>}>
      <div className={`a-final ${verdictTone(r.verdict)}`}>{verdictLabel(r.verdict)}<span>{msg}</span></div>
    </Ev>,
  );
  return <div className="a-tl">{out}</div>;
}

function Checks({ r }: { r: ChangeRequest }) {
  const [run, setRun] = useState<number | null>(null);
  const verify = () => {
    setRun(0);
    r.checks.forEach((_, i) => setTimeout(() => setRun(i + 1), 850 * (i + 1)));
  };
  const showing = (i: number) => run === null || run > i;
  return (
    <div className="x-card">
      <div className="a-side-title"><span>Checks</span><span className="x-mute" style={{ fontWeight: 500, fontSize: 13 }}>{r.checks.filter((c) => c.state === "pass").length}/{r.checks.length}</span></div>
      {r.checks.map((c, i) => (
        <div className="a-check" key={c.gate}>
          {showing(i) ? <StatusIcon tone={stateTone(c.state)} /> : <span className="a-spin" aria-hidden />}
          <span><b>{c.name}</b><small>{showing(i) ? c.note : "…"}</small></span>
          <span className="det" style={{ color: c.state === "fail" ? "var(--red-ink)" : c.state === "pass" ? "var(--green-ink)" : "var(--mute)" }}>{showing(i) ? c.detail : ""}</span>
        </div>
      ))}
      <div style={{ padding: 12, borderTop: ".8px solid var(--line-soft)" }}>
        <button className="x-btn ghost sm" style={{ width: "100%" }} onClick={verify} disabled={run !== null && run < r.checks.length}>Re-run</button>
      </div>
    </div>
  );
}

export default function RequestDetail({ r }: { r: ChangeRequest }) {
  const c = r.source;
  const final = c.rounds?.length ? c.rounds[c.improvement?.chosenRound ?? c.rounds.length - 1].weights : null;
  const tone = verdictTone(r.verdict);
  return (
    <Page>
      <div className="a-head" style={{ paddingBottom: 18 }}>
        <div>
          <div className="a-crumb"><Link href="/requests">Requests</Link><span>/</span><span>#{r.number}</span></div>
          <div className="a-title-row">
            <h1>{r.bot}: {pct(r.from.momentum)} → {pct(r.to.momentum)} momentum</h1>
            <span className={`x-pill ${tone}`}>{verdictLabel(r.verdict)}</span>
          </div>
          <p>{r.market} · {utc(r.at)}</p>
        </div>
      </div>
      <div className="a-detail">
        <div>
          <div className="x-card">
            <div className="x-card-head" style={{ paddingBottom: 0 }}>
              <b>Change</b>
              <span className="a-diff-legend"><span><i style={{ background: "var(--ink)" }} />momentum</span><span><i style={{ background: "var(--line)" }} />reversal</span><span>┆ limits</span></span>
            </div>
            <div className="a-diff a-mix">
              <MixBar large label="Today" mix={r.from} />
              <MixBar large label="Asked" mix={r.to} />
              {!c.rounds?.length && c.serv.provenance === "SERV_GENERATED" && <MixBar large label="SERV" mix={{ momentum: c.serv.suggestedWeights.momentum, reversal: c.serv.suggestedWeights.reversal }} />}
              {final && <MixBar large label="Final" mix={final} />}
            </div>
          </div>
          <Timeline r={r} />
        </div>
        <aside className="a-side">
          <Checks r={r} />
          <div className="x-card">
            <div className="a-side-title"><span>Receipts</span><a className="x-mute" style={{ fontWeight: 500, fontSize: 13 }} href="/proof/live-proof.json">Raw JSON</a></div>
            <div className="a-ids">
              <div><span>Request</span><code>{c.requestId}</code></div>
              <div><span>SERV · {c.serv.model}</span><code>{c.serv.responseId ?? "—"}</code></div>
              {(c.reppo || c.rounds?.some((x) => x.reppoEvalId)) && <div><span>Reppo eval</span><code>{c.reppo?.evalId ?? c.rounds?.find((x) => x.reppoEvalId)?.reppoEvalId}</code></div>}
              {c.reppo?.creditsCharged != null && <div><span>Credits</span><code>{c.reppo.creditsCharged}</code></div>}
            </div>
          </div>
        </aside>
      </div>
    </Page>
  );
}
