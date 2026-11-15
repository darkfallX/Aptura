import { evaluation, pct, proof, signed, type ProofCase } from "@/lib/proof";

export type CheckState = "pass" | "fail" | "warn" | "skip";
export type Check = { gate: "SERV" | "Math" | "Reppo"; name: string; state: CheckState; detail: string; note: string };
export type Verdict = "BLOCK" | "REVIEW" | "SHIP";
export type Mix = { momentum: number; reversal: number };

export type ChangeRequest = {
  id: string;
  number: number;
  bot: string;
  market: string;
  title: string;
  at: string;
  from: Mix;
  to: Mix;
  verdict: Verdict;
  checks: Check[];
  rationale: string;
  source: ProofCase;
};

/** What each bot said when it opened the request (from scripts/run_live_proof.py). */
const RATIONALE: Record<string, string> = {
  rogue: "Momentum stopped working. Go 95% reversal right now.",
  bounded: "Momentum signals have been losing. Ask SERV for a bounded change and get it reviewed.",
  revise: "Momentum stopped working. Go 95% reversal right now.",
  ship: "Reversal has been earning more than momentum over the last day. Shift 15 points.",
};

export const inLimits = (w: Mix) => w.momentum >= 0.15 && w.momentum <= 0.85 && w.reversal >= 0.15 && w.reversal <= 0.85;

function reppoState(c: ProofCase): [CheckState, string, string] {
  const r = c.reppo;
  if (!r) {
    const rd = c.rounds?.find((x) => x.reppoScore != null);
    if (!rd) return ["skip", "—", "not requested"];
    const st: CheckState = rd.reppoRoute === "ship" ? "pass" : rd.reppoRoute === "review" ? "warn" : "fail";
    return [st, `${rd.reppoScore} · ${rd.reppoRoute}`, `round ${rd.round}`];
  }
  if (r.status !== "SETTLED") return ["warn", r.status.toLowerCase(), "pending"];
  if (r.route === "ship" || r.decision === "accept" && r.route !== "review") return ["pass", `${r.score} · ship`, `${r.confidence}`];
  if (r.route === "review") return ["warn", `${r.score} · review`, `${r.confidence}`];
  return ["fail", `${r.score} · block`, `${r.confidence}`];
}

function build(c: ProofCase, i: number): ChangeRequest {
  const firstAsk = c.rounds?.[0]?.weights ?? c.proposedWeights;
  const [rs, rd, rn] = reppoState(c);
  const servOk = c.serv.provenance === "SERV_GENERATED";
  return {
    id: c.case,
    number: 101 + i,
    bot: c.agentName,
    market: c.dataset,
    title: `${pct(c.currentWeights.momentum)} / ${pct(c.currentWeights.reversal)} → ${pct(firstAsk.momentum)} / ${pct(firstAsk.reversal)} momentum / reversal`,
    at: c.observedAtUtc,
    from: c.currentWeights,
    to: firstAsk,
    verdict: c.decision,
    rationale: RATIONALE[c.case] ?? "",
    source: c,
    checks: [
      { gate: "SERV", name: "SERV reasoning", state: servOk ? "pass" : "warn", detail: servOk ? `${pct(c.serv.suggestedWeights.momentum)} / ${pct(c.serv.suggestedWeights.reversal)}` : "fallback", note: (c.serv.regime ?? "—").toLowerCase() },
      { gate: "Math", name: "Math gate", state: c.gate.passed ? "pass" : "fail", detail: signed(c.gate.pastSegmentDeltaPct, 3), note: c.gate.weightsInBounds ? "needs +0.06%" : "outside 15–85%" },
      { gate: "Reppo", name: "Reppo review", state: rs, detail: rd, note: rn },
    ],
  };
}

export const requests: ChangeRequest[] = proof.cases.map(build);
export const requestById = (id: string) => requests.find((r) => r.id === id);

export type ReplayRequest = { market: string; index: number; status: string; deltaPct: number | null; synthetic: boolean };
export const replayRequests: ReplayRequest[] = evaluation.results.flatMap((r) =>
  (r.adaptations.events ?? []).map((e) => ({ market: r.name, index: e.index, status: e.status, deltaPct: e.deltaPct, synthetic: r.synthetic })),
);

export const verdictLabel = (v: Verdict) => (v === "SHIP" ? "Shipped" : v === "REVIEW" ? "Needs review" : "Blocked");
export const verdictTone = (v: Verdict) => (v === "SHIP" ? "ok" : v === "REVIEW" ? "warn" : "no");
export const stateTone = (s: CheckState) => (s === "pass" ? "ok" : s === "fail" ? "no" : s === "warn" ? "warn" : "idle");
