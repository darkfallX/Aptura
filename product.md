> Live adaptation implementation: the primary workspace now connects fresh observed prices to strategy signals, delayed outcome evaluation, gated adaptation and prospective simulated execution. Historical replay remains separate. AI-generated proposals require SERV; external reviews require Reppo. Unconfigured providers must be displayed honestly, and deterministic adaptation must not be called an AI response.

> Updated direction — 11 November 2026: the default terminal and landing now show current on-chain trade data. Historical replay is an optional separate mode. Live market data and simulated-money strategy experiments are distinct. Free-provider polling is disclosed (15-second refresh; upstream delay may apply). The default experience uses plain language and spacious, border-free surfaces, preserving the sage/cream palette. Real-money order execution remains unimplemented.

# Aptura — Product Requirements & Experience Specification

**Status:** Hackathon MVP specification · **Version:** 1.0 · **Updated:** 2026-11-09  
**Event:** OpenServ Hackathon 02 · **Track:** Reppo · **Deadline:** 2026-11-15 23:59 UTC  
**Product type:** Web application, paper-trading research and strategy-supervision laboratory  
**One-line pitch:** *Markets change. Your strategies should too.*

> **Core promise:** Aptura supervises multiple algorithmic trading strategies, detects when their observed performance deteriorates, proposes controlled adaptations, and shows whether those changes actually help. It is a transparent experiment in adaptive decision-making—not a guaranteed-profit trading bot.

---

## 1. Product decision: three connected experiences, not one naked dashboard

A visitor should **never** arrive at a wall of charts with no explanation. The experience is deliberately split into:

| Route | Screen | Primary job |
|---|---|---|
| `/` | **Storytelling landing page** | Create curiosity, explain the problem in seconds, and show why the supervisor exists. |
| `/onboarding` | **Guided setup / demo selection** | Teach the interaction model, choose a historical replay, and set sensible defaults. |
| `/terminal` | **Adaptive AI Supervisor Terminal** | The single principal workspace: run replay, inspect agents, see decisions, audit adaptations, compare results. |

The terminal is one cohesive dashboard, **not the entire website**. This resolves the tension between a polished first impression and an efficient, judge-friendly demo.

### Navigation flow

`Landing → [Launch Simulator] → Onboarding → [Begin Replay] → Terminal`

Secondary direct path: `Landing → [Watch the System Adapt] → preconfigured guided replay in Terminal`.

- No account, wallet connection, Telegram integration, or payment required for the hackathon demo.
- Returning visitors can bypass onboarding; preserve setup in local storage or URL parameters.
- A persistent **Back to Home** link and **Restart Tour** action are available inside the terminal.
- Use URL-shareable replay presets, e.g. `/terminal?scenario=momentum-breakdown`.

## 2. Problem, users, and differentiation

**Problem:** A strategy can work in one market regime and deteriorate in another. Most signal interfaces show *what to trade*, but do not clearly reveal when an underlying strategy has become less reliable, what evidence triggered an adjustment, or whether the adjustment improved later outcomes.

**Primary users:** Crypto power users, quantitative hobbyists, bot builders, hackathon judges evaluating agent behavior. **Secondary:** Teams looking for a monitoring layer for existing automated strategies.

**Unique angle to demonstrate:**
1. **Supervision over prediction.** Compare strategies rather than pretend one AI knows where prices go.
2. **Adaptation as an observable event.** Show previous weights, evidence, proposed weights, evaluation status, decision, and version history.
3. **Independent gates.** External AI critique (Reppo) is separate from numerical market validation. Neither is treated as proof of the other.
4. **Counterfactual comparison.** Run a fixed-weight baseline through the identical data and realistic cost assumptions.
5. **Honest uncertainty.** WAIT/NO TRADE is a first-class decision; failed adaptations remain visible.

**What is NOT novel:** Momentum, mean-reversion, portfolio backtesting, adjustable strategy weights, or LLM-generated explanations in isolation. Do not market these as inventions.

## 3. Product narrative and landing page

### Visual direction

Premium, architectural, highly legible, **dark graphite / near-black base**, warm white typography, understated cool mint or icy-cyan accent for approved decisions, subdued amber for caution, and restrained red for failure. Motion should feel intentional, not like a casino.

