import proofJson from "@/public/proof/live-proof.json";
import evalJson from "@/public/proof/evaluation.json";

export type ProofCase = {
  case: "rogue" | "bounded" | "revise" | "ship";
  title: string;
  requestId: string;
  agentName: string;
  dataset: string;
  observedAtUtc: string;
  decision: "SHIP" | "REVIEW" | "BLOCK";
  summary: string;
  currentWeights: { momentum: number; reversal: number };
  proposedWeights: { momentum: number; reversal: number };
  serv: { provenance: string; model: string; responseId: string | null; latencyMs: number | null; schemaValid: boolean; regime: string | null; hypothesis: string; suggestedWeights: Record<string, number>; uncertainties: string[] };
  gate: { passed: boolean; weightsInBounds: boolean; noFutureLeakage: boolean; cooldownRespected: boolean; sampleSizeSufficient: boolean; evidenceVerified: boolean; pastSegmentDeltaPct: number; validationWindowBars: number; summary: string };
  rounds?: { round: number; source: string; weights: { momentum: number; reversal: number }; servProvenance: string; servResponseId: string | null; hypothesis: string; gatePassed: boolean; gateSummary: string; pastWindowDeltaPct: number; reppoEvalId: string | null; reppoScore: number | null; reppoRoute: string | null; reppoCritique: string | null; verdict: "SHIP" | "REVIEW" | "BLOCK" }[];
  improvement?: { rounds: number; chosenRound?: number; firstVerdict: string; finalVerdict: string; firstPastWindowDeltaPct: number; finalPastWindowDeltaPct: number; deltaGainPct: number };
  reppo: null | { evalId: string; status: string; provenance: string; submittedAt: string; settledAt: string | null; score: number | null; decision: string | null; confidence: string | null; route: string | null; critique: string | null; rubricScores: Record<string, number>; creditsCharged: number | null; requestHash: string; payload: string };
};

export type EvalResult = {
  datasetId: string; name: string; scenario: string; synthetic: boolean; candles: number;
  tracks: Record<"adaptive" | "fixed_50_50" | "momentum_only" | "cash", { label: string; netReturnPct: number; maxDrawdownPct: number; trades: number; feesUsd: number }>;
  adaptiveMinusFixedPct: number | null;
  adaptations: { proposed: number; accepted: number; rejected: number; events?: { index: number; status: string; deltaPct: number | null }[] };
};

export type Evaluation = {
  generatedAtUtc: string; engine: string;
  summary: { datasets: number; adaptiveBeatFixedOnReal: number; realDatasets: number; adaptiveProfitableOnReal: number; cashBeatAdaptive: number; adaptationsProposed: number; adaptationsRejected: number };
  results: EvalResult[];
  candleFiles: Record<string, { sha256: string; source: string; sourceUrl: string; synthetic: boolean }>;
};

export const proof = proofJson as unknown as { recordedAtUtc: string; cases: ProofCase[] };
export const evaluation = evalJson as unknown as Evaluation;
export const rogue = proof.cases.find((c) => c.case === "rogue")!;
export const bounded = proof.cases.find((c) => c.case === "bounded")!;
export const revise = proof.cases.find((c) => c.case === "revise");
export const ship = proof.cases.find((c) => c.case === "ship");

export const pct = (w: number) => `${Math.round(w * 100)}%`;
export const signed = (n: number, d = 2) => `${n > 0 ? "+" : n < 0 ? "−" : ""}${Math.abs(n).toFixed(d)}%`;
export const shortId = (s: string | null | undefined, n = 10) => (s ? (s.length > n + 2 ? `${s.slice(0, n)}…` : s) : "—");
export const utc = (iso: string) => iso.replace("T", " ").replace(/(:\d\d)(\.\d+)?Z?$/, "$1").slice(0, 16) + " UTC";
