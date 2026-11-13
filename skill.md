---
name: aptura-builder
description: Build and evaluate Aptura's adaptive trading supervisor, historical replay, SERV Reasoning and Reppo integrations, and landing/onboarding/terminal experience. Use for implementation, debugging, validation, and demo preparation.
---

# Skill — Aptura Builder

> This is a **project-local coding-agent skill**, not a claimed installed platform skill. The downloaded filename is `skill.md`; if your agent framework supports discoverable skills, place a copy at its expected path (commonly a folder containing `SKILL.md`) and retain this frontmatter. Keep `product.md` and `agents.md` beside the project for context.

## Outcome

Produce a functioning, inspectable **Adaptive AI Trading Supervisor** for historical Solana meme-token replay. Every polished visual must correspond to a real observable system state. The product flow is **Landing → Guided Onboarding → Single Terminal**.

## Read before working

1. `product.md` — user experience, scope, API contracts, acceptance criteria.
2. `agents.md` / `AGENTS.md` — repo rules, temporal correctness, security, test requirements.
3. Relevant source files and test fixtures. Do not guess whether a component exists.
4. Current provider documentation before implementing third-party calls.

## Which workflow to execute?

### Workflow A — Data + reproducible replay

**Use when:** adding datasets, data ingestion, clock logic, indicators, backtesting, equity calculation.

1. Choose an actual Solana pool with historical candles available under acceptable use terms.
2. Record source URL, pool address, chain, quote asset, timezone/UTC range, timeframe, fetch timestamp, and dataset hash in metadata.
3. Validate open/high/low/close, volumes, monotonic timestamps, gaps, duplicates, missing values, and candle closure. Reject bad data or explicitly mark missing data.
4. Add a simulated clock that reveals one completed candle at a time. Warm-up before trading signals are eligible.
5. Calculate signals using only the visible window. Place paper orders on next eligible bar with disclosed cost/slippage assumptions.
6. Add **fixed-weight**, **momentum-only**, and **cash** baseline runs. Compare with identical settings.
7. Test: deterministic replay, gap handling, next-bar fill, no look-ahead, idempotent reset.

**Done when:** The same dataset/configuration yields the same trace, fills, and metrics on repeated runs, with no AI dependency.

### Workflow B — Adaptive supervision

**Use when:** implementing performance monitoring, drift detection, strategy weighting, proposals, or validation.

1. Implement two narrow strategies: Momentum Scout and Reversal Scout. Make Risk Guardian a guardrail rather than a fake predictive model.
2. Persist each strategy's shadow signal even when not followed; calculate its evaluation outcome **only after the chosen horizon ends**.
3. Define a documented, causal trailing metric (e.g. EWMA of matured net signal return, with minimum sample size and smoothing).
4. Implement bounded adaptation (minimum/maximum weight, rate limit, cooldown); normalize weights and log every change.
5. Trigger a separate `AdaptationProposal` for more significant drift. Include `evidenceIds`, old/proposed weights, proposal timestamp, sample size, and active config version.
6. Validate proposed change against a **past-only** segment that was available when proposed; keep the future chronological holdout untouched.
7. Activate only after gates pass. Create a new immutable version and log rejection reasons otherwise.
8. Test an adversarial scenario where recent noise would cause harmful overreaction; assert the cooldown / acceptance gate stops the change.

**Done when:** A reviewer can identify the signal that deteriorated, the precise configuration change proposed, and whether later outcomes vindicated it.

### Workflow C — SERV Reasoning and Reppo

**Use when:** integrating AI decision review, improving narratives, storing eval states.

1. Derive a **structured, bounded** SERV prompt from numerical telemetry already computed in Python. Require machine-validated output (e.g. hypothesis, evidence IDs, suggested bounded weights, assumptions, uncertainties). Use the current official SERV endpoint/model configuration; do not hardcode undocumented values.
2. Check every evidence ID exists and refers to information at or before proposal time. Discard out-of-range suggestions and mark them invalid.
3. Construct a Reppo `plan` or `trace` submission with concise sanitized summary, concrete criteria, and public-safe context. Avoid secrets, private accounts, or unreleased proprietary data.
4. Submit to `POST /api/v1/agents/eval-requests/submit` on `https://eval.reppo.xyz` and persist the returned `evalId`. Follow current API documentation for the exact request fields.
5. Poll `GET /api/v1/agents/eval-requests/{evalId}` asynchronously. The API currently allows a **minimum 10-minute settlement window** and **one pending evaluation per account**; do not fake immediate results.
6. Map actual `PENDING`, `SETTLED`, `FAILED` to UI states. Reppo's verdict critiques the **quality of the submitted reasoning**, not the accuracy of future trades.
7. Require separate deterministic validation before promotion. Explicitly show when Reppo approved a plan but backtesting rejected it—or vice versa.
8. Save the external evaluation ID, request hash, timestamps, real scores, critique, and final local gate decision. No hardcoded "approved" results.

