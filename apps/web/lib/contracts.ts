import { z } from "zod";

export const CandleSchema = z.object({
  index: z.number(),
  timestamp: z.number(),
  observedAt: z.string(),
  open: z.number(),
  high: z.number(),
  low: z.number(),
  close: z.number(),
  volume: z.number(),
  poolId: z.string(),
  source: z.string(),
  timeframe: z.string(),
  isClosed: z.boolean(),
});

export const DatasetMetadataSchema = z.object({
  id: z.string(),
  name: z.string(),
  scenarioLabel: z.string(),
  description: z.string(),
  regimeSummary: z.string(),
  poolAddress: z.string(),
  chain: z.string(),
  baseAsset: z.string(),
  priceCurrency: z.string().default("USD"),
  quoteAsset: z.string(),
  source: z.string(),
  sourceUrl: z.string(),
  timeframe: z.string(),
  candleCount: z.number(),
  startTimeUtc: z.string(),
  endTimeUtc: z.string(),
  fetchedAtUtc: z.string(),
  sha256Hash: z.string(),
  completenessScore: z.number(),
  gapCount: z.number(),
  isSynthetic: z.boolean(),
  recommended: z.boolean(),
});

export const SignalSchema = z.object({
  id: z.string(),
  strategyId: z.enum(["momentum", "reversal"]),
  observedAt: z.string(),
  candleIndex: z.number(),
  action: z.enum(["BUY", "WAIT", "EXIT"]),
  strength: z.number(),
  indicators: z.record(z.string(), z.number()),
  evidence: z.array(z.string()),
  rationale: z.string().optional().default(""),
});

export const RiskGuardianSchema = z.object({
  observedAt: z.string(),
  candleIndex: z.number(),
  status: z.enum(["ALLOW", "CAUTION", "BLOCK"]),
  realizedVolatilityPct: z.number(),
  volumeRatio: z.number(),
  dataCompletenessOk: z.boolean(),
  exposurePct: z.number(),
  reasons: z.array(z.string()),
  evidenceIds: z.array(z.string()),
});

export const SupervisorDecisionSchema = z.object({
  id: z.string(),
  runId: z.string(),
  observedAt: z.string(),
  candleIndex: z.number(),
  configVersion: z.string(),
  action: z.enum(["BUY", "WAIT", "EXIT", "AVOID"]),
  weights: z.record(z.string(), z.number()),
  guardian: z.enum(["ALLOW", "CAUTION", "BLOCK"]),
  guardianReasons: z.array(z.string()).optional().default([]),
  combinedScore: z.number(),
  evidenceIds: z.array(z.string()),
  reason: z.string(),
  provenance: z.string().optional().default("DETERMINISTIC"),
});

export const SERVProposalSchema = z.object({
  hypothesis: z.string(),
  evidenceIds: z.array(z.string()),
  suggestedWeights: z.record(z.string(), z.number()),
  assumptions: z.array(z.string()),
  uncertainties: z.array(z.string()),
  schemaValid: z.boolean(),
  modelUsed: z.string(),
  provenance: z.enum(["SERV_GENERATED", "DETERMINISTIC_FALLBACK"]),
  generatedAt: z.string(),
  regimeDiagnosis: z.string().nullable().optional(),
  buyThresholdDelta: z.number().optional().default(0),
  latencyMs: z.number().nullable().optional(),
  responseId: z.string().nullable().optional(),
});

export const ValidationGateResultSchema = z.object({
  passed: z.boolean(),
  weightsInBounds: z.boolean(),
  sampleSizeSufficient: z.boolean(),
  noFutureLeakage: z.boolean(),
  cooldownRespected: z.boolean(),
  evidenceVerified: z.boolean(),
  pastSegmentCandidateReturnPct: z.number(),
  pastSegmentBaselineReturnPct: z.number(),
  pastSegmentDeltaPct: z.number(),
  validationWindowBars: z.number(),
  summary: z.string(),
});

