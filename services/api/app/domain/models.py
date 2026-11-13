"""Typed Pydantic contracts for Aptura's replay, strategies, supervisor, and evaluations."""

from __future__ import annotations

from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


StrategyId = Literal["momentum", "reversal"]
SignalAction = Literal["BUY", "WAIT", "EXIT"]
DecisionAction = Literal["BUY", "WAIT", "EXIT", "AVOID"]
GuardianStatus = Literal["ALLOW", "CAUTION", "BLOCK"]
RiskProfile = Literal["conservative", "balanced", "aggressive"]
TrackId = Literal["adaptive", "fixed_50_50", "momentum_only", "cash"]
RunStatus = Literal["READY", "RUNNING", "PAUSED", "FINISHED"]
AdaptationStatus = Literal[
    "DETECTED",
    "PROPOSED",
    "PENDING_REVIEW",
    "VALIDATING",
    "ACCEPTED",
    "REJECTED",
    "FAILED",
]


class Candle(BaseModel):
    index: int
    timestamp: int
    observedAt: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    poolId: str
    source: str
    timeframe: str
    isClosed: bool = True


class DatasetMetadata(BaseModel):
    id: str
    name: str
    scenarioLabel: str
    description: str
    regimeSummary: str
    poolAddress: str
    chain: str
    baseAsset: str
    priceCurrency: str = "USD"
    quoteAsset: str
    source: str
    sourceUrl: str
    timeframe: str
    candleCount: int
    startTimeUtc: str
    endTimeUtc: str
    fetchedAtUtc: str
    sha256Hash: str
    completenessScore: float
    gapCount: int
    isSynthetic: bool
    recommended: bool


class Signal(BaseModel):
    id: str
    strategyId: StrategyId
    observedAt: str
    candleIndex: int
    action: SignalAction
    strength: float = Field(ge=0.0, le=1.0)
    indicators: dict[str, float] = Field(default_factory=dict)
    evidence: list[str] = Field(default_factory=list)
    rationale: str = ""


class RiskGuardianAssessment(BaseModel):
    observedAt: str
    candleIndex: int
    status: GuardianStatus
    realizedVolatilityPct: float
    volumeRatio: float
    dataCompletenessOk: bool
    exposurePct: float
    reasons: list[str]
    evidenceIds: list[str]


class SupervisorDecision(BaseModel):
    id: str
    runId: str
    observedAt: str
    candleIndex: int
    configVersion: str
    action: DecisionAction
    weights: dict[str, float]
    guardian: GuardianStatus
    guardianReasons: list[str] = Field(default_factory=list)
    combinedScore: float
    evidenceIds: list[str]
    reason: str
    provenance: Literal["DETERMINISTIC"] = "DETERMINISTIC"


class ShadowSignalOutcome(BaseModel):
    signalId: str
    strategyId: StrategyId
    issuedAtIndex: int
    maturedAtIndex: int
    observedAt: str
    maturedAt: str
    action: SignalAction
    strength: float
    entryPrice: float
    exitPrice: float
    netReturnPct: float
    wasHelpful: bool


class PaperOrder(BaseModel):
    id: str
    runId: str
    track: TrackId
    decisionObservedAt: str
    filledAt: str
    decisionCandleIndex: int
    fillCandleIndex: int
    side: Literal["BUY", "SELL"]
    referencePrice: float
    fillPrice: float
    quantity: float
    notionalUsd: float
    feeUsd: float
    slippageUsd: float
    realizedPnlUsd: float
    configVersion: str
    reason: str


class EquityPoint(BaseModel):
    candleIndex: int
    observedAt: str
    closePrice: float
    adaptiveEquity: float
    fixedEquity: float
    momentumOnlyEquity: float
    cashEquity: float
    adaptiveDrawdownPct: float
    fixedDrawdownPct: float
    momentumOnlyDrawdownPct: float
    adaptiveExposurePct: float
    configVersion: str


class TrackMetrics(BaseModel):
    track: TrackId
    label: str
    initialCapitalUsd: float
    finalEquityUsd: float
    netReturnPct: float
    maxDrawdownPct: float
    tradeCount: int
    totalFeesUsd: float
    totalSlippageUsd: float
    avgExposurePct: float
    sharpeLikeRatio: float
    winCount: int
    lossCount: int


class ConfigVersionRecord(BaseModel):
    version: str
    runId: str
    createdAt: str
    candleIndex: int
    weights: dict[str, float]
    mechanism: Literal["INITIAL", "FAST_MATHEMATICAL_SHIFT", "REVIEWED_PROPOSAL"]
    sourceEventId: Optional[str] = None
    rationale: str


class SERVProposal(BaseModel):
    hypothesis: str
    evidenceIds: list[str]
    suggestedWeights: dict[str, float]
    assumptions: list[str]
    uncertainties: list[str]
    schemaValid: bool
    modelUsed: str
    provenance: Literal["SERV_GENERATED", "DETERMINISTIC_FALLBACK"]
    generatedAt: str
    regimeDiagnosis: Optional[Literal["TRENDING", "MEAN_REVERTING", "HIGH_VOLATILITY_CHOP", "UNCERTAIN"]] = None
    buyThresholdDelta: float = 0.0
    latencyMs: Optional[int] = None
    responseId: Optional[str] = None