- Strong typographic hierarchy; generous whitespace; crisp 1px borders; subtle grid/coordinate systems.
- Thin animated lines and shifting agent-weight bars; avoid gratuitous 3D, glowing coins, or large decorative mascots.
- One standout hero visualization: **three signal paths converge into a supervisor node; one path degrades; trust redistributes**.
- Charts should be readable at normal zoom. Display units, legends, data source, and simulated/live badges.
- Desktop-first for judge demo, responsive and usable on mobile. Respect `prefers-reduced-motion`.

### Landing-page sections (in order)

**1 — Hero (first viewport):**  
Eyebrow: `ADAPTIVE STRATEGY INTELLIGENCE // SIMULATION`  
Headline: **Markets change. Your strategies should too.**  
Subhead: *Meet the AI supervisor that watches trading strategies, questions failing assumptions, and tests every adjustment before trusting it.*  
Primary CTA: **Launch Simulator**. Secondary CTA: **See How It Works**.  
Hero visual: minimal animated network of Momentum Scout ↔ Reversal Scout → Supervisor, with Risk Guardian enforcing a guardrail.

**2 — The problem, told as a sequence:** `A strategy works → The market shifts → The same strategy starts failing → An ordinary bot keeps going`. Use scroll-linked stages or simple stepped cards; ensure content reads without animation.

**3 — How Aptura reacts:** Three numbered chapters: **Observe → Evaluate → Adapt**. Each reveals the evidence, a proposed modification, and an acceptance/rejection gate.

**4 — Proof, not promises:** Split panel illustrating **Fixed vs Adaptive** results and an actual audit record. Do not show fabricated outperformance as if measured; use `Illustrative interface` until linked to actual replay output.

**5 — Built for transparency:** Brief cards for reproducible replay, decision traces, human-readable reasons, and experimental guardrails. Explain SERV Reasoning and Reppo without pretending they execute trades or prove profitability.

**6 — Final CTA/footer:** **Run a historical replay**; links to repository, methodology, source acknowledgments, disclaimers, and hackathon attribution.

### Non-negotiable marketing language

Say **"simulated trades"**, **"historical replay"**, **"tested adaptation"**, **"strategy confidence"**. Avoid **"guaranteed profit"**, **"predicts every rug"**, **"unbeatable AI"**, or unqualified **"real-time learning"**. If only historical data powers the demo, do not label it live trading.

## 4. Onboarding: useful, not friction for friction's sake

**Goal:** Reach the first visible adaptation event quickly. Keep onboarding to **three short steps**; guest use must require no signup.

1. **Meet your team.** Three cards—Momentum Scout, Reversal Scout, Risk Guardian—with 1-sentence descriptions and the role of the Supervisor. A simple diagram makes the relationship obvious. Button: `Continue`.
2. **Choose a replay.** Scenario cards backed by actual available datasets: `Momentum Breakdown` (recommended), `Choppy Market`, and `Steady Trend`, **only if those datasets have been sourced and validated**. Until then, show one verified scenario. Each card lists token/pool, historical UTC date range, candle interval, and sample size. An explicitly synthetic tutorial may be offered but must be labeled `Synthetic demonstration`.
3. **Set your experiment.** Paper balance (default $1,000, illustrative), risk profile (`Conservative` default), replay speed (`1×`, `4×`, `16×`), and a plain disclosure about estimates, costs, and no real trading. Button: **Enter Terminal**.

- Provide `Skip tour / use recommended defaults` on every step.
- Never imply API access, wallet access, or real capital authorization.
- When the terminal opens, spotlight the `Start Replay` control and `Adaptation Timeline` once; allow dismissing the tour.

## 5. Terminal: single-workspace design

### Top bar

Logo + `SUPERVISION TERMINAL` · dataset label · `HISTORICAL REPLAY` badge · run state (`READY / RUNNING / PAUSED / FINISHED`) · `Reset` · links (`Methodology`, `Home`).