**Done when:** A real, reproducible adaptation event includes an inspectable SERV proposal, a persisted Reppo record, and an independent market-validation decision.

### Workflow D — Story-led product UI

**Use when:** building or polishing site pages, animations, terminal cards, marketing narrative.

1. Start with the information architecture: `/`, `/onboarding`, `/terminal`.
2. Build the landing as a **narrative**, not a second dashboard. Hero → why strategies fail → Observe/Evaluate/Adapt → proof of auditability → CTA.
3. Build onboarding as a short three-step wizard: `Meet agents` → `Pick verified replay` → `Set paper-trading parameters`. Support Skip and no-login guest mode.
4. Build the terminal as one powerful workspace. Every number/marker must map to an API record; attach visual provenance badges.
5. Animate state **transitions**, not fictional analysis: route changes, moving replay cursor, actual strategy weight changes, event focus, pending → settled review.
6. Prefer refined restraint: graphite surface, white type, quiet dividers, one restrained accent, expressive data typography. Good visual hierarchy beats dozens of glowing crypto cards.
7. Implement responsive stacks, accessible labels, contrast, chart text alternatives, keyboard focus, skeleton/empty/failure states, `prefers-reduced-motion`.
8. Test a cold first-time visitor: they should explain the product after the landing and reach replay in a few clicks.

**Done when:** Landing tells the story, onboarding gives necessary context, and the terminal makes the adaptive loop immediately intelligible. A direct judge demo route remains available.

### Workflow E — Demonstration + audit

**Use when:** creating a demo scenario, recording a submission, adding performance metrics, or declaring readiness.

1. Select and verify a reproducible historical period; state that it is historical. Do not cherry-pick without disclosure: show why this scenario was chosen and test at least one different regime.
2. Prepare a brief live path: hero → launch guided demo → play replay → inspect trigger → see proposal/evaluation → compare to frozen baseline.
3. Include **one accepted** and, if the data actually supports it, **one rejected** proposal. Do not manufacture events; use a separately labeled synthetic tutorial only when needed for UI teaching.
4. Show trade count, net simulated performance after fees, exposure, drawdown, and adaptation history—not only a flattering percentage.
5. Make a second run against an unseen chronological section. Report failures as well as successes.
6. Verify both SERV and Reppo were called for real. If Reppo is pending, show a *previously completed real* evaluation with its timestamp and launch a new request visibly.
7. Confirm all public URLs, README setup steps, and code are usable; never expose keys in screenshots, logs, client bundles, or commits.

**Done when:** Judges can independently distinguish live UI behavior, real historical input data, numerical outcomes, external AI review, and illustrative narrative.

## Definition of done by milestone

| Milestone | Minimal verified evidence |
|---|---|
| Data ready | Source/provenance, validated candles, replayable fixture |
| Engine ready | Strategy signals, paper broker, fixed baseline, tests |
| Adaptation ready | Logged trigger, proposed change, accepted/rejected gate, version |
| SERV ready | Real schema-valid response tied to evidence IDs |
| Reppo ready | Real eval submission ID and eventual status/critique |
| Experience ready | Landing, onboarding, terminal reachable and coherent |
| Demo ready | No credentials required to experience replay; metric and source honesty |

## Stop-and-check triggers

Stop introducing new features when any of the following happens:
- Replays see future data, or fill orders at unavailable prices.
- The same run cannot be reproduced.
- The UI presents synthetic or pre-rendered metrics as actual performance.
- A model output directly controls risk limits or overrides deterministic validation.
- An evaluation is described as settled before an actual Reppo result arrives.
- A claimed data field (liquidity, holder count, insider wallet) is not in the source dataset.
- Landing/page polish threatens the working adaptation demo under the event deadline.

## Useful current references

- OpenServ Hackathon: https://www.openserv.ai/hackathon-2
- SERV docs: https://docs.openserv.ai/
- Reppo evaluation concepts: https://docs.reppo.ai/concepts/evaluation-api
- Reppo submit/read: https://docs.reppo.ai/api/eval/evaluations
- Reppo API limitations: https://docs.reppo.ai/api/eval/overview
- Market-data provider docs: https://docs.coingecko.com/

## Response format for coding-agent task completion

Conclude implementation work with a succinct report:

```text
Implemented:
- ...
Files changed:
- ...
Tests run:
- ...
Verified behavior:
- ...
Known limitations:
- ...
Next smallest step:
- ...
```

**Core mantra:** Show **what the agent observed**, **what it proposed**, **what was independently evaluated**, **what actually changed**, and **what the evidence says happened next**.
