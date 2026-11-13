"use client";

import Link from "next/link";
import { Brand } from "@/components/WorkspaceNav";
import { LivePreview } from "@/components/LiveWorkspace";

const THREE_GATE_STEPS = [
  {
    gate: "Gate 1 · OpenServ SERV Reasoning",
    title: "Diagnose regime drift causally",
    text: "Diagnoses why a strategy mix is slipping from strictly observed telemetry—never touches future bars.",
  },
  {
    gate: "Gate 2 · 24-Bar Math & Risk Gate",
    title: "Hard bounds beat model claims",
    text: "Deterministic Python simulator tests weight bounds [15–85%], cooldowns, and past-only replay delta before acceptance.",
  },
  {
    gate: "Gate 3 · Reppo Eval + Service API",
    title: "Independent critique & agent API",
    text: "Reppo evaluator panel scores reasoning asynchronously (ship / review / block), exposed via POST /api/v1/supervise.",
  },
];

const METHOD_TILES = [
  {
    title: "1. Detect drift without look-ahead",
    text: "Causal scouts track rolling shadow utility against completed candles at close and paper-fill on the next open.",
  },
  {
    title: "2. Propose & stress-test changes",
    text: "SERV Reasoning proposes bounded weight adjustments; the 24-bar deterministic gate rejects weak or overfitting changes explicitly.",
  },
  {
    title: "3. Audit via Reppo & OpenServ API",
    text: "Every accepted or declined adaptation creates an immutable config version and optional Reppo panel audit.",
  },
];

export default function LandingPage() {
  return (
    <div className="home-page">
      <header className="home-nav">
        <Brand />
        <nav>
          <a href="#three-gates">3-Gate architecture</a>
          <a href="#how-it-works">How it works</a>
          <Link href="/onboarding">Guided setup</Link>
        </nav>
        <Link href="/terminal?scenario=momentum-breakdown&autorun=1" className="btn btn-dark">
          Watch 3-Gate Demo →
        </Link>
      </header>

      <main>
        <section className="home-hero">
          <div className="hero-intro">
            <span className="kicker">OPENSERV HACKATHON 02 · REPPO TRACK · PAPER RESEARCH LAB</span>
            <h1>
              Trading bots adapt blindly.
              <br />
              <span>Aptura audits every shift.</span>
            </h1>
            <p>
              An adaptive AI trading supervisor that combines OpenServ SERV Reasoning, a zero-look-ahead deterministic math gate, and asynchronous Reppo evaluation.
            </p>
            <div className="home-actions">
              <Link
                href="/terminal?scenario=momentum-breakdown&autorun=1"
                className="btn btn-dark btn-large"
              >
                Watch 3-Gate Demo →
              </Link>
              <Link href="/terminal" className="btn btn-large">
                Live Market Feed
              </Link>
              <Link href="/onboarding" className="text-link">
                Guided Replay Setup →
              </Link>
            </div>
            <div className="small-note">
              Historical replay &amp; simulated paper P&amp;L only. No wallets or real-money execution.
            </div>
          </div>
          <LivePreview />
        </section>

        <section className="home-pipeline-strip" id="three-gates" aria-label="Three-gate supervision pipeline">
          {THREE_GATE_STEPS.map((step) => (
            <article className="home-pipeline-card" key={step.gate}>
              <span>{step.gate}</span>
              <strong>{step.title}</strong>
              <p>{step.text}</p>
            </article>
          ))}
        </section>

        <section className="home-method" id="how-it-works">
          <div className="method-heading">
            <h2>Start simple. Inspect every gate.</h2>
          </div>
          <div className="method-tiles">
            {METHOD_TILES.map((item) => (
              <article key={item.title}>
                <h3>{item.title}</h3>
                <p>{item.text}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="home-end">
          <h2>See the adaptation gates, not just the price chart.</h2>
          <Link href="/terminal?scenario=momentum-breakdown&autorun=1" className="btn btn-dark">
            Launch Replay + Supervisor API →
          </Link>
        </section>
      </main>

      <footer>
        <Brand />
        <span>
          OpenServ Hackathon 02 · Reppo Track. Historical replay &amp; live Coinbase market snapshots; paper execution only.
        </span>
        <Link href="/onboarding">Explore historical scenarios →</Link>
      </footer>
    </div>
  );
}