### Desktop layout

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│ APTURA      / TERMINAL       REPLAY ●          [Tour] [Methodology] [Reset] │
├─────────────────────────────────────────────────────────────────────────────┤
│ Scenario: Momentum Breakdown  [Change]  [▶ Play] [Ⅱ] [Speed ▾]  T+ 00:12  │
├──────────────────────────────────────────────┬──────────────────────────────┤
│ PRICE + TRADE SIGNAL CHART                  │ SUPERVISOR DECISION          │
│ - timestamped candles                       │ WAIT / BUY / EXIT / AVOID    │
│ - decisions and adaptation markers          │ Why now? Evidence summary   │
│ - replay cursor                             │ Risk gate: pass / block     │
├──────────────────────────────────────────────┼──────────────────────────────┤
│ STRATEGY CARDS                              │ ADAPTATION / AUDIT TIMELINE │
│ Momentum Scout   60% → 35%                  │ Detect → Propose → Evaluate │
│ Reversal Scout   40% → 65%                  │ → Backtest → Accept/Reject  │
│ Risk Guardian    CAUTION                    │ [Inspect event]             │
├──────────────────────────────────────────────┴──────────────────────────────┤
│ FIXED vs ADAPTIVE: EQUITY CURVES, METRICS, COSTS, VERSION CHANGE HISTORY    │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Interaction:** Selecting a chart marker focuses the matching event in the audit timeline. Selecting a timeline event moves the replay cursor to the corresponding timestamp. Agent cards show current signal, weight, recent realized outcomes, and provenance.

### Main terminal modules and their data

| Module | Must display | User action |
|---|---|---|
| Replay controls | Dataset, UTC timeline, candle frequency, speed, play/pause/reset | Play, pause, step, seek if available |
| Market chart | OHLCV, strategy signals, executed paper trades, adaptation markers | Hover for point-in-time facts |
| Agent cards | Current signal, trust weight, trailing *matured* results | Click for signal rules/history |
| Supervisor card | BUY / WAIT / EXIT / AVOID + evidence IDs + risk gate | Expand decision trace |
| Adaptation timeline | Detected drift, proposal, pending Reppo, numeric validation, accepted/rejected | Inspect proposal/evidence |
| Results compare | Adaptive vs fixed identical dataset, simulated return, max drawdown, fees/slippage, trade count | Switch metrics, export run |
| Reppo evidence drawer | Evaluation ID, status, real verdict/critique, timestamp, link if supported | Refresh pending evaluation |

### Microinteractions that actually teach

- When performance deterioration is detected: quietly pulse a border; freeze the event in the timeline without automatically interrupting playback.
- A weight change animates `60/40 → 35/65` **only after activation**, not merely after proposal.
- Pending Reppo shows an honest `Evaluation queued / waiting` indicator; never simulate instant settlement.
- If validation rejects a proposal, show a prominent **REJECTED — baseline retained** explanation.
- A badge differentiates `DETERMINISTIC`, `SERV GENERATED`, `REPPO REVIEWED`, `HISTORICAL`, and `ILLUSTRATIVE` evidence.

## 6. Decision system and technical behavior

### MVP actors

- **Momentum Scout:** deterministic trend/momentum features over completed candles; emits `BUY`, `WAIT`, `EXIT` plus normalized strength and evidence.
- **Reversal Scout:** deterministic mean-reversion/reversal features over completed candles; same output schema.
- **Risk Guardian:** deterministic volatility / insufficient data / liquidity-quality checks. Emits `ALLOW`, `CAUTION`, or `BLOCK`. Initial OHLCV-only build **must not** claim to know creator wallets, holders, or actual liquidity if those feeds are absent.
- **Adaptive Supervisor:** combines strategy recommendations using current weights, applies risk gate and position rules, creates timestamped decision records, and updates weights based on eligible matured observations.
- **SERV Reasoning Analyst:** when a drift trigger occurs, generates a *bounded, structured* explanation and an adaptation proposal based solely on provided past information; no direct order execution.
- **Reppo External Reviewer:** asynchronously critiques the proposal/trace. Its accept/revise/reject result informs review but never substitutes for backtesting or hard safety constraints.

### A valid adaptation cycle