export const ReppoEvaluationRecordSchema = z.object({
  evalId: z.string(),
  adaptationEventId: z.string(),
  runId: z.string(),
  type: z.enum(["plan", "trace", "action"]),
  status: z.enum(["PENDING", "SETTLED", "FAILED", "UNCONFIGURED"]),
  submittedAt: z.string(),
  minSettleAt: z.string().nullable().optional(),
  settledAt: z.string().nullable().optional(),
  payload: z.string(),
  criteria: z.array(z.string()),
  context: z.string(),
  requestHash: z.string(),
  score: z.number().nullable().optional(),
  decision: z.enum(["accept", "revise", "reject"]).nullable().optional(),
  confidence: z.enum(["high", "medium", "low"]).nullable().optional(),
  route: z.string().nullable().optional(),
  critique: z.string().nullable().optional(),
  verdicts: z.array(z.record(z.string(), z.any())).optional().default([]),
  provenance: z.enum(["REPPO_LIVE", "REPPO_UNCONFIGURED"]),
  providerStatus: z.string().nullable().optional(),
  creditsCharged: z.number().nullable().optional(),
  rubricScores: z.record(z.string(), z.number()).optional().default({}),
});

export const AdaptationEventSchema = z.object({
  id: z.string(),
  runId: z.string(),
  detectedAt: z.string(),
  candleIndex: z.number(),
  mechanism: z.enum(["FAST_MATHEMATICAL_SHIFT", "REVIEWED_PROPOSAL"]),
  status: z.enum([
    "DETECTED",
    "PROPOSED",
    "PENDING_REVIEW",
    "VALIDATING",
    "ACCEPTED",
    "REJECTED",
    "FAILED",
  ]),
  fromVersion: z.string(),
  proposedVersion: z.string().nullable().optional(),
  oldWeights: z.array(z.number()),
  proposedWeights: z.array(z.number()).nullable().optional(),
  triggerMetric: z.string(),
  maturedSampleCount: z.number(),
  momentumTrailingScore: z.number(),
  reversalTrailingScore: z.number(),
  evidenceIds: z.array(z.string()),
  rationale: z.string(),
  servProposal: SERVProposalSchema.nullable().optional(),
  validationResult: ValidationGateResultSchema.nullable().optional(),
  evaluationId: z.string().nullable().optional(),
  reppoStatus: z.string().nullable().optional(),
  rejectionReason: z.string().nullable().optional(),
  activatedAt: z.string().nullable().optional(),
  provenanceBadges: z.array(z.string()).optional().default([]),
});

export const PaperOrderSchema = z.object({
  id: z.string(),
  runId: z.string(),
  track: z.enum(["adaptive", "fixed_50_50", "momentum_only", "cash"]),
  decisionObservedAt: z.string(),
  filledAt: z.string(),
  decisionCandleIndex: z.number(),
  fillCandleIndex: z.number(),
  side: z.enum(["BUY", "SELL"]),
  referencePrice: z.number(),
  fillPrice: z.number(),
  quantity: z.number(),
  notionalUsd: z.number(),
  feeUsd: z.number(),
  slippageUsd: z.number(),
  realizedPnlUsd: z.number(),
  configVersion: z.string(),
  reason: z.string(),
});

export const EquityPointSchema = z.object({
  candleIndex: z.number(),
  observedAt: z.string(),
  closePrice: z.number(),
  adaptiveEquity: z.number(),
  fixedEquity: z.number(),
  momentumOnlyEquity: z.number(),
  cashEquity: z.number(),
  adaptiveDrawdownPct: z.number(),
  fixedDrawdownPct: z.number(),
  momentumOnlyDrawdownPct: z.number(),
  adaptiveExposurePct: z.number(),
  configVersion: z.string(),
});

export const TrackMetricsSchema = z.object({
  track: z.enum(["adaptive", "fixed_50_50", "momentum_only", "cash"]),
  label: z.string(),
  initialCapitalUsd: z.number(),
  finalEquityUsd: z.number(),
  netReturnPct: z.number(),
  maxDrawdownPct: z.number(),
  tradeCount: z.number(),
  totalFeesUsd: z.number(),
  totalSlippageUsd: z.number(),
  avgExposurePct: z.number(),
  sharpeLikeRatio: z.number(),
  winCount: z.number(),
  lossCount: z.number(),
});

export const ConfigVersionRecordSchema = z.object({
  version: z.string(),
  runId: z.string(),
  createdAt: z.string(),
  candleIndex: z.number(),
  weights: z.record(z.string(), z.number()),
  mechanism: z.enum(["INITIAL", "FAST_MATHEMATICAL_SHIFT", "REVIEWED_PROPOSAL"]),
  sourceEventId: z.string().nullable().optional(),
  rationale: z.string(),
});