class ValidationGateResult(BaseModel):
    passed: bool
    weightsInBounds: bool
    sampleSizeSufficient: bool
    noFutureLeakage: bool
    cooldownRespected: bool
    evidenceVerified: bool
    pastSegmentCandidateReturnPct: float
    pastSegmentBaselineReturnPct: float
    pastSegmentDeltaPct: float
    validationWindowBars: int
    summary: str


class ReppoEvaluationRecord(BaseModel):
    evalId: str
    adaptationEventId: str
    runId: str
    type: Literal["plan", "trace", "action"]
    status: Literal["PENDING", "SETTLED", "FAILED", "UNCONFIGURED"]
    submittedAt: str
    minSettleAt: Optional[str] = None
    settledAt: Optional[str] = None
    payload: str
    criteria: list[str]
    context: str
    requestHash: str
    score: Optional[float] = None
    decision: Optional[Literal["accept", "revise", "reject"]] = None
    confidence: Optional[Literal["high", "medium", "low"]] = None
    route: Optional[str] = None
    critique: Optional[str] = None
    verdicts: list[dict[str, Any]] = Field(default_factory=list)
    provenance: Literal["REPPO_LIVE", "REPPO_UNCONFIGURED"]
    providerStatus: Optional[str] = None
    creditsCharged: Optional[int] = None
    rubricScores: dict[str, float] = Field(default_factory=dict)


class AdaptationEvent(BaseModel):
    id: str
    runId: str
    detectedAt: str
    candleIndex: int
    mechanism: Literal["FAST_MATHEMATICAL_SHIFT", "REVIEWED_PROPOSAL"]
    status: AdaptationStatus
    fromVersion: str
    proposedVersion: Optional[str] = None
    oldWeights: list[float]
    proposedWeights: Optional[list[float]] = None
    triggerMetric: str
    maturedSampleCount: int
    momentumTrailingScore: float
    reversalTrailingScore: float
    evidenceIds: list[str]
    rationale: str
    servProposal: Optional[SERVProposal] = None
    validationResult: Optional[ValidationGateResult] = None
    evaluationId: Optional[str] = None
    reppoStatus: Optional[str] = None
    rejectionReason: Optional[str] = None
    activatedAt: Optional[str] = None
    provenanceBadges: list[str] = Field(default_factory=list)


class ReplayCreateRequest(BaseModel):
    datasetId: str = "momentum-breakdown"
    seed: int = 42
    initialCapitalUsd: float = Field(default=1000.0, ge=100.0, le=1000000.0)
    riskProfile: RiskProfile = "conservative"
    feeBps: float = Field(default=20.0, ge=0.0, le=200.0)
    slippageBps: float = Field(default=15.0, ge=0.0, le=200.0)
    warmupBars: int = Field(default=20, ge=10, le=50)
    evaluationHorizonBars: int = Field(default=4, ge=2, le=16)


class ReplayAdvanceRequest(BaseModel):
    steps: int = Field(default=1, ge=1, le=500)


class ReplaySnapshot(BaseModel):
    runId: str
    dataset: DatasetMetadata
    seed: int
    status: RunStatus
    cursor: int
    totalCandles: int
    currentObservedAt: str
    configVersion: str
    activeWeights: dict[str, float]
    initialCapitalUsd: float
    riskProfile: RiskProfile
    feeBps: float
    slippageBps: float
    warmupBars: int
    evaluationHorizonBars: int
    visibleCandles: list[Candle]
    latestSignals: dict[str, Signal]
    latestDecision: Optional[SupervisorDecision] = None
    latestGuardian: Optional[RiskGuardianAssessment] = None
    strategyPerformance: dict[str, dict[str, Any]]
    recentDecisions: list[SupervisorDecision]
    adaptationEvents: list[AdaptationEvent]
    configHistory: list[ConfigVersionRecord]
    paperOrders: list[PaperOrder]
    equityCurve: list[EquityPoint]
    metricsComparison: dict[str, TrackMetrics]
    evaluations: list[ReppoEvaluationRecord]
    maturedOutcomes: list[ShadowSignalOutcome]


class SuperviseRequest(BaseModel):
    agentName: str = Field(default="external-trading-agent", min_length=1, max_length=80)
    datasetId: str = "momentum-breakdown"
    cursorIndex: Optional[int] = Field(default=None, ge=30, le=5000)
    currentWeights: dict[str, float] = Field(default_factory=lambda: {"momentum": 0.60, "reversal": 0.40})
    proposedWeights: Optional[dict[str, float]] = None
    rationale: Optional[str] = Field(default=None, max_length=1200)
    runReppoReview: bool = False
    waitForReppo: bool = False


class SuperviseResponse(BaseModel):
    requestId: str
    agentName: str
    datasetId: str
    datasetName: str
    observedAtUtc: str
    cursorIndex: int
    decision: Literal["SHIP", "REVIEW", "BLOCK"]
    currentWeights: dict[str, float]
    proposedWeights: dict[str, float]
    servProposal: SERVProposal
    deterministicGate: ValidationGateResult
    reppoEvaluation: Optional[ReppoEvaluationRecord] = None
    unitEconomics: dict[str, Any]
    summary: str
