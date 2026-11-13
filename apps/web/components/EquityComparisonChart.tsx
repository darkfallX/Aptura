"use client";

import React from "react";
import { EquityPoint } from "@/lib/contracts";

interface EquityComparisonChartProps {
  equityCurve: EquityPoint[];
  initialCapitalUsd: number;
  mode: "equity" | "drawdown";
}

export default function EquityComparisonChart({
  equityCurve,
  initialCapitalUsd,
  mode,
}: EquityComparisonChartProps) {
  const width = 760;
  const height = 210;
  const leftPad = 14;
  const rightPad = 68;
  const topPad = 18;
  const bottomPad = 24;
  const plotW = width - leftPad - rightPad;
  const plotH = height - topPad - bottomPad;

  if (equityCurve.length === 0) {
    return (
      <div
        className="font-mono"
        style={{
          height: "210px",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "var(--text-muted)",
          fontSize: "0.8rem",
        }}
      >
        Advance replay to populate comparative equity curves.
      </div>
    );
  }

  let minVal = Infinity;
  let maxVal = -Infinity;

  equityCurve.forEach((pt) => {
    const vals =
      mode === "equity"
        ? [pt.adaptiveEquity, pt.fixedEquity, pt.momentumOnlyEquity, pt.cashEquity]
        : [-pt.adaptiveDrawdownPct, -pt.fixedDrawdownPct, -pt.momentumOnlyDrawdownPct, 0];
    vals.forEach((v) => {
      if (v < minVal) minVal = v;
      if (v > maxVal) maxVal = v;
    });
  });

  const span = maxVal - minVal;
  const pad = span * 0.12 || (mode === "equity" ? initialCapitalUsd * 0.02 : 1.0);
  const lo = minVal - pad;
  const hi = maxVal + pad;

  const valToY = (v: number) => {
    const r = (v - lo) / Math.max(1e-9, hi - lo);
    return topPad + plotH - r * plotH;
  };

  const idxToX = (i: number) => {
    if (equityCurve.length <= 1) return leftPad + plotW / 2;
    return leftPad + (i / (equityCurve.length - 1)) * plotW;
  };

  const buildPoints = (getter: (pt: EquityPoint) => number) =>
    equityCurve.map((pt, i) => `${idxToX(i).toFixed(1)},${valToY(getter(pt)).toFixed(1)}`).join(" ");

  const adaptivePts = buildPoints((p) => (mode === "equity" ? p.adaptiveEquity : -p.adaptiveDrawdownPct));
  const fixedPts = buildPoints((p) => (mode === "equity" ? p.fixedEquity : -p.fixedDrawdownPct));
  const momPts = buildPoints((p) => (mode === "equity" ? p.momentumOnlyEquity : -p.momentumOnlyDrawdownPct));
  const cashPts = buildPoints((p) => (mode === "equity" ? p.cashEquity : 0));

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      style={{ width: "100%", height: "auto", display: "block", background: "#ffffff" }}
      role="img"
      aria-label="Counterfactual equity comparison between Aptura Adaptive Supervisor, Fixed 50/50 baseline, Momentum-Only baseline, and Cash benchmark"
    >
      {[0, 0.5, 1].map((frac) => {
        const val = lo + frac * (hi - lo);
        const y = valToY(val);
        return (
          <g key={frac}>
            
            <text
              x={width - rightPad + 6}
              y={y + 3}
              fill="#64748b"
              fontSize="9.5"
              fontFamily="JetBrains Mono, monospace"
            >
              {mode === "equity" ? `$${val.toFixed(0)}` : `${val.toFixed(1)}%`}
            </text>
          </g>
        );
      })}

      {/* Cash benchmark */}
      <polyline
        fill="none"
        stroke="#64748b"
        strokeWidth="1.2"
        strokeDasharray="4 4"
        points={cashPts}
      />

      {/* Momentum-Only baseline */}
      <polyline
        fill="none"
        stroke="#b08c51"
        strokeWidth="1.5"
        points={momPts}
        opacity="0.85"
      />

      {/* Fixed 50/50 baseline */}
      <polyline
        fill="none"
        stroke="#6f7da4"
        strokeWidth="1.6"
        points={fixedPts}
        opacity="0.9"
      />

      {/* Aptura Adaptive Supervisor */}
      <polyline
        fill="none"
        stroke="#42845d"
        strokeWidth="2.4"
        points={adaptivePts}
      />
    </svg>
  );
}
