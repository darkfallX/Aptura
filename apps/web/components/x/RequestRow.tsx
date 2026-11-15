"use client";
import Link from "next/link";
import { CheckDots, MixBar, StatusIcon } from "@/components/x/Shell";
import { pct } from "@/lib/proof";
import { verdictLabel, verdictTone, type ChangeRequest } from "@/lib/requests";

export function RequestRow({ r, i = 0 }: { r: ChangeRequest; i?: number }) {
  const tone = verdictTone(r.verdict);
  return (
    <Link href={`/requests/${r.id}`} className="a-row" style={{ ["--i" as string]: i }}>
      <StatusIcon tone={tone} />
      <div style={{ minWidth: 0 }}>
        <div className="a-row-title">{pct(r.from.momentum)} → {pct(r.to.momentum)} momentum</div>
        <div className="a-row-meta">{r.bot} · #{r.number}</div>
      </div>
      <div className="a-mix a-mix-small"><MixBar mix={r.from} /><MixBar mix={r.to} /></div>
      <CheckDots checks={r.checks} />
      <span className={`x-pill ${tone}`}>{verdictLabel(r.verdict)}</span>
    </Link>
  );
}
