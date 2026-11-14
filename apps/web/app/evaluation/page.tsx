"use client";

import { Odometer, PaperFoot, PaperNav, useInView, useTicker } from "@/components/paper/Paper";
import { evaluation, signed, utc } from "@/lib/proof";

const TRACKS = [["adaptive", "ADAPTIVE"], ["fixed_50_50", "FIXED 50/50"], ["momentum_only", "MOMENTUM"], ["cash", "CASH"]] as const;

function Strip({ events, candles }: { events: { index: number; status: string; deltaPct: number | null }[]; candles: number }) {
  const [ref, seen] = useInView<HTMLDivElement>(0.25);
  const shown = useTicker(events.length, seen, 110);
  return (
    <div ref={ref} className="p-strip" role="img" aria-label={`${events.filter((e) => e.status === "REJECTED").length} of ${events.length} changes rejected`}>
      {events.map((e, i) => (
        <i key={i} className={`${e.status === "REJECTED" ? "no" : "yes"} ${i < shown ? "on" : ""}`} style={{ left: `${(e.index / candles) * 100}%` }} />
      ))}
    </div>
  );
}

export default function EvaluationPage() {
  const s = evaluation.summary;
  const [ref, seen] = useInView<HTMLDivElement>(0.3);
  return (
    <div className="p-page">
      <PaperNav />
      <main className="p-wrap">
        <h1 className="p-display" style={{ marginTop: 50 }}>Where it works.<br /><em>Where it doesn't.</em></h1>
        <div className="p-notes" ref={ref}>
          <div><b><Odometer value={`${s.adaptiveBeatFixedOnReal}/${s.realDatasets}`} run={seen} /></b><p>real markets where adaptive beat fixed 50/50</p></div>
          <div className="red"><b><Odometer value={`${s.cashBeatAdaptive}/${s.datasets}`} run={seen} /></b><p>markets where holding cash beat adaptive</p></div>
          <div><b><Odometer value={`${s.adaptationsRejected}/${s.adaptationsProposed}`} run={seen} /></b><p>proposed changes the gate rejected</p></div>
        </div>

        <div className="p-table-wrap">
          <table className="p-table">
            <thead><tr><th>MARKET</th>{TRACKS.map(([, l]) => <th key={l}>{l}</th>)}<th>MAX DRAWDOWN</th><th>CHANGES</th></tr></thead>
            <tbody>
              {evaluation.results.map((r) => {
                const best = Math.max(...TRACKS.map(([k]) => r.tracks[k].netReturnPct));
                return (
                  <tr key={r.datasetId}>
                    <td>{r.name}{r.synthetic && <span className="p-mono" style={{ fontSize: 11, color: "var(--stamp)", marginLeft: 10 }}>SYNTHETIC</span>}</td>
                    {TRACKS.map(([k]) => {
                      const v = r.tracks[k].netReturnPct;
                      return <td key={k} className={`${v < 0 ? "neg" : ""} ${v === best ? "best" : ""}`}>{signed(v)}</td>;
                    })}
                    <td>{r.tracks.adaptive.maxDrawdownPct.toFixed(2)}%</td>
                    <td>{r.adaptations.accepted} / {r.adaptations.proposed}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>

        <section style={{ margin: "110px 0 40px" }}>
          <h2 className="p-h2">Every change, on the timeline.</h2>
          <div className="p-strips">
            {evaluation.results.map((r) => (
              <div key={r.datasetId} className="p-strip-row">
                <span>{r.name.split(" ")[0]}</span>
                <Strip events={r.adaptations.events ?? []} candles={r.candles} />
              </div>
            ))}
          </div>
          <div className="p-tape-key"><span><i style={{ background: "var(--stamp)" }} />rejected</span><span><i style={{ background: "var(--paper)" }} />shipped</span><span>hour 0 → 199</span></div>
        </section>

        <section className="p-fail">
          <span className="p-mono">FAILURE</span>
          <h2 className="p-h2">On pure noise, one change slipped through.<br /><em>It cost 1%.</em></h2>
          <p className="p-lede">The synthetic whipsaw exists to catch exactly this. The gate stopped 3 of 4 changes and missed one.</p>
        </section>

        <p className="p-mono" style={{ fontSize: 12, color: "var(--desk-dim)", lineHeight: 1.9, margin: "70px 0 120px" }}>
          {evaluation.engine} · generated {utc(evaluation.generatedAtUtc)} · reproduce: python scripts/run_evaluation.py
        </p>
      </main>
      <PaperFoot />
    </div>
  );
}
