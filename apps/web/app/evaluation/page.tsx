"use client";

import { LineChart } from "lucide-react";
import { Page, Spark } from "@/components/x/Shell";
import { evaluation, signed, utc } from "@/lib/proof";

const TRACKS = [["adaptive", "Adaptive"], ["fixed_50_50", "Fixed 50/50"], ["momentum_only", "Momentum"], ["cash", "Cash"]] as const;

export default function EvaluationPage() {
  const s = evaluation.summary;
  return (
    <Page>
      <div className="a-head">
        <div>
          <h1>Replays</h1>
        </div>
        <div className="a-head-actions"><a className="x-btn ghost" href="/proof/evaluation.json">Raw results</a></div>
      </div>

      <div className="x-grid" style={{ gridTemplateColumns: "repeat(4,minmax(0,1fr))" }}>
        {evaluation.results.map((r) => {
          const a = r.tracks.adaptive.netReturnPct;
          return (
            <div className="x-stat" key={r.datasetId}>
              <div className="x-stat-top"><span><LineChart />{r.name.split(" (")[0]}</span><em>{r.synthetic ? "synthetic" : `${r.candles}h`}</em></div>
              <div className="x-stat-val"><b className="num">{signed(a)}</b>{r.curve && <Spark values={r.curve.adaptive} red={a < 0} />}</div>
              <span className="x-stat-sub"><span className={(r.adaptiveMinusFixedPct ?? 0) >= 0 ? "x-up" : "x-down"}>{signed(r.adaptiveMinusFixedPct ?? 0)}</span> vs fixed</span>
            </div>
          );
        })}
      </div>

      <section className="a-sec">
        <div className="a-sec-head"><h2>Every track</h2></div>
        <div className="x-table-card">
          <div className="x-table-scroll">
            <table className="x-table">
              <thead><tr><th>Market</th>{TRACKS.map(([, l]) => <th key={l}>{l}</th>)}<th>Drawdown</th><th>Kept</th></tr></thead>
              <tbody>
                {evaluation.results.map((r) => {
                  const best = Math.max(...TRACKS.map(([k]) => r.tracks[k].netReturnPct));
                  return (
                    <tr key={r.datasetId}>
                      <td><b>{r.name.split(" (")[0]}</b>{r.synthetic && <span className="x-pill neutral" style={{ marginLeft: 8 }}>synthetic</span>}</td>
                      {TRACKS.map(([k]) => {
                        const v = r.tracks[k].netReturnPct;
                        return <td key={k} className={v > 0 ? "x-up" : v < 0 ? "x-down" : "x-mute"} style={{ fontWeight: v === best ? 800 : 500 }}>{signed(v)}</td>;
                      })}
                      <td className="x-mute">{r.tracks.adaptive.maxDrawdownPct.toFixed(2)}%</td>
                      <td>{r.adaptations.accepted}/{r.adaptations.proposed}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      <section className="a-sec">
        <div className="a-sec-head"><h2>Every proposal</h2><span className="a-diff-legend"><span><i style={{ background: "var(--red)" }} />blocked</span><span><i style={{ background: "var(--green)" }} />kept</span></span></div>
        <div className="x-card x-card-pad" style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {evaluation.results.map((r) => (
            <div key={r.datasetId} style={{ display: "grid", gridTemplateColumns: "120px 1fr", gap: 14, alignItems: "end" }}>
              <span style={{ fontSize: 13.5, fontWeight: 600 }}>{r.name.split(" ")[0]}</span>
              <div className="x-strip" role="img" aria-label={`${r.adaptations.rejected} of ${r.adaptations.proposed} rejected`}>
                {(r.adaptations.events ?? []).map((e, i) => <i key={i} className={e.status === "REJECTED" ? "no" : "ok"} style={{ left: `${(e.index / r.candles) * 100}%`, ["--i" as string]: i }} />)}
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="a-sec">
        <div className="a-sec-head"><h2>Where it failed</h2></div>
        <div className="a-final no" style={{ alignItems: "flex-start", flexDirection: "column", gap: 6 }}>
          One noise trade slipped through: −1%.
          <span>Cash beat adaptive in {s.cashBeatAdaptive} of {s.datasets}.</span>
        </div>
      </section>
    </Page>
  );
}