1. At replay time `t`, ingest only candle data finalized at or before `t`.
2. Generate strategy signals and paper decisions under the active immutable configuration version.
3. Record all strategies' **shadow signals** so an unselected strategy can still be assessed fairly after the configured outcome horizon has elapsed.
4. When outcomes mature, update trailing performance and calculate a documented drift statistic.
5. If a trigger threshold is met and sufficient observations exist, create `AdaptationProposal` with baseline version, proposed weights/rules, evidence window, rationale, and timestamp.
6. Apply **hard, deterministic validation**: permissible weight bounds, no unsupported data, minimum sample size, no test leakage, and comparison against unchanged baseline on a separate **past-only validation segment** available at `t`.
7. Submit a concise public-safe proposal/trace to Reppo; save its `evalId`; poll asynchronously. Status remains `PENDING` until real settlement. Fallback: keep baseline active if unavailable.
8. Activate a new immutable config version **only when all configured gates pass** (including an acceptable Reppo verdict in the full sponsored flow). Otherwise reject and keep the previous version.
9. Continue replay. Measure subsequent *unseen* outcomes after activation. Never retroactively relabel the earlier decisions as if the new weights had been active.

**Critical nuance:** If an LLM proposes changes at time `t`, its inputs, validation windows, and Reppo payload must not include post-`t` market outcomes. Reppo results may arrive after `t`; for a fast replay, pause at the pending proposal, or separate the deterministic real-time adaptation from slower externally reviewed proposals. **Do not backdate a completed Reppo verdict.**

### MVP simplification for a reliable hackathon build

- Use **deterministic, online weight adjustments** as the fast adaptive layer. E.g. exponential weights driven by matured, cost-adjusted shadow outcomes (with bounds and smoothing). This can adapt during fast replay without API waits.
- Use **SERV + Reppo** for a slower *reviewed proposal* layer; store completed real evaluations and display them as pre-existing records with their actual timestamps.
- Explicitly label these as two different mechanisms. Avoid claiming that every routine weight change has been reviewed by Reppo.

### Performance measurement

Compare against at least three controls: **fixed-weight 50/50**, **momentum-only**, and **no-trade/cash**. Report net equity including costs, max drawdown, number of trades, exposure, and risk-adjusted metrics if sample sizes permit. Win rate alone is misleading. Use identical datasets, starting balance, and execution assumptions.

Replay safeguards: UTC timestamps, stable sorting, no future candle peek, signals on closed bars and fills no earlier than the next bar under disclosed assumptions, bounded exposure, configurable transaction costs/slippage, seeded deterministic results. These simulations cannot guarantee real execution conditions.

## 7. Concrete data contracts

Use typed request/response schemas. Suggested records (field names can evolve with migrations):

```ts
type Signal = {
  strategyId: "momentum" | "reversal";
  observedAt: string; // ISO UTC, closed-candle boundary
  action: "BUY" | "WAIT" | "EXIT";
  strength: number; // 0..1
  evidence: string[]; // provenance/indicator refs, never invented
};

type SupervisorDecision = {
  runId: string; observedAt: string; configVersion: string;
  action: "BUY" | "WAIT" | "EXIT" | "AVOID";
  weights: { momentum: number; reversal: number };
  guardian: "ALLOW" | "CAUTION" | "BLOCK";
  evidenceIds: string[]; reason: string;
};

type AdaptationEvent = {
  id: string; runId: string; detectedAt: string;
  status: "DETECTED" | "PROPOSED" | "PENDING_REVIEW" |
          "VALIDATING" | "ACCEPTED" | "REJECTED" | "FAILED";
  fromVersion: string; proposedVersion?: string;
  oldWeights: [number, number]; proposedWeights?: [number, number];
  evidenceIds: string[]; evaluationId?: string;
  rejectionReason?: string; activatedAt?: string;
};
```

Persistence tables: `datasets`, `candles`, `replay_runs`, `strategy_signals`, `supervisor_decisions`, `paper_orders`, `equity_snapshots`, `adaptation_events`, `config_versions`, `reppo_evaluations`. Store input dataset hash, algorithm version, and run parameters for reproduction.

## 8. Stack and project boundaries

**Frontend:** Next.js (App Router), React, TypeScript, Tailwind, Lightweight Charts, minimal animation library if necessary.  
**Backend:** Python, FastAPI, pandas/numpy for deterministic calculations, SQLite for local/demo persistence.  
**AI:** OpenServ SERV Reasoning (structured proposals) + Reppo Evaluation API (asynchronous critique).  
**Market data:** Start with one verified historical Solana pool data source (CoinGecko/GeckoTerminal OHLCV or another licensed provider). Cache and version the dataset; verify coverage and terms before committing.  
**Deployment:** Vercel for web + a Python-capable backend host (or a unified deployment if reliable). Never expose API keys client-side.

