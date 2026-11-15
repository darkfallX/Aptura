"use client";

import { useState } from "react";
import Link from "next/link";
import { Page, StatusIcon } from "@/components/x/Shell";
import { RequestRow } from "@/components/x/RequestRow";
import { evaluation, signed } from "@/lib/proof";
import { replayRequests, requests } from "@/lib/requests";

type Tab = "live" | "replay";
type Filter = "all" | "blocked" | "kept";

export default function RequestsPage() {
  const [tab, setTab] = useState<Tab>("live");
  const [filter, setFilter] = useState<Filter>("all");
  const s = evaluation.summary;
  const live = requests.filter((r) => filter === "all" || (filter === "blocked" ? r.verdict === "BLOCK" : r.verdict !== "BLOCK"));
  const replay = replayRequests.filter((r) => filter === "all" || (filter === "blocked" ? r.status === "REJECTED" : r.status !== "REJECTED"));
  return (
    <Page>
      <div className="a-head">
        <div>
          <h1>Requests</h1>
        </div>
        <div className="a-head-actions"><Link href="/judge" className="x-btn">Open a request</Link></div>
      </div>

      <div className="a-score">
        <div style={{ ["--i" as string]: 0 }}><span>Live requests</span><b className="num">{requests.length}</b></div>
        <div style={{ ["--i" as string]: 1 }}><span>Live shipped</span><b className="num">0</b></div>
        <div style={{ ["--i" as string]: 2 }}><span>Replay proposals</span><b className="num">{s.adaptationsProposed}</b></div>
        <div style={{ ["--i" as string]: 3 }}><span>Replays blocked</span><b className="num x-down">{s.adaptationsRejected}</b></div>
      </div>

      <div className="a-list">
        <div className="a-list-head">
          <div className="x-tabs" role="tablist">
            <button role="tab" aria-pressed={tab === "live"} onClick={() => setTab("live")}>Live · {requests.length}</button>
            <button role="tab" aria-pressed={tab === "replay"} onClick={() => setTab("replay")}>Replays · {replayRequests.length}</button>
          </div>
          <div className="x-tabs" aria-label="Filter">
            {(["all", "blocked", "kept"] as Filter[]).map((f) => <button key={f} aria-pressed={filter === f} onClick={() => setFilter(f)}>{f === "all" ? "All" : f === "blocked" ? "Blocked" : "Passed"}</button>)}
          </div>
        </div>
        {tab === "live" ? (
          <div className="a-rows" key={`l${filter}`}>
            {live.map((r, i) => <RequestRow key={r.id} r={r} i={i} />)}
            {!live.length && <div className="a-row" style={{ gridTemplateColumns: "1fr", color: "var(--mute)" }}>None</div>}
          </div>
        ) : (
          <div className="a-rows" key={`r${filter}`}>
            {replay.map((r, i) => {
              const no = r.status === "REJECTED";
              return (
                <div key={`${r.market}${r.index}`} className="a-row replay" style={{ ["--i" as string]: Math.min(i, 20) }}>
                  <StatusIcon tone={no ? "no" : "ok"} />
                  <div style={{ minWidth: 0 }}>
                    <div className="a-row-title">{r.market}, hour {r.index}</div>
                    {r.synthetic && <div className="a-row-meta">synthetic</div>}
                  </div>
                  <span className={`a-dot ${no ? "fail" : "pass"}`} style={{ justifySelf: "start" }}>Math {r.deltaPct == null ? "" : signed(r.deltaPct, 3)}</span>
                  <span className={`x-pill ${no ? "no" : "ok"}`}>{no ? "Blocked" : "Kept"}</span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </Page>
  );
}
