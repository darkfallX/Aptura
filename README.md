# Aptura

**Before your trading bot rewrites its own rules, Aptura checks the change on past data, gets a second opinion, and blocks it if it doesn't hold up.**

OpenServ Hackathon 02 · Reppo track · Paper trading only: no wallet, no real money.

**Live app: [aptura-khaki.vercel.app](https://aptura-khaki.vercel.app)** · **[Demo video](https://x.com/Darkfall_x/status/2122039250598126073)**

[Run it locally](#run-it) · [Judges, start here](#judges-start-here) · [Proof](#proof-real-serv-and-reppo-calls) · [Results, losses included](#measured-results-losses-included)

---

## Kemi's 3 a.m. problem

Kemi (a made-up user) runs a small bot that trades BONK on Solana. It mixes two simple strategies: follow the trend (momentum) and bet on bounce-backs (reversal).

At 3 a.m. the trend breaks. The bot sees a few losing signals and decides to rewrite itself: **"Go 95% reversal, right now."** Nobody is awake to check whether that's a real change in the market or just noise.

Bots that tune themselves have no one asking *"prove it"* first. Aptura is that check.

**Every change has to get past three gates:**

| | Gate | What it does | Who decides |
|---|---|---|---|
| 1 | **OpenServ SERV Reasoning** | Reads only what was known at that moment and proposes a bounded change with its reasons | A language model, constrained to a strict JSON schema |
| 2 | **Math gate** | Re-runs the last 24 hours with fees and slippage. The change must actually beat the current mix, stay within limits and respect a cooldown | Python. No model can override it |
| 3 | **Reppo review** | Independent evaluators score the reasoning: ship, review or block | Reppo Eval Router |

The math gate always has the final say. A perfect review score can't push through a change that the numbers don't support.

**Rejections become feedback.** Set `maxRevisions` (up to 2) and a rejected change doesn't just stop there. The gate's reason and Reppo's critique are sent back to SERV, which proposes a revised change (or decides no change is justified), and the gate tests it again. Every round is returned with its weights, past-24-hour result, Reppo score and verdict, plus the measured gain from the first round to the last. Revisions are only sent to Reppo once they pass the math gate, so no credits go to candidates that can't ship.

---

## Judges, start here

No sign-in, no wallet.

| Path | Time | Where | What you'll see |
|---|---|---|---|
| **A. Watch a change get blocked** | 2 min | [`/terminal?scenario=momentum-breakdown&autorun=1`](https://aptura-khaki.vercel.app/terminal?scenario=momentum-breakdown&autorun=1) | The replay runs, drift is detected, and the three gates decide |
| **A0. Start here** | 1 min | [`/requests`](https://aptura-khaki.vercel.app/requests) | Every change a bot tried to make, as a request with its checks. Open one to read the full review |
| **B. Check the receipts** | 1 min | [`/proof`](https://aptura-khaki.vercel.app/proof) | Real SERV response IDs and a settled Reppo evaluation. Your browser re-hashes the candles and rechecks the limits |
| **C. Be the bot** | 2 min | [`/judge`](https://aptura-khaki.vercel.app/judge) → Be the bot, or the `curl` below | Send your own change. Watch it get rejected, revised from the feedback and re-tested |
| **D. See where we lose** | 1 min | [`/evaluation`](https://aptura-khaki.vercel.app/evaluation) | Every dataset, including the ones where cash beat us |

```bash
curl -X POST https://aptura-khaki.vercel.app/api/v1/supervise \
  -H "Content-Type: application/json" \
  -d '{"agentName":"kemi-bonk-bot","datasetId":"momentum-breakdown",
       "currentWeights":{"momentum":0.6,"reversal":0.4},
       "proposedWeights":{"momentum":0.05,"reversal":0.95},
       "runReppoReview":false, "maxRevisions":2}'
# -> "rounds": [ {verdict: BLOCK, 5/95}, {verdict: ..., SERV revision} ], "improvement": {...}
```

Agents can read [`/llms.txt`](apps/web/public/llms.txt) and `GET /api/agent/manifest`.

---

## The interface

Every change a bot wants to make to itself is shown as a **change request**, the way a code change gets a pull request and checks.

| Page | What it shows |
|---|---|
| `/` | A live request whose three checks resolve one by one into a verdict, the scoreboard, and the review flow |
| [`/requests`](https://aptura-khaki.vercel.app/requests) | The inbox: 4 live requests (real SERV and Reppo calls) and 34 replay proposals, filterable by blocked or passed. Each row shows the bot, a before/after weight bar, one chip per check and the verdict |
| `/requests/<id>` | One request. **Change**: today's mix, what was asked, SERV's suggestion and the final mix, with the 15% and 85% limits drawn as dashed lines. **Timeline**: the bot opens it → SERV reasons → the math gate replays the past 24 hours (result, +0.06% threshold, limit, step) → Reppo scores it → feedback goes back to SERV → revision → verdict. **Side panel**: the three checks (re-runnable) and every SERV and Reppo ID |
| `/judge` (Try it) | Open a request yourself: drag the slider, watch the limit pills, send it, and see the checks and revision rounds |
| `/evaluation` (Replays) | One sparkline card per market, every track (adaptive, fixed 50/50, momentum only, cash), the 34 proposals on a timeline, and where it failed |
| `/proof` (Verify) | 7 checks your browser runs itself: candle hash, history before the decision, no future data, limits, threshold, Reppo settlement |
| `/developers` (API) | Endpoints, a request and the recorded response, limits and proposed pricing. Agents can read `/llms.txt` and `/api/agent/manifest` |
| `/terminal` | The full replay workstation and the live market supervisor |

Check chips: **SERV** green means a live, schema-valid proposal. **Math** green means the change beat today's mix by at least +0.06% on the past 24 hours inside 15–85%, with a step of at most 25 points. **Reppo** green means route ship, amber means route review, grey means no review was requested. The math gate always has the final say.

Light, dark and system themes are in the top bar.

---

## Proof: real SERV and Reppo calls

Recorded on **14 Nov 2026** with `scripts/run_live_proof.py`. Four live calls, with every SERV response ID and Reppo eval ID listed. Full receipts are in [`data/proof/live-proof.json`](data/proof/live-proof.json).

**Receipt 1: the bot asks for 95% reversal**

| | |
|---|---|
| SERV | `SERV_GENERATED`, model `gpt-5.6-sol`, response `chatcmpl-EkChHtNc5bZQ3s9HdXiEZgjYB2K1v`, 9.4 s |
| Math gate | 95% breaks the 15–85% limit and the 25-point step limit. Past-24-hour test: −1.797% vs. current mix |
| Verdict | **BLOCK** |

**Receipt 2: SERV proposes a bounded change and Reppo reviews it**

| | |
|---|---|
| SERV | `SERV_GENERATED`, response `chatcmpl-EkChQRj5M4Jm7YM31ib3XhIzTpQ3o`, 8.4 s. Regime: `UNCERTAIN`. Suggests 70/30 |
| Reppo | Eval `cmwgqi5ji000107lauz6r6llv` · **100/100 · accept · route `ship`** · 440 credits · settled in 25 s |
| Math gate | Past-24-hour test: +0.000%. The threshold is +0.06% |
| Verdict | **BLOCK** |

**Receipt 3: rejected, then revised from the feedback** (`maxRevisions: 2`)

| Round | Weights | Past 24h | Reppo | Verdict |
|---|---|---|---|---|
| 0, the bot asks | 5 / 95 | −1.797% | `cmwgu3dz8000308jw2z0y5e11` · 99 · route `review` | BLOCK |
| 1, SERV revises using the gate reason + Reppo critique | 60 / 40 (no change) | 0.000% | not sent (didn't pass the gate) | BLOCK, "keep current weights" |

SERV responses: `chatcmpl-EkEGhthBektJ5D9jDTO4Y6Y9wTEb6`, `chatcmpl-EkEIrZ9YCRZmtJdk4kgokepVRwswp`. With the feedback in hand, SERV stopped asking for a change. That moved the outcome from −1.80% to 0.00% on the same past window.

**Receipt 4: a change that passes, and a revision that doesn't** (`maxRevisions: 1`, candle 70)

| Round | Weights | Past 24h | Reppo | Verdict |
|---|---|---|---|---|
| 0, the bot asks | 45 / 55 | **+0.771%** | `cmwgucnkc000107lbsueos9r1` · 81 · low confidence, route `review` | REVIEW |
| 1, SERV revises | 65 / 35 | −0.090% | not sent | BLOCK |
| **Returned** | **45 / 55** | | | **REVIEW**: round 0 kept |

Receipt 2 is the most important thing we learned (see below).

**Nothing has shipped on a live call yet.** In all 4 live calls, either the gate or Reppo held the change back. In the offline replays the gate accepted 8 of 34 changes, so it can say yes. Live, a change has to clear both.

---

## Measured results, losses included

Full replays of all 4 datasets with `scripts/run_evaluation.py`, no network, fully reproducible. Fills happen at the next candle's open with 20 bps fee + 15 bps slippage per side. Raw numbers are in [`data/evaluation/results.json`](data/evaluation/results.json).

| Dataset | Adaptive | Fixed 50/50 | Momentum only | Cash | Changes proposed → accepted |
|---|---|---|---|---|---|
| BONK/SOL, momentum breaks | **+1.66%** | −5.52% | −0.76% | 0% | 9 → 3 |
| POPCAT/SOL, choppy | −4.39% | −5.23% | −6.14% | 0% | 10 → 2 |
| SOL/USDC, steady trend | −3.38% | −4.39% | −3.96% | 0% | 11 → 2 |
| SYNTHETIC whipsaw | −1.00% | 0% | +4.28% | 0% | 4 → 1 |

What this says, plainly:

- **Adaptive beat fixed 50/50 on all 3 real datasets**, by +7.2, +0.8 and +1.0 points.
- **It made money on only 1 of 3.** Holding cash beat it on 3 of the 4 datasets.
- **The gate rejected 26 of 34 proposed changes (76%).** Most proposed changes didn't show a measurable benefit on past data, so they never shipped.
- **It failed the synthetic noise test.** One change slipped through on pure noise and cost 1%. That test exists to catch exactly this, so we report it.
- 3 real datasets of 199 hourly candles is far too few to claim an edge. Aptura's job is to block bad changes, not to promise profit.

---

## What we found building it

**Our first feedback loop made things worse, and a live call caught it.** On the first live run of Receipt 4, round 0 passed the gate (+0.771%). Reppo routed it to review, SERV revised to 70/30, that failed (−0.090%), and the loop returned the failed revision. A revision should never throw away a better round. Aptura now keeps the best round (SHIP, then a gate-passing REVIEW, then BLOCK), there's a regression test for it, and the before-fix receipt is kept in [`data/proof/ship-before-fix.json`](data/proof/ship-before-fix.json) (Reppo eval `cmwgu6f8o000408jwns9arakf`).

**SERV and the replay keep disagreeing about direction.** In every live call SERV read the matured signal outcomes as favouring momentum. At candle 70 the 24-hour portfolio replay said the opposite: tilting toward reversal earned +0.771%, while SERV's momentum-leaning revisions lost. They measure different things (per-signal outcomes vs. a fee-paying portfolio), which is exactly why one of them has to have the final say.

**The reviewer and the numbers disagreed, and the numbers were right to win.** In Receipt 2, Reppo gave SERV's reasoning a perfect 100 and said ship. The same change showed +0.000% on the past 24 hours: no measurable benefit. The reasoning was well written and safe, but it wasn't backed by evidence. If review scores alone could promote changes, this one would have shipped. That's why Reppo's verdict can block a change but can never approve one on its own.

**The bot's panic was backwards.** The bot wanted 95% reversal. SERV read the same 7 matured outcomes and concluded that reversal was the strategy that was consistently losing. It suggested a small shift toward momentum (70/30), flagged the regime as `UNCERTAIN`, and noted that 7 samples is very few. Even that careful suggestion didn't clear the math gate. Two layers disagreeing with a panicked bot is the point.

---

## Who pays

Builders of self-tuning trading agents. A bad self-update can cost far more than a check.

| Tier | What you get | Proposed price | Our cost |
|---|---|---|---|
| Check | Math gate only, rate limited | Free | $0 |
| Reason | SERV proposal + up to 2 feedback revisions + math gate | $0.05 per change | SERV inference |
| Reviewed | Everything above + a Reppo review of each change that passes the gate | $0.49 per change | ~$0.22 (440 Reppo credits) |

These prices are proposed, not billed yet. They're also published in `GET /api/agent/manifest` so other agents can read them.

---

## Limits we state plainly

- **Paper trading only.** No wallet, no exchange keys, no order is ever sent anywhere. All profit and loss is simulated.
- **Reppo scores reasoning, not profit.** Its scores are never shown as trading performance.
- **Small sample.** 3 real markets × 199 hourly candles, plus 1 synthetic. Not enough to claim an edge.
- **The datasets are integrity-hashed, not source-signed.** Hashes prove the candles weren't changed after capture, not that the provider was right.
- **The live feed** polls GeckoTerminal's free API every 15 seconds, so data can lag.
- **Revisions re-use the same 24-hour window.** Each extra round is another test on the same data, which raises the chance of passing by luck. That's why revisions are capped at 2, the fallback revision just halves the step (it's never tuned on the window), and we report every round.
- **Single machine.** SQLite and file locks; not a hardened multi-user deployment.
- **Public deployments:** set `APTURA_PUBLIC=1` and `APTURA_ADMIN_KEY`. Reppo reviews then need the `x-aptura-admin-key` header, and `/api/v1/supervise` is limited to 6 calls per IP per minute (`APTURA_SUPERVISE_PER_MIN`). The IP comes from `x-forwarded-for`, so put the API behind a proxy you control.

---

## Run it

```bash
cp .env.example .env          # add SERV_API_KEY, SERV_MODEL, REPPO_API_KEY for live calls
docker compose up --build     # web :3000, API :8000
```

Without Docker:

```bash
pip install -r requirements.txt
PYTHONPATH=services/api python -m uvicorn app.main:app --port 8000
cd apps/web && npm install && npm run dev
```

On Windows you can also run `./Start-Aptura.ps1`. The `/`, `/proof`, `/evaluation` and `/judge` pages read static files in `apps/web/public/proof`, so they work even without the API.

---

## For developers

```text
apps/web/            Next.js 15 · landing, /requests, /requests/[id], /judge (try it), /proof (verify), /evaluation (replays), /onboarding, /terminal (light, dark, system themes)
services/api/app/    FastAPI · strategies, supervisor, replay, SERV + Reppo clients, SQLite
scripts/             run_evaluation.py, run_live_proof.py
data/                datasets, evaluation results, proof receipts
tests/               63 tests: replay, gates, providers (mocked), proof endpoints, revise loop, rate limit
```

**Gate rules** (`services/api/app/supervisor/engine.py`): each weight stays between 15% and 85% and weights sum to 1 · a step moves a weight by at most 25 points · 18-bar cooldown · the change must beat the current mix by at least +0.06% on the 24 bars before the decision · enough matured samples · cited evidence IDs must exist.

**Sponsor tech**

- *OpenServ SERV Reasoning* — `services/api/app/evaluation/clients.py`. Uses `/chat/completions` with a strict `json_schema` response format, a `json_object` fallback and one repair retry. Records `SERV_GENERATED` vs. `DETERMINISTIC_FALLBACK` provenance, latency and response ID.
- *Reppo Eval Router* — `POST /api/v1/agents/evals` (`taskType: action`), then polls `GET /api/v1/agents/evals/{id}`. Sends a sanitized prompt only: timestamps, weights, scores and evidence IDs, never keys. The job queue survives restarts.

**Tests**

```bash
PYTHONPATH=services/api python -m pytest -q -m "not live"     # hermetic
PYTHONPATH=services/api python -m pytest -s -m live           # real SERV + Reppo, spends credits
npm --prefix apps/web run typecheck && npm --prefix apps/web run build
```
