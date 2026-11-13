"use client";



import React, { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";

import Link from "next/link";

import { useSearchParams } from "next/navigation";

import {

  AdaptationEvent,

  DatasetMetadata,

  ReplaySnapshot,

  ReppoEvaluationRecord,

  advanceReplayRun,

  createReplayRun,

  fetchDatasets,

  fetchReplaySnapshot,

  formatPrice,

  formatUtcShort,

  pollReppoEvaluation,

  resetReplayRun,

  seekReplayRun,

  submitReppoEvaluation,

} from "@/lib/contracts";

import MarketReplayChart from "@/components/MarketReplayChart";

import LiveWorkspace from "@/components/LiveWorkspace";
import ResearchControls from "@/components/ResearchControls";
import InterventionReport from "@/components/InterventionReport";
import WorkspaceNav from "@/components/WorkspaceNav";
import ThreeGatePipeline from "@/components/ThreeGatePipeline";
import AgentSupervisePanel from "@/components/AgentSupervisePanel";

import { ArrowUpRight, ArrowDownToLine, Play, Pause, RotateCcw, StepForward, Activity, Wallet, TrendingUp, ShieldCheck, ArrowRight, X } from "lucide-react";

import EquityComparisonChart from "@/components/EquityComparisonChart";



function TerminalWorkspace() {

  const searchParams = useSearchParams();



  const initialScenario = searchParams.get("scenario") || "momentum-breakdown";

  const initialCapital = Number(searchParams.get("capital")) || 1000;

  const initialRisk =

    (searchParams.get("risk") as "conservative" | "balanced" | "aggressive") || "conservative";

  const initialSpeed = (Number(searchParams.get("speed")) as 1 | 4 | 16) || 4;

  const autoRunParam = searchParams.get("autorun") === "1";



  const [datasets, setDatasets] = useState<DatasetMetadata[]>([]);

  const [selectedDatasetId, setSelectedDatasetId] = useState<string>(initialScenario);

  const [capitalUsd, setCapitalUsd] = useState<number>(initialCapital);

  const [riskProfile, setRiskProfile] = useState<"conservative" | "balanced" | "aggressive">(

    initialRisk

  );

  const [speed, setSpeed] = useState<1 | 4 | 16>(initialSpeed);



  const [snapshot, setSnapshot] = useState<ReplaySnapshot | null>(null);

  const [isPlaying, setIsPlaying] = useState<boolean>(autoRunParam);

  const [loading, setLoading] = useState<boolean>(true);

  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const [stepping, setStepping] = useState<boolean>(false);



  const [selectedAdaptationId, setSelectedAdaptationId] = useState<string | null>(null);



  const [chartMetricMode, setChartMetricMode] = useState<"equity" | "drawdown">("equity");



  const [reppoBusy, setReppoBusy] = useState<boolean>(false);

  const [activeEvalRecord, setActiveEvalRecord] = useState<ReppoEvaluationRecord | null>(null);




  const prevAdaptationCountRef = useRef<number>(0);



  // Load dataset catalog and create initial replay session

  const initSession = useCallback(

    async (

      dsId: string,

      cap: number,

      risk: "conservative" | "balanced" | "aggressive",

      shouldAutoAdvance: boolean = false

    ) => {

      setLoading(true);

      setErrorMsg(null);

      setIsPlaying(false);

      try {

        const dsList = await fetchDatasets();

        setDatasets(dsList);

        const validId = dsList.some((d) => d.id === dsId) ? dsId : dsList[0]?.id || "momentum-breakdown";

        const snap = await createReplayRun({

          datasetId: validId,

          seed: 42,

          initialCapitalUsd: cap,

          riskProfile: risk,

        });

        // Advance past warm-up + first adaptation if autorun so judges immediately see real activity, or keep at bar 0 if reset

        if (shouldAutoAdvance) {

          const advanced = await advanceReplayRun(snap.runId, 50);

          setSnapshot(advanced);

          prevAdaptationCountRef.current = advanced.adaptationEvents.length;

          if (advanced.adaptationEvents.length > 0) {

            setSelectedAdaptationId(

              advanced.adaptationEvents[advanced.adaptationEvents.length - 1].id

            );

          }

          if (advanced.evaluations.length > 0) {

            setActiveEvalRecord(advanced.evaluations[0]);

          }

          setIsPlaying(false);

        } else {

          setSnapshot(snap);

          prevAdaptationCountRef.current = snap.adaptationEvents.length;

          setSelectedAdaptationId(null);

          if (snap.evaluations.length > 0) {

            setActiveEvalRecord(snap.evaluations[0]);

          }

        }

      } catch (err: unknown) {

        setErrorMsg(err instanceof Error ? err.message : "Unable to connect to Aptura replay engine.");

      } finally {

        setLoading(false);

      }

    },

    []

  );



  useEffect(() => {

    initSession(selectedDatasetId, capitalUsd, riskProfile, autoRunParam);

    // eslint-disable-next-line react-hooks/exhaustive-deps

  }, []);



  const handleStep = useCallback(

    async (stepsCount: number = 1) => {

      if (!snapshot || stepping || snapshot.status === "FINISHED") return;

      setStepping(true);

      try {

        const nextSnap = await advanceReplayRun(snapshot.runId, stepsCount);

        setSnapshot(nextSnap);

        if (nextSnap.adaptationEvents.length > prevAdaptationCountRef.current) {

          const newest = nextSnap.adaptationEvents[nextSnap.adaptationEvents.length - 1];

          setSelectedAdaptationId(newest.id);



        }

        prevAdaptationCountRef.current = nextSnap.adaptationEvents.length;

        if (nextSnap.status === "FINISHED") {

          setIsPlaying(false);

        }

      } catch (err: unknown) {

        setErrorMsg(err instanceof Error ? err.message : "Failed to advance replay.");

        setIsPlaying(false);

      } finally {

        setStepping(false);

      }

    },

    [snapshot, stepping]

  );



  // Playback loop

  useEffect(() => {

    if (!isPlaying || !snapshot || snapshot.status === "FINISHED") return;

    const intervalMs = speed === 16 ? 220 : speed === 4 ? 480 : 950;

    const stepsPerTick = speed === 16 ? 3 : 1;

    const timer = setInterval(() => {

      handleStep(stepsPerTick);

    }, intervalMs);

    return () => clearInterval(timer);

  }, [isPlaying, snapshot, speed, handleStep]);



  // Keyboard shortcuts (Space = Play/Pause, ArrowRight = Step +1)

  useEffect(() => {

    const onKeyDown = (e: KeyboardEvent) => {

      if (

        document.activeElement &&

        ["INPUT", "SELECT", "TEXTAREA", "BUTTON"].includes(document.activeElement.tagName)

      ) {

        return;

      }

      if (e.code === "Space") {

        e.preventDefault();

        setIsPlaying((p) => !p);

      } else if (e.code === "ArrowRight") {

        e.preventDefault();

        setIsPlaying(false);

        handleStep(1);

      }

    };

    window.addEventListener("keydown", onKeyDown);

    return () => window.removeEventListener("keydown", onKeyDown);

  }, [handleStep]);



  const handleReset = async () => {

    if (!snapshot) return;

    setIsPlaying(false);

    setStepping(true);

    try {

      const resetSnap = await resetReplayRun(snapshot.runId);

      setSnapshot(resetSnap);

      prevAdaptationCountRef.current = 0;

      setSelectedAdaptationId(null);

    } catch (err: unknown) {

      setErrorMsg(err instanceof Error ? err.message : "Failed to reset replay.");

    } finally {

      setStepping(false);

    }

  };



  const handleSeek = async (targetIdx: number) => {

    if (!snapshot || stepping) return;

    setIsPlaying(false);

    setStepping(true);

    try {

      const sought = await seekReplayRun(snapshot.runId, targetIdx);

      setSnapshot(sought);

      prevAdaptationCountRef.current = sought.adaptationEvents.length;

    } catch (err: unknown) {

      setErrorMsg(err instanceof Error ? err.message : "Failed to seek replay cursor.");

    } finally {

      setStepping(false);

    }

  };



  const handleJumpToNextAdaptation = async () => {

    if (!snapshot || stepping) return;

    setIsPlaying(false);

    // Advance in chunks of 30 bars if no adaptation yet, or 18 bars to trigger the next drift assessment

    const jumpSteps = snapshot.cursor < 26 ? 28 - snapshot.cursor : 18;

    await handleStep(Math.max(1, jumpSteps));

  };



  const handleScenarioChange = async (newDatasetId: string) => {

    setSelectedDatasetId(newDatasetId);

    await initSession(newDatasetId, capitalUsd, riskProfile, false);

  };



  const selectedAdaptation: AdaptationEvent | null = useMemo(() => {

    if (!snapshot || snapshot.adaptationEvents.length === 0) return null;

    if (selectedAdaptationId) {

      const found = snapshot.adaptationEvents.find((e) => e.id === selectedAdaptationId);

      if (found) return found;

    }

    return snapshot.adaptationEvents[snapshot.adaptationEvents.length - 1];

  }, [snapshot, selectedAdaptationId]);



  const handleSubmitReppo = async (adaptationId: string) => {

    setReppoBusy(true);

    try {

      const rec = await submitReppoEvaluation(adaptationId);

      setActiveEvalRecord(rec);

      if (snapshot) {

        try {

          const refreshed = await fetchReplaySnapshot(snapshot.runId);

          setSnapshot(refreshed);

        } catch {

          const updatedEvents = snapshot.adaptationEvents.map((e) =>

            e.id === adaptationId

              ? {

                  ...e,

                  evaluationId: rec.evalId,

                  reppoStatus: rec.status,

                  provenanceBadges: rec.status !== "PENDING" || e.provenanceBadges.includes("PENDING REVIEW")

                    ? e.provenanceBadges

                    : [...e.provenanceBadges, "PENDING REVIEW"],

                }

              : e

          );

          const existingEvals = snapshot.evaluations.filter((ev) => ev.evalId !== rec.evalId);

          setSnapshot({

            ...snapshot,

            adaptationEvents: updatedEvents,

            evaluations: [rec, ...existingEvals],

          });

        }

      }

    } catch (err: unknown) {

      setErrorMsg(err instanceof Error ? err.message : "Failed to submit Reppo evaluation.");

    } finally {

      setReppoBusy(false);

    }

  };



  const handlePollReppo = useCallback(async (evalId: string) => {

    setReppoBusy(true);

    try {

      const rec = await pollReppoEvaluation(evalId);

      setActiveEvalRecord(rec);

      setSnapshot((prev) => {

        if (!prev) return prev;

        const existingEvals = prev.evaluations.filter((ev) => ev.evalId !== rec.evalId);

        const updatedEvents = prev.adaptationEvents.map((e) =>

          e.id === rec.adaptationEventId

            ? {

                ...e,

                evaluationId: rec.evalId,

                reppoStatus: rec.status,

                provenanceBadges:

                  rec.status === "SETTLED"

                    ? Array.from(

                        new Set([

                          ...e.provenanceBadges.filter((b) => b !== "PENDING REVIEW"),

                          "REPPO REVIEWED",

                        ])

                      )

                    : e.provenanceBadges,

              }

            : e

        );

        return {

          ...prev,

          adaptationEvents: updatedEvents,

          evaluations: [rec, ...existingEvals],

        };

      });

    } catch (err: unknown) {

      setErrorMsg(err instanceof Error ? err.message : "Failed to poll Reppo evaluation.");

    } finally {

      setReppoBusy(false);

    }

  }, []);



  const handleExportAuditJson = async () => {

    if (!snapshot) return;

    const response = await fetch(`/api/replays/${snapshot.runId}/audit`);
    if (!response.ok) { setErrorMsg("Could not export the audit. Please retry."); return; }
    const audit = await response.json();
    const blob = new Blob([JSON.stringify(audit, null, 2)], { type: "application/json" });

    const url = URL.createObjectURL(blob);

    const a = document.createElement("a");

    a.href = url;

    a.download = `aptura_audit_${snapshot.dataset.id}_bar_${snapshot.cursor}.json`;

    a.click();

    URL.revokeObjectURL(url);

  };



  if (loading && !snapshot) return <div className="loading-page"><Activity size={32}/><h2>Preparing your workspace…</h2><p>Loading a historical replay.</p></div>;

  if (!snapshot) return <div className="loading-page"><h2>Let’s reconnect.</h2><p>{errorMsg || "The replay service is unavailable."}</p><button className="btn btn-dark" onClick={()=>initSession(selectedDatasetId,capitalUsd,riskProfile)}>Try again</button><Link href="/">Back home</Link></div>;

  const decision=snapshot.latestDecision;

  const guardian=snapshot.latestGuardian;

  const metrics=snapshot.metricsComparison.adaptive;

  const latest=snapshot.visibleCandles.at(-1);

  const money=(n:number)=>n.toLocaleString("en-US",{style:"currency",currency:"USD",maximumFractionDigits:2});

  const runState=isPlaying?"Playing":snapshot.status==="FINISHED"?"Finished":snapshot.cursor>0?"Paused":"Ready";

  const selectedEvalRecord=selectedAdaptation?(snapshot.evaluations.find(ev=>ev.adaptationEventId===selectedAdaptation.id)||(activeEvalRecord?.adaptationEventId===selectedAdaptation.id?activeEvalRecord:null)):null;

  return <div className="workspace-shell"><WorkspaceNav/><main className="workspace-main" id="overview">

   <header className="workspace-header"><div><span className="kicker">YOUR RESEARCH SPACE</span><h1>Overview<span className="header-dot">.</span></h1></div><div className="header-actions"><span className="badge">{snapshot.dataset.isSynthetic?"SYNTHETIC":"HISTORICAL REPLAY"}</span><button className="btn" onClick={handleExportAuditJson}><ArrowDownToLine size={16}/> Export run</button></div></header>

   <div className="workspace-context"><span><span className="tiny-dot"/> Paper trade <span className="muted">/</span> {snapshot.dataset.name}</span><span className="muted">{formatUtcShort(snapshot.currentObservedAt)}</span></div>

   {errorMsg&&<div className="notice" role="alert">{errorMsg}<button aria-label="Dismiss error" onClick={()=>setErrorMsg(null)}><X size={16}/></button></div>}

   <div className="metric-grid"><article className="metric-card metric-featured"><span><Wallet size={17}/> Paper balance</span><strong>{money(metrics?.finalEquityUsd??snapshot.initialCapitalUsd)}</strong><small>Simulated portfolio value</small></article><article className="metric-card"><span><TrendingUp size={17}/> Net return</span><strong className={(metrics?.netReturnPct||0)<0?"negative":""}>{(metrics?.netReturnPct||0).toFixed(2)}<em>%</em></strong><small>After fees & slippage</small></article><article className="metric-card"><span><ShieldCheck size={17}/> Max drawdown</span><strong>{(metrics?.maxDrawdownPct||0).toFixed(2)}<em>%</em></strong><small>Largest decline so far</small></article><article className="metric-card"><span><Activity size={17}/> Paper trades</span><strong>{metrics?.tradeCount||0}</strong><small>{snapshot.adaptationEvents.length} adaptation checks</small></article></div>

   <div className="replay-toolbar"><label><span className="sr-only">Replay scenario</span><select value={snapshot.dataset.id} onChange={e=>handleScenarioChange(e.target.value)} disabled={stepping||loading}>{datasets.map(d=><option key={d.id} value={d.id}>{d.scenarioLabel} · {d.name}</option>)}</select></label><div className="transport"><button id="replay-play-pause-btn" className="btn btn-dark" disabled={snapshot.status==="FINISHED"||loading} onClick={()=>setIsPlaying(p=>!p)}>{isPlaying?<Pause size={16}/>:<Play size={16}/>} {isPlaying?"Pause":"Play replay"}</button><button className="btn icon-btn" aria-label="Advance one candle" disabled={stepping||snapshot.status==="FINISHED"} onClick={()=>{setIsPlaying(false);handleStep(1);}}><StepForward size={17}/></button><select aria-label="Replay speed" value={speed} onChange={e=>setSpeed(Number(e.target.value) as 1|4|16)}>{[1,4,16].map(n=><option key={n} value={n}>{n}×</option>)}</select><button className="btn icon-btn" aria-label="Reset replay" disabled={stepping} onClick={handleReset}><RotateCcw size={16}/></button></div></div>

   <div className="dashboard-grid"><section className="panel market-panel"><div className="panel-heading"><div><h2>Market overview</h2><span className="muted">{snapshot.dataset.name} <span className="dot-divider">·</span> {snapshot.dataset.timeframe} candles</span></div><div className="market-price">{latest?formatPrice(latest.close):"—"}<small>{snapshot.dataset.priceCurrency}</small></div></div><MarketReplayChart candles={snapshot.visibleCandles} orders={snapshot.paperOrders} adaptations={snapshot.adaptationEvents} selectedAdaptationId={selectedAdaptation?.id||null} onSelectAdaptation={id=>{setSelectedAdaptationId(id);document.getElementById("activity")?.scrollIntoView({behavior:"smooth"});}} quoteAsset={snapshot.dataset.priceCurrency} baseAsset={snapshot.dataset.baseAsset}/><div className="chart-footer"><span>{runState} · {snapshot.cursor+1} / {snapshot.totalCandles} candles</span><input aria-label="Replay position" type="range" min={0} max={snapshot.totalCandles-1} value={snapshot.cursor} onChange={e=>handleSeek(Number(e.target.value))}/><button className="text-link" disabled={stepping||snapshot.status==="FINISHED"} onClick={handleJumpToNextAdaptation}>Skip ahead <ArrowRight size={14}/></button></div></section>

   <section className="panel decision-panel"><div className="panel-heading"><h2>Next move</h2><span className="badge">Supervisor</span></div><div className={`decision-orbit decision-${decision?.action?.toLowerCase()||"wait"}`}><span>Current decision</span><strong>{decision?.action||"WAIT"}</strong><small>{guardian?.status==="BLOCK"?"Risk limit reached":snapshot.cursor<snapshot.warmupBars?"Getting to know the market":"Based on completed candles"}</small></div><div className="risk-status"><ShieldCheck size={18}/><span>Risk guardian</span><strong>{guardian?.status||"Warming up"}</strong></div><details><summary>Why this decision?</summary><p>{decision?.reason||"Play the replay to gather enough observations."}</p><small>{decision?.evidenceIds.join(" · ")}</small></details></section>

   <section className="panel strategies-panel"><div className="panel-heading"><h2>Your strategies</h2><span className="muted">Current influence</span></div>{(["momentum","reversal"] as const).map((key,i)=>{const sig=snapshot.latestSignals[key];const weight=Math.round((snapshot.activeWeights[key]||0)*100);return <details className="strategy-row" key={key}><summary><span className={`strategy-avatar strategy-${key}`}>{i===0?<TrendingUp size={20}/>:<RotateCcw size={20}/>}</span><span className="strategy-name"><strong>{i===0?"Momentum scout":"Reversal scout"}</strong><small>{sig?.action||"Warming up"}</small></span><span className="strategy-weight"><strong>{weight}%</strong><progress max={100} value={weight}/></span></summary><p>{sig?.rationale||"Waiting for completed candles."}</p><small>{sig?.evidence.join(" · ")}</small></details>;})}<div className="panel-footnote">Weights change only after a check. <span>{snapshot.configVersion}</span></div></section>

   <section className="panel activity-panel" id="activity"><div className="panel-heading"><h2>Recent activity</h2><span className="badge">{snapshot.adaptationEvents.length} checks</span></div>{!snapshot.adaptationEvents.length?<div className="empty-state"><HistoryIcon/><h3>Room for the next insight.</h3><p>Changes and rejected proposals appear here as the replay runs.</p><button className="text-link" onClick={handleJumpToNextAdaptation} disabled={stepping}>Advance replay <ArrowRight size={14}/></button></div>:<><div className="event-list">{[...snapshot.adaptationEvents].reverse().map(ev=><button className={`event-row ${selectedAdaptation?.id===ev.id?"selected":""}`} key={ev.id} onClick={()=>setSelectedAdaptationId(ev.id)}><span className={`event-indicator ${ev.status==="ACCEPTED"?"accepted":""}`}><GitBranchIcon/></span><span><strong>{ev.status==="ACCEPTED"?"Weights adjusted":ev.status==="REJECTED"?"Change declined":"Change under review"}</strong><small>{formatUtcShort(ev.detectedAt)}</small></span><ArrowUpRight size={16}/></button>)}</div>{selectedAdaptation&&<details className="event-details" key={selectedAdaptation.id}><summary>Inspect selected check</summary><span className="badge">{selectedAdaptation.status}</span><p>{selectedAdaptation.rationale}</p><p>{selectedAdaptation.rejectionReason}</p><p>Momentum / Reversal: {selectedAdaptation.oldWeights.map(w=>Math.round(w*100)+"%").join(" / ")} → {selectedAdaptation.proposedWeights?.map(w=>Math.round(w*100)+"%").join(" / ")||"No change"}</p><p>{selectedAdaptation.validationResult?.summary}</p><p>Mechanism: {selectedAdaptation.mechanism}</p><p>Reasoning: {selectedAdaptation.servProposal?.provenance||"No proposal"}</p><p>{selectedAdaptation.servProposal?.hypothesis}</p><small>Evidence: {selectedAdaptation.evidenceIds.join(", ")}</small><div className="detail-actions"><button className="btn" onClick={()=>handleSeek(selectedAdaptation.candleIndex)}>Go to candle</button><button className="btn" disabled={reppoBusy} onClick={()=>handleSubmitReppo(selectedAdaptation.id)}>Request Reppo review</button></div>{selectedEvalRecord&&<div><p>Reppo: {selectedEvalRecord.status} · {selectedEvalRecord.evalId}</p><p>{selectedEvalRecord.critique}</p><button className="btn" disabled={reppoBusy} onClick={()=>handlePollReppo(selectedEvalRecord.evalId)}>Refresh review</button></div>}<small>Reppo reviews reasoning, not investment performance.</small></details>}</>}</section>

   <section className="panel performance-panel" id="performance"><div className="panel-heading"><div><h2>How did it compare?</h2><span className="muted">Same market. Same starting balance.</span></div><div className="segmented"><button className={chartMetricMode==="equity"?"active":""} onClick={()=>setChartMetricMode("equity")}>Balance</button><button className={chartMetricMode==="drawdown"?"active":""} onClick={()=>setChartMetricMode("drawdown")}>Drawdown</button></div></div><InterventionReport runId={snapshot.runId} cursor={snapshot.cursor}/><div className="chart-legend"><span className="legend-adaptive">Adaptive</span><span className="legend-fixed">Fixed 50/50</span><span className="legend-momentum">Momentum</span><span className="legend-cash">Cash</span></div><EquityComparisonChart equityCurve={snapshot.equityCurve} initialCapitalUsd={snapshot.initialCapitalUsd} mode={chartMetricMode}/><details><summary>Compare all results</summary><div className="table-scroll"><table><thead><tr><th>Strategy</th><th>Balance</th><th>Return</th><th>Drawdown</th><th>Trades</th><th>Fees</th><th>Slippage</th><th>Exposure</th></tr></thead><tbody>{Object.values(snapshot.metricsComparison).map(m=><tr key={m.track}><td>{m.label}</td><td>{money(m.finalEquityUsd)}</td><td>{m.netReturnPct.toFixed(2)}%</td><td>{m.maxDrawdownPct.toFixed(2)}%</td><td>{m.tradeCount}</td><td>{money(m.totalFeesUsd)}</td><td>{money(m.totalSlippageUsd)}</td><td>{m.avgExposurePct.toFixed(1)}%</td></tr>)}</tbody></table></div></details></section></div>

   {selectedAdaptation&&<ThreeGatePipeline event={selectedAdaptation} evalRecord={selectedEvalRecord} busy={reppoBusy} onTriggerAudit={handleSubmitReppo} onPollEval={handlePollReppo} onSeekCandle={handleSeek}/>}

   <AgentSupervisePanel datasets={datasets} defaultDatasetId={snapshot.dataset.id}/>

   <ResearchControls runId={snapshot.runId} datasetId={snapshot.dataset.id} synthetic={snapshot.dataset.isSynthetic} events={snapshot.adaptationEvents}/>
   <footer className="workspace-footer" id="sources"><span>SIMULATED P&L <span className="dot-divider">·</span> {snapshot.dataset.source}</span><details><summary>Methodology & sources</summary><p>Orders fill at the next candle’s open with {snapshot.feeBps} bps fees and {snapshot.slippageBps} bps slippage per side. Signals use completed candles. Outcomes mature after {snapshot.evaluationHorizonBars} bars.</p><p>Fast mathematical weight changes are separate from externally reviewed proposals. Neither SERV nor Reppo overrides risk limits.</p><a href={snapshot.dataset.sourceUrl} target="_blank" rel="noreferrer">Data source ↗</a><p>UTC: {snapshot.dataset.startTimeUtc} — {snapshot.dataset.endTimeUtc}</p><p>Dataset hash: {snapshot.dataset.sha256Hash}</p><p>Run: {snapshot.runId} · Seed {snapshot.seed}</p><button className="btn" onClick={handleExportAuditJson}>Download full evidence</button></details></footer>

  </main></div>;

}

function HistoryIcon(){return <RotateCcw size={26}/>;}

function GitBranchIcon(){return <Activity size={15}/>;}

function WorkspaceMode(){const params=useSearchParams();return params.has("scenario")||params.get("mode")==="replay"?<TerminalWorkspace/>:<LiveWorkspace/>;}

export default function TerminalPage(){return <Suspense fallback={<div className="loading-page">Loading workspace…</div>}><WorkspaceMode/></Suspense>;}