export const ShadowSignalOutcomeSchema = z.object({
  signalId: z.string(),
  strategyId: z.enum(["momentum", "reversal"]),
  issuedAtIndex: z.number(),
  maturedAtIndex: z.number(),
  observedAt: z.string(),
  maturedAt: z.string(),
  action: z.enum(["BUY", "WAIT", "EXIT"]),
  strength: z.number(),
  entryPrice: z.number(),
  exitPrice: z.number(),
  netReturnPct: z.number(),
  wasHelpful: z.boolean(),
});

export const ReplaySnapshotSchema = z.object({
  runId: z.string(),
  dataset: DatasetMetadataSchema,
  seed: z.number(),
  status: z.enum(["READY", "RUNNING", "PAUSED", "FINISHED"]),
  cursor: z.number(),
  totalCandles: z.number(),
  currentObservedAt: z.string(),
  configVersion: z.string(),
  activeWeights: z.record(z.string(), z.number()),
  initialCapitalUsd: z.number(),
  riskProfile: z.enum(["conservative", "balanced", "aggressive"]),
  feeBps: z.number(),
  slippageBps: z.number(),
  warmupBars: z.number(),
  evaluationHorizonBars: z.number(),
  visibleCandles: z.array(CandleSchema),
  latestSignals: z.record(z.string(), SignalSchema),
  latestDecision: SupervisorDecisionSchema.nullable().optional(),
  latestGuardian: RiskGuardianSchema.nullable().optional(),
  strategyPerformance: z.record(z.string(), z.record(z.string(), z.any())),
  recentDecisions: z.array(SupervisorDecisionSchema),
  adaptationEvents: z.array(AdaptationEventSchema),
  configHistory: z.array(ConfigVersionRecordSchema),
  paperOrders: z.array(PaperOrderSchema),
  equityCurve: z.array(EquityPointSchema),
  metricsComparison: z.record(z.string(), TrackMetricsSchema),
  evaluations: z.array(ReppoEvaluationRecordSchema),
  maturedOutcomes: z.array(ShadowSignalOutcomeSchema),
});

export type Candle = z.infer<typeof CandleSchema>;
export type DatasetMetadata = z.infer<typeof DatasetMetadataSchema>;
export type Signal = z.infer<typeof SignalSchema>;
export type RiskGuardianAssessment = z.infer<typeof RiskGuardianSchema>;
export type SupervisorDecision = z.infer<typeof SupervisorDecisionSchema>;
export type SERVProposal = z.infer<typeof SERVProposalSchema>;
export type ValidationGateResult = z.infer<typeof ValidationGateResultSchema>;
export type ReppoEvaluationRecord = z.infer<typeof ReppoEvaluationRecordSchema>;
export type AdaptationEvent = z.infer<typeof AdaptationEventSchema>;
export type PaperOrder = z.infer<typeof PaperOrderSchema>;
export type EquityPoint = z.infer<typeof EquityPointSchema>;
export type TrackMetrics = z.infer<typeof TrackMetricsSchema>;
export type ConfigVersionRecord = z.infer<typeof ConfigVersionRecordSchema>;
export type ShadowSignalOutcome = z.infer<typeof ShadowSignalOutcomeSchema>;
export type ReplaySnapshot = z.infer<typeof ReplaySnapshotSchema>;

export interface OnboardingPreferences {
  datasetId: string;
  initialCapitalUsd: number;
  riskProfile: "conservative" | "balanced" | "aggressive";
  speedMultiplier: 1 | 4 | 16;
  completedOnboarding: boolean;
}

export const DEFAULT_PREFERENCES: OnboardingPreferences = {
  datasetId: "momentum-breakdown",
  initialCapitalUsd: 1000,
  riskProfile: "conservative",
  speedMultiplier: 4,
  completedOnboarding: false,
};

