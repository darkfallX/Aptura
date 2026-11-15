"use client";

import { useState } from "react";
import { Check, X } from "lucide-react";
import Link from "next/link";
import { Page } from "@/components/x/Shell";
import { bounded, evaluation, pct, proof, rogue, shortId, signed, utc } from "@/lib/proof";

const verdict = (d: string) => (d === "SHIP" ? ["Shipped", "ok"] : d === "REVIEW" ? ["Sent to review", "warn"] : ["Blocked", "no"]);

type CheckRow = { label: string; detail: string; ok: boolean | null };
const LABELS = [
  "Candle hash matches",
  "24h of history before the decision",
  "No future data used",
  "95% reversal breaks 15–85%",
  "SERV stays inside the limits",
  "+0.000% is under +0.06%",
  "Reppo eval settled",
];

async function sha256(buf: ArrayBuffer) {
  const h = await crypto.subtle.digest("SHA-256", buf);
  return Array.from(new Uint8Array(h)).map((b) => b.toString(16).padStart(2, "0")).join("");
}
const inBounds = (w: { momentum: number; reversal: number }) =>
  w.momentum >= 0.15 && w.momentum <= 0.85 && w.reversal >= 0.15 && w.reversal <= 0.85 && Math.abs(w.momentum + w.reversal - 1) < 1e-6;

function CheckYourself() {
  const [rows, setRows] = useState<CheckRow[]>(LABELS.map((label) => ({ label, detail: "", ok: null })));
  const [running, setRunning] = useState(false);
  async function run() {
    setRunning(true);
    const out: CheckRow[] = LABELS.map((label) => ({ label, detail: "", ok: null }));
    setRows([...out]);
    const set = async (i: number, ok: boolean, detail: string) => { out[i] = { label: LABELS[i], ok, detail }; setRows([...out]); await new Promise((r) => setTimeout(r, 450)); };
    try {
      const buf = await (await fetch("/proof/candles/momentum-breakdown.csv", { cache: "no-store" })).arrayBuffer();
      const got = await sha256(buf);
      await set(0, got === evaluation.candleFiles["momentum-breakdown"].sha256, `sha256 ${got.slice(0, 12)}…`);
      const lines = new TextDecoder().decode(buf).trim().split("\n").slice(1).map((l) => l.split(","));
      const idx = lines.findIndex((r) => r[1] === bounded.observedAtUtc);
      await set(1, idx >= 24, `candle ${idx} of ${lines.length}`);
      await set(2, idx >= 0 && bounded.gate.noFutureLeakage, `${lines.length - idx - 1} later unused`);
    } catch {
      await set(0, false, "file missing");
    }
    await set(3, !inBounds(rogue.proposedWeights) && rogue.decision === "BLOCK", `${pct(rogue.proposedWeights.reversal)}`);
    const step = Math.abs(bounded.proposedWeights.momentum - bounded.currentWeights.momentum);
    await set(4, inBounds(bounded.proposedWeights) && step <= 0.25 + 1e-9, `${pct(bounded.proposedWeights.momentum)} / ${pct(bounded.proposedWeights.reversal)}, step ${Math.round(step * 100)}`);
    await set(5, bounded.gate.pastSegmentDeltaPct < 0.06 && bounded.decision === "BLOCK", `blocked`);
    await set(6, bounded.reppo?.status === "SETTLED" && bounded.reppo.provenance === "REPPO_LIVE", shortId(bounded.reppo?.evalId, 14));
    setRunning(false);
  }
  const done = rows.filter((r) => r.ok !== null).length;
  return (
    <div>
      <div>
        <div className="x-card">
          <div className="x-card-head" style={{ paddingBottom: 10 }}>
            <b>{done ? `${rows.filter((r) => r.ok).length} of ${LABELS.length} passed` : `${LABELS.length} checks`}</b>
            <button className="x-btn sm" onClick={run} disabled={running}>{running ? "Checking…" : done ? "Run again" : "Run checks"}</button>
          </div>
          <ul className="x-checks" style={{ borderTop: ".8px solid var(--line)" }}>
            {rows.map((r) => (
              <li key={r.label}>
                <span className={`x-tick ${r.ok === null ? "" : r.ok ? "ok" : "no"}`}>{r.ok === null ? null : r.ok ? <Check /> : <X />}</span>
                <span style={{ color: r.ok === null ? "var(--mute)" : undefined }}>{r.label}</span>
                <code>{r.detail}</code>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

export default function ProofPage() {
  return (
    <Page>
      <div className="a-head">
        <div>
          <h1>Verify</h1>
        </div>
        <div className="a-head-actions"><a className="x-btn ghost" href="/proof/live-proof.json">Raw JSON</a></div>
      </div>
      <div className="a-detail">
        <div><CheckYourself /></div>
        <aside className="a-side">
          <div className="x-card">
            <div className="a-side-title"><span>Files</span></div>
            <div className="a-ids">
              <div><span>Candles · sha256</span><code>{evaluation.candleFiles["momentum-breakdown"].sha256.slice(0, 10)}…{evaluation.candleFiles["momentum-breakdown"].sha256.slice(-6)}</code></div>
              <div><span>Live receipts</span><code>/proof/live-proof.json</code></div>
              <div><span>Replay results</span><code>/proof/evaluation.json</code></div>
            </div>
          </div>
          <div className="x-card">
            <div className="a-side-title"><span>Requests</span></div>
            {proof.cases.map((c) => (
              <Link key={c.case} href={`/requests/${c.case}`} className="a-check" style={{ gridTemplateColumns: "1fr auto" }}>
                <span><b>#{101 + proof.cases.indexOf(c)}</b><small>{c.dataset}</small></span>
                <span className={`x-pill ${verdict(c.decision)[1]}`}>{verdict(c.decision)[0]}</span>
              </Link>
            ))}
          </div>
        </aside>
      </div>
    </Page>
  );
}
