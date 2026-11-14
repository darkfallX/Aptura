# Aptura — submission kit

## One line

Before your trading bot rewrites its own rules, Aptura checks the change on past data, gets a second opinion, and blocks it if it doesn't hold up.

## Write-up

**Problem.** Trading bots that tune themselves change their own settings with nobody checking. When a market changes character, a bot sees a few losses and rewrites itself, often in the wrong direction and often at 3 a.m.

**What Aptura does.** Every proposed change goes through three gates:
1. **OpenServ SERV Reasoning** reads only what was known at that moment and proposes a bounded change, in strict JSON.
2. **A math gate** re-runs the past 24 hours with fees and slippage. The change must beat the current mix, stay within 15–85% per strategy, move at most 25 points and respect an 18-bar cooldown. No model can override it.
3. **Reppo** evaluators independently score the reasoning: ship, review or block.

**Feedback becomes improvement.** When a change is rejected, the gate's reason and Reppo's critique go back to SERV, which revises (or decides no change is justified), and the gate re-tests it. Every round is measured and returned. A revision can never replace a better earlier round.

Other agents can call it directly with `POST /api/v1/supervise` and get back `SHIP`, `REVIEW` or `BLOCK`, plus every revision round.

**Who pays.** Builders of self-tuning agents. Proposed pricing: math-gate check free, $0.05 with SERV revisions, $0.49 with a Reppo review (cost basis about $0.22). Not billed yet.

**Proof.** On 14 Nov 2026 we made real calls. SERV responses `chatcmpl-EkChHtNc5bZQ3s9HdXiEZgjYB2K1v` and `chatcmpl-EkChQRj5M4Jm7YM31ib3XhIzTpQ3o`. Reppo eval `cmwgqi5ji000107lauz6r6llv` scored 100/100, route ship, 440 credits. The math gate still blocked that change: +0.000% on past data.

**Results, losses included.** Adaptive beat fixed 50/50 on all 3 real datasets but made money on only 1. Cash beat it on 3 of 4. The gate rejected 26 of 34 changes. It let one noise-driven change through on the synthetic test, which cost 1%.

**Feedback loop, live.** The bot asked for 95% reversal: −1.80%, blocked, Reppo 99 routed to review. Given that feedback, SERV revised to "keep current weights" (0.00%). On another call a 45/55 change passed the gate (+0.77%, Reppo 81, review). SERV's revision failed, and Aptura kept the passing round.

**What we found.** Reppo gave a perfect score to reasoning that the numbers didn't support, so review scores can block a change but never approve one alone. Our first feedback loop returned a worse revision instead of a passing round. A live call caught it, and we fixed it and added a test. Nothing has shipped on a live call yet: every change was held back by the gate or by Reppo.

**Built with.** Python 3.13, FastAPI, Pydantic, SQLite · Next.js 15, React 19, TypeScript · OpenServ SERV Reasoning · Reppo Eval Router · GeckoTerminal market data.

## X post

> Your trading bot just rewrote its own rules at 3am. Who checked?
>
> Aptura, for @openservai Hackathon 02 (Reppo track):
> 1. SERV Reasoning proposes a bounded change
> 2. A math gate replays the last 24h with fees. No model can override it
> 3. Reppo reviews the reasoning
>
> Rejected changes don't just die: the gate reason + Reppo critique go back to SERV, which revises, and the gate re-tests.
>
> Our favourite result: Reppo scored a change 100/100. The numbers said +0.000%. Blocked.
>
> Paper trading only. Receipts in the repo.

## Demo script (3:00)

**0:00 Hook** (landing). "This is Kemi's bot. At 3 a.m. it wants to go 95% reversal. Nobody's awake to check." The hero receipt prints and gets stamped BLOCKED.

**0:20 The three gates** (scroll). The receipt moves through three punches: SERV, the math gate, Reppo. "The math gate always has the final say."

**0:40 Watch it happen** (`/terminal?scenario=momentum-breakdown&autorun=1`). The replay runs, momentum breaks, drift is detected. Show the gates deciding, and a rejected change staying rejected.

**1:30 Receipts** (`/proof`). Show the real SERV IDs and the Reppo eval, then press *Check it yourself*: the browser re-hashes the candles and rechecks the limits. "Reppo said 100, ship. The numbers said nothing changed. Blocked."

**2:10 Where we lose** (`/evaluation`). "Cash beat us on 3 of 4. Aptura's job is to block bad changes, not to promise profit."

**2:35 Be the bot** (`/judge`). Drag to 5% momentum and send. The receipt prints round 0 BLOCK, then SERV's revision from the feedback. "Rejections become feedback. Any OpenServ agent can ask before it changes itself."

**2:50 Close.** "No wallet. No real money. Every decision has a receipt."
