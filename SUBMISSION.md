# Aptura — OpenServ Hackathon 02 (Reppo Track) Submission Assets

---

## 1. Hackathon Submission Write-Up (Ready to Paste)

### Project Name
**Aptura** — Adaptive AI Trading Strategy Supervisor

### Tagline
*Trading bots adapt blindly. Aptura audits every weight shift through OpenServ SERV Reasoning, a zero-look-ahead 24-bar math gate, and asynchronous Reppo evaluation.*

### Problem
Autonomous trading agents routinely drift out of sync when market regimes shift (e.g., from momentum breakouts to mean-reverting chop). Letting an LLM directly rewrite strategy parameters creates two failure modes: **silent overfitting** (chasing short-term noise or leaking look-ahead bias) and **unbounded risk** (jumping to extreme allocations without deterministic guardrails).

### Solution: 3-Gate Causal Supervision + Supervisor-as-a-Service
Aptura separates **reasoning**, **numerical verification**, and **external peer evaluation** into three strict gates:

1. **Gate 1 — OpenServ SERV Reasoning (`SERVAnalyst`):** Inspects strictly past-only telemetry (matured shadow outcomes, EWMA strategy divergence, current weight split) and produces a schema-validated adaptation hypothesis, regime diagnosis, and bounded candidate weights (`SERV_GENERATED` vs `DETERMINISTIC_FALLBACK` clearly badged).
2. **Gate 2 — Zero-Look-Ahead Deterministic Math & Risk Gate (`AdaptationEngine` + `validate_weights`):** Hard Python constraints always override model output—verifying `[15%, 85%]` bounds, cooldown spacing, and a counterfactual replay delta across the prior 24 closed candles using realistic next-open execution (`20 bps` fee + `15 bps` slippage per side). Weak or overfitting changes (tested against the adversarial `synthetic-noise-guard` scenario) are explicitly **rejected**.
3. **Gate 3 — Independent Reppo Eval Panel (`ReppoClient`):** Submits sanitized reasoning traces asynchronously to the Reppo Eval Router (`POST /api/v1/agents/evals`, `taskType: "action"`), polls `GET /api/v1/agents/evals/{id}`, and attaches verifiable rubric scores plus routing decisions (`ship` / `review` / `block`).

**Agent Ecosystem Utility:** Beyond its Next.js supervision terminal and live Coinbase market monitor, Aptura exposes **`GET /api/agent/manifest`** and **`POST /api/v1/supervise`** as a callable **Supervisor-as-a-Service** endpoint so any external OpenServ agent can submit candidate weight changes and receive a deterministic `SHIP | REVIEW | BLOCK` verdict before updating live strategy config.

### How We Use OpenServ & Reppo
- **OpenServ SERV Reasoning:** Structured JSON Schema (`strict: true`) hypothesis synthesis over causal telemetry at `https://inference-api.openserv.ai/v1` with explicit schema-repair retry and full prompt/response provenance.
- **Reppo Eval Router:** Live asynchronous agent evaluations at `https://eval.reppo.xyz/api/v1/agents/evals` auditing whether proposed parameter shifts are justified by past-only evidence and free of look-ahead bias.
- **Unit Economics:** Running Gate 2 locally costs `$0.00`; escalating high-stakes configuration changes to the Reppo panel costs `440` credits (`~$0.22`) per audited decision rather than paying per candle tick.

### Built With
- **Backend:** Python 3.13, FastAPI, Pydantic v2, NumPy, Pandas, SQLite, httpx, Pytest
- **Frontend:** Next.js 15 (App Router), React 19, TypeScript, Zod, Lucide icons
- **Integrations:** OpenServ SERV Reasoning API, Reppo Eval Router API, Coinbase public market data

---

## 2. Draft X (Twitter) Post

> Trading bots shouldn't rewrite their own risk weights unchecked.
>
> Introducing **Aptura** for @openservai Hackathon 02 (Reppo Track): an auditable 3-gate AI trading supervisor.
>
> 1. @openservai SERV Reasoning diagnoses strategy drift from causal telemetry
> 2. Deterministic Python math gate tests `[15-85%]` bounds & 24-bar past-only replay (`$0.00`)
> 3. Reppo Eval Router independently scores & routes (`ship / review / block`)
>
> Plus `POST /api/v1/supervise` so other OpenServ agents can call Aptura as a live risk governor before shipping config changes.
>
> Paper trading research only. Zero wallets. Zero look-ahead.
> #OpenServ #Reppo #AIAgents

---

## 3. Demo Video Script (~2 minutes 30 seconds)

**[0:00 – 0:25] Hook & Problem (Landing Page `/`):**
- Start on `/` showing the Sage/Cream hero, live market preview, and the **3-Gate Architecture** strip.
- Narration: *"Most AI trading demos let an LLM look at a chart and spit out trades—or silently tweak parameters without any proof it didn't overfit. Meet Aptura: an adaptive AI trading strategy supervisor built for OpenServ Hackathon 02 on the Reppo track."*

**[0:25 – 0:55] Causal Replay & Drift Detection (`/terminal?scenario=momentum-breakdown&autorun=1`):**
- Click **Watch 3-Gate Demo →**. Show BONK/SOL advancing past the first drift event automatically, pausing cleanly right on an adaptation check.
- Point out the four comparison equity tracks (**Adaptive**, **Fixed 50/50**, **Momentum**, **Cash**), deterministic scouts, and next-candle-open paper execution.

**[0:55 – 1:35] Live 3-Gate Audit Pipeline (SERV Reasoning -> Math Gate -> Reppo):**
- Scroll to the **Three-Gate Adaptation Check** panel.
- Click **Run Live SERV + Reppo Audit**.
- Explain each card as it updates live:
  - **Gate 1 (SERV Reasoning):** Generates a structured diagnosis and candidate mix with `SERV GENERATED` badge, model name, and measured latency.
  - **Gate 2 (Causal Math Gate):** Verifies `[15–85%]` hard bounds, cooldown spacing, zero look-ahead, and 24-bar historical validation delta. Mention how `synthetic-noise-guard` rejects weak changes cleanly.
  - **Gate 3 (Reppo Eval Panel):** Shows real Reppo evaluation ID (`QUEUED` -> auto-polling -> `COMPLETED`), rubric scores, credits charged, and `ship / review / block` verdict—clearly labeled as reasoning review, never portfolio P&L.

**[1:35 – 2:15] Supervisor-as-a-Service (`POST /api/v1/supervise` Workbench):**
- Scroll to **Supervisor-as-a-Service**.
- First run **Test rogue agent (95% reversal -> BLOCK)** and click **Call /api/v1/supervise**. Show the immediate red **`VERDICT: BLOCK`** from Gate 2 refusing to let an unbounded weight change ship.
- Switch to **SERV Reasoning proposes bounded weights** and run again to show SERV synthesizing a bounded proposal and passing Gate 2 (`VERDICT: SHIP`).

**[2:15 – 2:30] Live Market Feed & Closing Disclaimer (`/terminal`):**
- Switch to the live Coinbase feed mode briefly to show live tick ingestion with persistent SQLite supervision state, `GET /api/agent/manifest`, and restate: *"Zero wallets, zero look-ahead, 100% auditable adaptation."*
