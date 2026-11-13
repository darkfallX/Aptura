"use client";

import React, { useEffect, useState } from "react";

interface RegimeState {
  id: "trend" | "deterioration" | "guardrail";
  label: string;
  configVersion: string;
  momWeight: number;
  revWeight: number;
  momStatus: string;
  momScore: string;
  revStatus: string;
  revScore: string;
  guardianStatus: "ALLOW" | "CAUTION" | "BLOCK";
  verdict: "BUY" | "WAIT" | "EXIT" | "AVOID";
  verdictNote: string;
  degradedNode: "none" | "momentum" | "market";
}

const REGIMES: RegimeState[] = [
  {
    id: "trend",
    label: "Stage 01 // Initial Trend Regime",
    configVersion: "v1.0.0",
    momWeight: 60,
    revWeight: 40,
    momStatus: "BUY · 0.74",
    momScore: "+1.18% EWMA",
    revStatus: "WAIT · 0.18",
    revScore: "-0.22% EWMA",
    guardianStatus: "ALLOW",
    verdict: "BUY",
    verdictNote: "Momentum Scout leads on verified breakout; next-bar paper fill queued.",
    degradedNode: "none",
  },
  {
    id: "deterioration",
    label: "Stage 02 // Momentum Deteriorates → Trust Redistributes",
    configVersion: "v1.1.0",
    momWeight: 35,
    revWeight: 65,
    momStatus: "BUY (Failing) · 0.41",
    momScore: "-1.15% EWMA",
    revStatus: "EXIT / REVERT · 0.78",
    revScore: "+0.59% EWMA",
    guardianStatus: "CAUTION",
    verdict: "WAIT",
    verdictNote:
      "Matured shadow signals expose momentum drift (-1.15% EWMA). Validated adaptation shifts weights 60/40 → 35/65.",
    degradedNode: "momentum",
  },
  {
    id: "guardrail",
    label: "Stage 03 // Volatility Spike → Risk Guardian Enforces Block",
    configVersion: "v1.1.0",
    momWeight: 35,
    revWeight: 65,
    momStatus: "EXIT · 0.62",
    momScore: "-1.34% EWMA",
    revStatus: "BUY · 0.55",
    revScore: "+0.41% EWMA",
    guardianStatus: "BLOCK",
    verdict: "AVOID",
    verdictNote:
      "12-bar realized volatility breaches conservative ceiling. Hard constraint overrides scout signals.",
    degradedNode: "market",
  },
];

