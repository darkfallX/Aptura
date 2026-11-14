# Aptura — Coding Agent Operating Instructions

> **Usage:** Place this document at the repository root for any code-generation assistant to read before editing.

## Mission

Build **Aptura**, a **web-based adaptive AI trading supervisor** for the **OpenServ Hackathon 02 / Reppo track**. It is an auditable, paper-trading research laboratory, **not** an autonomous real-money trading bot.

The experience has **three connected routes**:
- `/` — premium, story-led **marketing landing page** that explains *why* strategies need supervision.
- `/onboarding` — lightweight **guided setup** that introduces strategies and chooses a reproducible historical replay.
- `/terminal` — a **single cohesive supervision dashboard** with price chart, strategies, decisions, adaptation timeline, fixed-vs-adaptive performance, and real evaluation evidence.

Read `docs/product.md` for the product contract, and `docs/skill.md` for the recommended task workflow. If the documents disagree, defer to `docs/product.md` for functionality, this file for implementation safeguards, and ask for clarification only if a blocking contradiction remains.

## Non-negotiable engineering principles

1. **Prove behavior.** The demo must run actual deterministic replay logic. Never fabricate data, trades, AI evaluations, accuracy, or portfolio performance to make the UI look better.
2. **No look-ahead.** At replay instant `t`, strategies and agent prompts may only use information available at or before `t`. Trades use disclosed subsequent-bar execution assumptions; never trade at a future price while scoring the current decision.
3. **No live money.** Do not request wallets, exchange credentials, seed phrases, private keys, or build real trade execution in the MVP.
4. **AI is not the numerical engine.** Python computes indicators, simulated fills, metrics, drift signals, and validation tests. SERV Reasoning proposes/explains changes from bounded inputs. Reppo critiques output asynchronously. Reppo scores are **not** trading-performance measurements.
5. **Adaptation must be inspectable.** Persist evidence, proposed change, review, deterministic gate results, final action, and immutable configuration versions. Reject weak changes explicitly.
6. **Hard constraints beat model output.** No LLM or external verdict bypasses risk limits, schema validation, source timestamps, or test requirements.
7. **Demonstrate uncertainty.** Support `WAIT`, `AVOID`, and rejected proposals. An agent that always buys or always claims success fails product intent.
8. **Labels are honest.** Clearly mark `HISTORICAL REPLAY`, `PAPER TRADE`, `SIMULATED P&L`, `SYNTHETIC` (only when applicable), `PENDING REVIEW`, and data-source attribution.
9. **No secret leakage.** Keys only server-side; `.env.example` has blank placeholders; redact credentials and private user data before external evaluation. Reppo currently exposes submissions to reviewers.
10. **Small vertical slices.** Make one end-to-end path work before adding strategy count, real-time feeds, authentication, Telegram, or polish.

## Stack and repo layout

```text
aptura/
├── product.md                 # product contract
├── AGENTS.md                  # operating instructions
├── skill.md                   # project-specific operating playbook
├── apps/
│   └── web/                   # Next.js App Router + TypeScript + CSS
│       ├── app/page.tsx       # storytelling landing
│       ├── app/onboarding/page.tsx
│       ├── app/terminal/page.tsx
│       └── components/        # reusable visualizations + UI
├── services/
│   └── api/                   # Python FastAPI service
│       └── app/
│           ├── main.py
│           ├── domain/        # typed contracts
│           ├── data/          # data adapters, validation, provenance
│           ├── strategies/    # deterministic momentum / reversal
│           ├── supervisor/    # decisions, risk gating, weight updates
│           ├── replay/        # simulated clock, fills, accounting
│           ├── evaluation/    # SERV and Reppo adapters + state
│           └── storage/       # SQLite repositories
├── data/                      # approved datasets and metadata
├── tests/                     # replay/strategies/integration tests
├── .env.example
└── README.md
```