**Suggested endpoints:** `GET /api/datasets`, `POST /api/replays`, `POST /api/replays/{id}/advance`, `POST /api/replays/{id}/reset`, `GET /api/replays/{id}`, `GET /api/replays/{id}/events`, `POST /api/adaptations/{id}/evaluate`, `GET /api/evaluations/{evalId}`, `GET /api/health`.

Web UI must be usable with seed data and a local backend if external APIs are temporarily down. External evaluation results should display their actual provenance and status.

## 9. MVP acceptance criteria (definition of done)

- [ ] Landing page clearly explains the problem and offers a working launch CTA.
- [ ] Guided onboarding works with skip, recommended scenario, and no login.
- [ ] `/terminal` loads an authentic, time-bounded historical dataset with source/UTC metadata.
- [ ] Play/pause/step/reset works and produces repeatable results for the same seed/config.
- [ ] Two transparent strategies, one guardian, and one supervisor generate actual decisions.
- [ ] At least one real, traceable adaptation event can occur; rejected changes are preserved.
- [ ] Fixed vs adaptive comparison uses exactly the same available information and cost model.
- [ ] SERV produces at least one real structured proposal/critique tied to a saved event.
- [ ] Reppo integration submits and retrieves at least one **real** asynchronous evaluation; pending states are honest.
- [ ] A judge can inspect what changed, why, when, and whether later performance improved.
- [ ] No real trading, wallets, fake P&L, look-ahead leakage, or unverified profitability claims.
- [ ] Repository, reproducible instructions, demo, short write-up, and public X post prepared before official deadline.

## 10. Scope guardrails and implementation order

**P0 (must):** verified data; deterministic replay; strategies; supervisor; fixed comparison; actual adaptation log; real SERV call; real Reppo call; landing + short onboarding + terminal.  
**P1 (if time):** keyboard shortcuts, comparison exports, beautiful metric tooltips, polished transitions, direct-share scenarios.  
**P2 (post-hackathon):** Telegram alerts, continuous live monitoring, token discovery, more strategies, exchange integrations, wallet data, paid plans, account systems.

**Recommended build order:** (1) data quality and temporal correctness; (2) engine + baselines + tests; (3) adaptation + evidence storage; (4) SERV and Reppo integrations; (5) terminal; (6) landing/onboarding polish; (7) submission packaging. **Design all three experiences from day one, but prioritize working behavior over visual effects.**

## 11. Risks and contingency planning

| Risk | Mitigation |
|---|---|
| Historical data too sparse or expensive | Verify pool coverage immediately. Choose one reproducible licensed sample; label synthetic examples honestly. |
| Adaptive system underperforms | Show failures. A validated rejection and correct abstention still demonstrate supervision. Do not forge wins. |
| Reppo settlement delay/limit | Queue one evaluation, store real result, show correct pending state; do not pretend reviews are instant. |
| Model hallucinates market facts | Pass structured, versioned inputs and schema-validate outputs. Calculations remain deterministic. |
| Unrealistic paper trading | Next-bar fills, explicit friction assumptions, position caps, caveats about actual liquidity. |
| UI takes time from working engine | Use a simple functional terminal first, then enhance visuals without altering semantics. |
| Server/API inaccessible during demo | Cached dataset, idempotent reset, verified completed evaluation record, health indicator. |

## 12. Public references and status

Information verified as of 2026-11-09; confirm any integration changes before coding:

- Hackathon rules and deadline: https://www.openserv.ai/hackathon-2
- OpenServ documentation: https://docs.openserv.ai/
- Reppo evaluation concepts: https://docs.reppo.ai/concepts/evaluation-api
- Reppo API overview: https://docs.reppo.ai/api/eval/overview
- Reppo API submit/read: https://docs.reppo.ai/api/eval/evaluations
- CoinGecko onchain market-data docs: https://docs.coingecko.com/

**Product principle to protect:** A beautiful landing page earns curiosity. A guided onboarding earns understanding. A **real, inspectable adaptation cycle** earns credibility.