export default function HeroSupervisorDiagram() {
  const [activeIdx, setActiveIdx] = useState<number>(1);
  const [paused, setPaused] = useState<boolean>(false);

  useEffect(() => {
    if (paused) return;
    const timer = setInterval(() => {
      setActiveIdx((prev) => (prev + 1) % REGIMES.length);
    }, 5200);
    return () => clearInterval(timer);
  }, [paused]);

  const state = REGIMES[activeIdx];

  return (
    <div
      className="arch-panel"
      style={{ padding: "1.35rem", background: "var(--bg-surface)" }}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      {/* Header bar */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "0.75rem",
          paddingBottom: "1rem",
          borderBottom: "1px solid var(--border-subtle)",
          marginBottom: "1.1rem",
        }}
      >
        <div>
          <div className="eyebrow" style={{ marginBottom: "0.2rem" }}>
            SIGNAL CONVERGENCE &amp; TRUST REDISTRIBUTION
          </div>
          <div className="font-mono" style={{ fontSize: "0.8rem", color: "var(--text-secondary)" }}>
            {state.label}
          </div>
        </div>
        <div style={{ display: "flex", gap: "0.35rem" }}>
          {REGIMES.map((r, i) => (
            <button
              key={r.id}
              type="button"
              id={`hero-regime-tab-${r.id}`}
              onClick={() => {
                setActiveIdx(i);
                setPaused(true);
              }}
              className="btn btn-sm font-mono"
              style={{
                padding: "0.3rem 0.65rem",
                fontSize: "0.72rem",
                background: i === activeIdx ? "var(--accent-mint-soft)" : "var(--bg-elevated)",
                borderColor: i === activeIdx ? "var(--accent-mint)" : "var(--border-subtle)",
                color: i === activeIdx ? "var(--accent-mint)" : "var(--text-secondary)",
              }}
            >
              0{i + 1}
            </button>
          ))}
        </div>
      </div>

      {/* SVG Network Diagram: 3 paths converging into Supervisor Node */}
      <div style={{ width: "100%", overflowX: "auto" }}>
        <svg
          viewBox="0 0 640 280"
          style={{ width: "100%", height: "auto", minWidth: "480px", display: "block" }}
          role="img"
          aria-label="Three signal paths from Momentum Scout, Reversal Scout, and Risk Guardian converging into the Aptura Supervisor node"
        >
          {/* Subtle coordinate lines */}
          <line x1="230" y1="15" x2="230" y2="265" stroke="rgba(255,255,255,0.05)" strokeDasharray="3 3" />
          <line x1="415" y1="15" x2="415" y2="265" stroke="rgba(255,255,255,0.05)" strokeDasharray="3 3" />

          {/* Path 1: Momentum Scout -> Supervisor */}
          <path
            d="M 210 52 C 295 52, 310 125, 395 125"
            fill="none"
            stroke={state.degradedNode === "momentum" ? "#f87171" : "#38bdf8"}
            strokeWidth={state.momWeight >= 50 ? "2.6" : "1.4"}
            strokeDasharray={state.degradedNode === "momentum" ? "5 4" : "none"}
          />

          {/* Path 2: Reversal Scout -> Supervisor */}
          <path
            d="M 210 140 C 295 140, 310 140, 395 140"
            fill="none"
            stroke="#2dd4bf"
            strokeWidth={state.revWeight >= 50 ? "2.8" : "1.6"}
          />

          {/* Path 3: Risk Guardian -> Supervisor */}
          <path
            d="M 210 228 C 295 228, 310 155, 395 155"
            fill="none"
            stroke={
              state.guardianStatus === "BLOCK"
                ? "#f87171"
                : state.guardianStatus === "CAUTION"
                ? "#f59e0b"
                : "rgba(255,255,255,0.35)"
            }
            strokeWidth={state.guardianStatus === "BLOCK" ? "2.5" : "1.5"}
          />

          {/* Node 1: Momentum Scout */}
          <g transform="translate(12, 18)">
            <rect
              width="198"
              height="68"
              fill="#141921"
              stroke={state.degradedNode === "momentum" ? "rgba(248,113,113,0.55)" : "rgba(56,189,248,0.4)"}
              strokeWidth="1"
            />
            <text x="12" y="21" fill="#f3f4f6" fontSize="11.5" fontWeight="600" fontFamily="Space Grotesk, sans-serif">
              MOMENTUM SCOUT
            </text>
            <text
              x="186"
              y="21"
              textAnchor="end"
              fill={state.degradedNode === "momentum" ? "#f87171" : "#38bdf8"}
              fontSize="11"
              fontWeight="600"
              fontFamily="JetBrains Mono, monospace"
            >
              {state.momWeight}%
            </text>
            <text x="12" y="41" fill="#9ca3af" fontSize="10" fontFamily="JetBrains Mono, monospace">
              Signal: {state.momStatus}
            </text>
            <text
              x="12"
              y="56"
              fill={state.degradedNode === "momentum" ? "#f87171" : "#64748b"}
              fontSize="9.5"
              fontFamily="JetBrains Mono, monospace"
            >
              Shadow: {state.momScore}
            </text>
          </g>

          {/* Node 2: Reversal Scout */}
          <g transform="translate(12, 106)">
            <rect
              width="198"
              height="68"
              fill="#141921"
              stroke={state.revWeight >= 50 ? "rgba(45,212,191,0.55)" : "rgba(255,255,255,0.14)"}
              strokeWidth="1"
            />
            <text x="12" y="21" fill="#f3f4f6" fontSize="11.5" fontWeight="600" fontFamily="Space Grotesk, sans-serif">
              REVERSAL SCOUT
            </text>
            <text
              x="186"
              y="21"
              textAnchor="end"
              fill="#2dd4bf"
              fontSize="11"
              fontWeight="600"
              fontFamily="JetBrains Mono, monospace"
            >
              {state.revWeight}%
            </text>
            <text x="12" y="41" fill="#9ca3af" fontSize="10" fontFamily="JetBrains Mono, monospace">
              Signal: {state.revStatus}
            </text>
            <text x="12" y="56" fill="#2dd4bf" fontSize="9.5" fontFamily="JetBrains Mono, monospace">
              Shadow: {state.revScore}
            </text>
          </g>

          {/* Node 3: Risk Guardian */}
          <g transform="translate(12, 194)">
            <rect
              width="198"
              height="68"
              fill="#141921"
              stroke={
                state.guardianStatus === "BLOCK"
                  ? "rgba(248,113,113,0.6)"
                  : state.guardianStatus === "CAUTION"
                  ? "rgba(245,158,11,0.5)"
                  : "rgba(255,255,255,0.14)"
              }
              strokeWidth="1"
            />
            <text x="12" y="21" fill="#f3f4f6" fontSize="11.5" fontWeight="600" fontFamily="Space Grotesk, sans-serif">
              RISK GUARDIAN
            </text>
            <text
              x="186"
              y="21"
              textAnchor="end"
              fill={
                state.guardianStatus === "BLOCK"
                  ? "#f87171"
                  : state.guardianStatus === "CAUTION"
                  ? "#f59e0b"
                  : "#2dd4bf"
              }
              fontSize="10.5"
              fontWeight="600"
              fontFamily="JetBrains Mono, monospace"
            >
              {state.guardianStatus}
            </text>
            <text x="12" y="41" fill="#9ca3af" fontSize="10" fontFamily="JetBrains Mono, monospace">
              OHLCV Completeness: PASS
            </text>
            <text x="12" y="56" fill="#64748b" fontSize="9.5" fontFamily="JetBrains Mono, monospace">
              Hard Volatility &amp; Cap Gate
            </text>
          </g>

          {/* Mid-path weight callout */}
          <g transform="translate(252, 76)">
            <rect width="122" height="32" fill="#0f1318" stroke="rgba(255,255,255,0.1)" />
            <text x="61" y="14" textAnchor="middle" fill="#64748b" fontSize="8.5" fontFamily="JetBrains Mono, monospace">
              ACTIVE TRUST SPLIT
            </text>
            <text x="61" y="26" textAnchor="middle" fill="#f3f4f6" fontSize="10.5" fontWeight="600" fontFamily="JetBrains Mono, monospace">
              {state.momWeight}% / {state.revWeight}%
            </text>
          </g>

          {/* Converged Supervisor Node */}
          <g transform="translate(395, 58)">
            <rect
              width="232"
              height="164"
              fill="#141921"
              stroke="rgba(255,255,255,0.22)"
              strokeWidth="1"
            />
            <text x="16" y="26" fill="#2dd4bf" fontSize="9.5" fontFamily="JetBrains Mono, monospace">
              APTURA SUPERVISOR // {state.configVersion}
            </text>
            <text x="16" y="52" fill="#f3f4f6" fontSize="16" fontWeight="700" fontFamily="Space Grotesk, sans-serif">
              VERDICT: {state.verdict}
            </text>
            <line x1="16" y1="64" x2="216" y2="64" stroke="rgba(255,255,255,0.08)" />
            <text x="16" y="84" fill="#9ca3af" fontSize="10" fontFamily="JetBrains Mono, monospace">
              Momentum Trust: {state.momWeight}%
            </text>
            <text x="16" y="102" fill="#9ca3af" fontSize="10" fontFamily="JetBrains Mono, monospace">
              Reversal Trust: {state.revWeight}%
            </text>
            <text x="16" y="120" fill="#9ca3af" fontSize="10" fontFamily="JetBrains Mono, monospace">
              Guardian Gate: {state.guardianStatus}
            </text>
            <rect x="16" y="132" width="200" height="18" fill="rgba(45,212,191,0.08)" />
            <text x="22" y="144" fill="#2dd4bf" fontSize="9" fontFamily="JetBrains Mono, monospace">
              CAUSAL AUDIT: ZERO LOOK-AHEAD
            </text>
          </g>
        </svg>
      </div>

      {/* Live Weight Bar & State Summary */}
      <div
        style={{
          marginTop: "1rem",
          paddingTop: "0.9rem",
          borderTop: "1px solid var(--border-subtle)",
        }}
      >
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            fontSize: "0.75rem",
            marginBottom: "0.4rem",
          }}
          className="font-mono"
        >
          <span style={{ color: "var(--accent-cyan)" }}>Momentum Scout: {state.momWeight}%</span>
          <span style={{ color: "var(--text-muted)" }}>Config {state.configVersion}</span>
          <span style={{ color: "var(--accent-mint)" }}>Reversal Scout: {state.revWeight}%</span>
        </div>
        <div className="weight-bar-track">
          <div
            className="weight-bar-fill"
            style={{ width: `${state.momWeight}%`, background: "var(--accent-cyan)" }}
          />
          <div
            className="weight-bar-fill"
            style={{ width: `${state.revWeight}%`, background: "var(--accent-mint)" }}
          />
        </div>
        <p
          style={{
            marginTop: "0.75rem",
            fontSize: "0.82rem",
            color: "var(--text-secondary)",
          }}
        >
          {state.verdictNote}
        </p>
      </div>
    </div>
  );
}