export async function fetchDatasets(): Promise<DatasetMetadata[]> {
  const res = await fetch("/api/datasets", { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Failed to load datasets (HTTP ${res.status})`);
  }
  const raw = await res.json();
  return z.array(DatasetMetadataSchema).parse(raw);
}

export async function createReplayRun(params: {
  datasetId: string;
  seed?: number;
  initialCapitalUsd?: number;
  riskProfile?: "conservative" | "balanced" | "aggressive";
  feeBps?: number;
  slippageBps?: number;
}): Promise<ReplaySnapshot> {
  const res = await fetch("/api/replays", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      datasetId: params.datasetId,
      seed: params.seed ?? 42,
      initialCapitalUsd: params.initialCapitalUsd ?? 1000,
      riskProfile: params.riskProfile ?? "conservative",
      feeBps: params.feeBps ?? 20,
      slippageBps: params.slippageBps ?? 15,
    }),
  });
  if (!res.ok) {
    throw new Error(`Failed to create replay run (HTTP ${res.status})`);
  }
  const raw = await res.json();
  return ReplaySnapshotSchema.parse(raw);
}

export async function advanceReplayRun(runId: string, steps: number = 1): Promise<ReplaySnapshot> {
  const res = await fetch(`/api/replays/${encodeURIComponent(runId)}/advance`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ steps }),
  });
  if (!res.ok) {
    throw new Error(`Failed to advance replay run (HTTP ${res.status})`);
  }
  const raw = await res.json();
  return ReplaySnapshotSchema.parse(raw);
}

export async function seekReplayRun(runId: string, targetIndex: number): Promise<ReplaySnapshot> {
  const res = await fetch(`/api/replays/${encodeURIComponent(runId)}/seek`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ targetIndex }),
  });
  if (!res.ok) {
    throw new Error(`Failed to seek replay run (HTTP ${res.status})`);
  }
  const raw = await res.json();
  return ReplaySnapshotSchema.parse(raw);
}

export async function resetReplayRun(runId: string): Promise<ReplaySnapshot> {
  const res = await fetch(`/api/replays/${encodeURIComponent(runId)}/reset`, {
    method: "POST",
  });
  if (!res.ok) {
    throw new Error(`Failed to reset replay run (HTTP ${res.status})`);
  }
  const raw = await res.json();
  return ReplaySnapshotSchema.parse(raw);
}

export async function fetchReplaySnapshot(runId: string): Promise<ReplaySnapshot> {
  const res = await fetch(`/api/replays/${encodeURIComponent(runId)}`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch replay run (HTTP ${res.status})`);
  }
  const raw = await res.json();
  return ReplaySnapshotSchema.parse(raw);
}

export async function submitReppoEvaluation(adaptationId: string): Promise<ReppoEvaluationRecord> {
  const res = await fetch(`/api/adaptations/${encodeURIComponent(adaptationId)}/evaluate`, {
    method: "POST",
  });
  if (!res.ok) {
    throw new Error(`Failed to submit evaluation (HTTP ${res.status})`);
  }
  const raw = await res.json();
  return ReppoEvaluationRecordSchema.parse(raw);
}

export async function pollReppoEvaluation(evalId: string): Promise<ReppoEvaluationRecord> {
  const res = await fetch(`/api/evaluations/${encodeURIComponent(evalId)}`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Failed to poll evaluation (HTTP ${res.status})`);
  }
  const raw = await res.json();
  return ReppoEvaluationRecordSchema.parse(raw);
}

export const SuperviseResponseSchema = z.object({
  requestId: z.string(),
  agentName: z.string(),
  datasetId: z.string(),
  datasetName: z.string(),
  observedAtUtc: z.string(),
  cursorIndex: z.number(),
  decision: z.enum(["SHIP", "REVIEW", "BLOCK"]),
  currentWeights: z.record(z.string(), z.number()),
  proposedWeights: z.record(z.string(), z.number()),
  servProposal: SERVProposalSchema,
  deterministicGate: ValidationGateResultSchema,
  reppoEvaluation: ReppoEvaluationRecordSchema.nullable().optional(),
  unitEconomics: z.record(z.string(), z.any()),
  summary: z.string(),
});
export type SuperviseResponse = z.infer<typeof SuperviseResponseSchema>;

export async function runSuperviseService(params: {
  agentName: string;
  datasetId: string;
  currentWeights?: Record<string, number>;
  proposedWeights?: Record<string, number>;
  rationale?: string;
  runReppoReview?: boolean;
}): Promise<SuperviseResponse> {
  const res = await fetch("/api/v1/supervise", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const errBody = await res.json().catch(() => ({}));
    throw new Error(errBody.detail || `Supervise request failed (HTTP ${res.status})`);
  }
  const raw = await res.json();
  return SuperviseResponseSchema.parse(raw);
}

export function formatPrice(val: number): string {
  if (val === 0) return "0.00";
  if (val < 0.0001) return val.toFixed(8);
  if (val < 0.01) return val.toFixed(6);
  if (val < 1) return val.toFixed(5);
  return val.toFixed(2);
}

export function formatUtcShort(iso: string): string {
  if (!iso) return "—";
  return iso.replace("T", " ").replace(":00Z", " UTC").replace("Z", " UTC");
}
