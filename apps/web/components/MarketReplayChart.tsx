"use client";

import React, { useMemo, useState } from "react";
import {
  AdaptationEvent,
  Candle,
  PaperOrder,
  formatPrice,
  formatUtcShort,
} from "@/lib/contracts";

interface MarketReplayChartProps {
  candles: Candle[];
  orders: PaperOrder[];
  adaptations: AdaptationEvent[];
  selectedAdaptationId: string | null;
  onSelectAdaptation: (adaptationId: string) => void;
  quoteAsset: string;
  baseAsset: string;
}

export default function MarketReplayChart({
  candles,
  orders,
  adaptations,
  selectedAdaptationId,
  onSelectAdaptation,
  quoteAsset,
  baseAsset,
}: MarketReplayChartProps) {
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);

  const visible = useMemo(() => candles.slice(-110), [candles]);

  const { minPrice, maxPrice, maxVol, emaFast, emaSlow } = useMemo(() => {
    if (visible.length === 0) {
      return { minPrice: 0, maxPrice: 1, maxVol: 1, emaFast: [], emaSlow: [] };
    }
    let minP = Infinity;
    let maxP = -Infinity;
    let maxV = 0;

    const eFast: number[] = [];
    const eSlow: number[] = [];
    const alphaFast = 2 / 7;
    const alphaSlow = 2 / 19;

    visible.forEach((c, idx) => {
      if (c.low < minP) minP = c.low;
      if (c.high > maxP) maxP = c.high;
      if (c.volume > maxV) maxV = c.volume;
      if (idx === 0) {
        eFast.push(c.close);
        eSlow.push(c.close);
      } else {
        eFast.push(alphaFast * c.close + (1 - alphaFast) * eFast[idx - 1]);
        eSlow.push(alphaSlow * c.close + (1 - alphaSlow) * eSlow[idx - 1]);
      }
    });

    const pad = (maxP - minP) * 0.08 || maxP * 0.02 || 1e-6;
    return {
      minPrice: minP - pad,
      maxPrice: maxP + pad,
      maxVol: maxV || 1,
      emaFast: eFast,
      emaSlow: eSlow,
    };
  }, [visible]);

  const adaptiveOrdersByBar = useMemo(() => {
    const map = new Map<number, PaperOrder[]>();
    orders
      .filter((o) => o.track === "adaptive")
      .forEach((o) => {
        const list = map.get(o.fillCandleIndex) || [];
        list.push(o);
        map.set(o.fillCandleIndex, list);
      });
    return map;
  }, [orders]);

  const adaptationsByBar = useMemo(() => {
    const map = new Map<number, AdaptationEvent>();
    adaptations.forEach((ev) => {
      map.set(ev.candleIndex, ev);
    });
    return map;
  }, [adaptations]);

  const inspectedCandle =
    hoverIdx !== null && visible[hoverIdx]
      ? visible[hoverIdx]
      : visible[visible.length - 1];

  const width = 780;
  const height = 310;
  const chartTop = 22;
  const chartBottom = 242;
  const volTop = 252;
  const volBottom = 292;
  const leftPad = 14;
  const rightPad = 72;
  const plotWidth = width - leftPad - rightPad;
  const plotHeight = chartBottom - chartTop;

  const priceToY = (p: number) => {
    const ratio = (p - minPrice) / Math.max(1e-12, maxPrice - minPrice);
    return chartBottom - ratio * plotHeight;
  };

  const idxToX = (i: number) => {
    if (visible.length <= 1) return leftPad + plotWidth / 2;
    return leftPad + (i / (visible.length - 1)) * plotWidth;
  };

  const emaFastPoints = emaFast.map((v, i) => `${idxToX(i).toFixed(1)},${priceToY(v).toFixed(1)}`).join(" ");
  const emaSlowPoints = emaSlow.map((v, i) => `${idxToX(i).toFixed(1)},${priceToY(v).toFixed(1)}`).join(" ");

  const barWidth = Math.max(2.5, Math.min(9, (plotWidth / Math.max(1, visible.length)) * 0.62));

  return (
    <div className="market-chart">
      <details className="chart-details"><summary>Candle details</summary>
      {/* Point-in-time telemetry strip */}
      <div
        className="font-mono chart-telemetry"
        style={{
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "space-between",
          gap: "0.75rem",
          fontSize: "0.73rem",
          paddingBottom: "0.65rem",
          marginBottom: "0.5rem",
          borderBottom: "1px solid var(--border-subtle)",
          color: "var(--text-secondary)",
        }}
      >
        {inspectedCandle ? (
          <div style={{ display: "flex", flexWrap: "wrap", gap: "0.9rem" }}>
            <span>
              BAR <strong style={{ color: "var(--text-primary)" }}>#{inspectedCandle.index}</strong>
            </span>
            <span>{formatUtcShort(inspectedCandle.observedAt)}</span>
            <span>
              O: <strong style={{ color: "var(--text-primary)" }}>{formatPrice(inspectedCandle.open)}</strong>
            </span>
            <span>
              H: <strong style={{ color: "var(--text-primary)" }}>{formatPrice(inspectedCandle.high)}</strong>
            </span>
            <span>
              L: <strong style={{ color: "var(--text-primary)" }}>{formatPrice(inspectedCandle.low)}</strong>
            </span>
            <span>
              C:{" "}
              <strong
                style={{
                  color:
                    inspectedCandle.close >= inspectedCandle.open
                      ? "var(--accent-mint)"
                      : "var(--danger-red)",
                }}
              >
                {formatPrice(inspectedCandle.close)} {quoteAsset}
              </strong>
            </span>
            <span>
              VOL: <strong style={{ color: "var(--text-primary)" }}>{Math.round(inspectedCandle.volume).toLocaleString()}</strong>
            </span>
          </div>
        ) : (
          <span>Loading OHLCV series...</span>
        )}
        <div style={{ display: "flex", gap: "0.85rem", alignItems: "center" }}>
          <span style={{ color: "#6f7da4" }}>― EMA(6)</span>
          <span style={{ color: "#b08c51" }}>― EMA(18)</span>
          <span style={{ color: "var(--accent-mint)" }}>▲ BUY</span>
          <span style={{ color: "#c66e70" }}>▼ SELL</span>
          <span style={{ color: "var(--accent-mint)" }}>◆ ADAPT</span>
        </div>
      </div>

      </details>
      {/* Interactive SVG Candlestick + Signal + Adaptation Chart */}
      <div style={{ position: "relative", width: "100%" }}>
        <svg
          viewBox={`0 0 ${width} ${height}`}
          style={{ width: "100%", height: "auto", display: "block", background: "#ffffff" }}
          role="img"
          aria-label={`Historical OHLCV price chart for ${baseAsset}/${quoteAsset} with paper trade fills and adaptation markers`}
          onMouseLeave={() => setHoverIdx(null)}
        >
          {/* Horizontal price guide lines */}
          {[0, 0.25, 0.5, 0.75, 1].map((frac) => {
            const p = minPrice + frac * (maxPrice - minPrice);
            const y = priceToY(p);
            return (
              <g key={frac}>
                
                <text
                  x={width - rightPad + 6}
                  y={y + 3}
                  fill="#64748b"
                  fontSize="9.5"
                  fontFamily="JetBrains Mono, monospace"
                >
                  {formatPrice(p)}
                </text>
              </g>
            );
          })}

          {/* Separator between price and volume */}
          

          {/* Adaptation Event Vertical Markers */}
          {visible.map((c, i) => {
            const adapt = adaptationsByBar.get(c.index);
            if (!adapt) return null;
            const x = idxToX(i);
            const isSelected = selectedAdaptationId === adapt.id;
            const isAccepted = adapt.status === "ACCEPTED";
            const strokeColor = isAccepted ? "#42845d" : "#c66e70";
            return (
              <g
                key={adapt.id}
                style={{ cursor: "pointer" }}
                onClick={() => onSelectAdaptation(adapt.id)}
              >
                <line
                  x1={x}
                  y1={chartTop}
                  x2={x}
                  y2={volBottom}
                  stroke={strokeColor}
                  strokeWidth={isSelected ? "2" : "1.2"}
                  strokeDasharray={isAccepted ? "none" : "3 3"}
                  opacity={isSelected ? 1 : 0.75}
                />
                <rect
                  x={x - 28}
                  y={4}
                  width="56"
                  height="15"
                  fill={isSelected ? strokeColor : "#edf1ee"}
                  stroke={strokeColor}
                  strokeWidth="1"
                />
                <text
                  x={x}
                  y={14}
                  textAnchor="middle"
                  fill={isSelected ? "#090b0e" : strokeColor}
                  fontSize="8.5"
                  fontWeight="600"
                  fontFamily="JetBrains Mono, monospace"
                >
                  {isAccepted ? adapt.proposedVersion || "ADAPT" : "REJECT"}
                </text>
              </g>
            );
          })}

          {/* Candlesticks + Volume Bars */}
          {visible.map((c, i) => {
            const x = idxToX(i);
            const isUp = c.close >= c.open;
            const color = isUp ? "#42845d" : "#c66e70";
            const highY = priceToY(c.high);
            const lowY = priceToY(c.low);
            const openY = priceToY(c.open);
            const closeY = priceToY(c.close);
            const bodyTop = Math.min(openY, closeY);
            const bodyHeight = Math.max(1.5, Math.abs(closeY - openY));

            const volRatio = c.volume / maxVol;
            const vHeight = Math.max(1, volRatio * (volBottom - volTop));
            const vY = volBottom - vHeight;

            return (
              <g
                key={c.index}
                onMouseEnter={() => setHoverIdx(i)}
                style={{ cursor: "crosshair" }}
              >
                {/* Invisible wider hit target */}
                <rect
                  x={x - Math.max(4, barWidth)}
                  y={chartTop}
                  width={Math.max(8, barWidth * 2)}
                  height={volBottom - chartTop}
                  fill="transparent"
                />
                {/* Wick */}
                <line x1={x} y1={highY} x2={x} y2={lowY} stroke={color} strokeWidth="1" />
                {/* Candle Body */}
                <rect
                  x={x - barWidth / 2}
                  y={bodyTop}
                  width={barWidth}
                  height={bodyHeight}
                  fill={color}
                  opacity={hoverIdx === i ? 1 : 0.85}
                />
                {/* Volume Bar */}
                <rect
                  x={x - barWidth / 2}
                  y={vY}
                  width={barWidth}
                  height={vHeight}
                  fill={color}
                  opacity={0.32}
                />
              </g>
            );
          })}

          {/* EMA Overlays */}
          {visible.length > 2 && (
            <>
              <polyline
                fill="none"
                stroke="#6f7da4"
                strokeWidth="1.4"
                points={emaFastPoints}
                opacity="0.85"
              />
              <polyline
                fill="none"
                stroke="#b08c51"
                strokeWidth="1.3"
                points={emaSlowPoints}
                opacity="0.75"
              />
            </>
          )}

          {/* Executed Paper Orders (Adaptive Track) */}
          {visible.map((c, i) => {
            const barOrders = adaptiveOrdersByBar.get(c.index);
            if (!barOrders || barOrders.length === 0) return null;
            const x = idxToX(i);
            return barOrders.map((ord) => {
              const isBuy = ord.side === "BUY";
              const y = isBuy ? priceToY(c.low) + 12 : priceToY(c.high) - 12;
              return (
                <g key={ord.id}>
                  <polygon
                    points={
                      isBuy
                        ? `${x},${y - 7} ${x - 5},${y + 3} ${x + 5},${y + 3}`
                        : `${x},${y + 7} ${x - 5},${y - 3} ${x + 5},${y - 3}`
                    }
                    fill={isBuy ? "#42845d" : "#b08c51"}
                    stroke="#090b0e"
                    strokeWidth="1"
                  />
                </g>
              );
            });
          })}

          {/* Hover Crosshair */}
          {hoverIdx !== null && visible[hoverIdx] && (
            <line
              x1={idxToX(hoverIdx)}
              y1={chartTop}
              x2={idxToX(hoverIdx)}
              y2={volBottom}
              stroke="#9ba79f"
              strokeDasharray="2 2"
              pointerEvents="none"
            />
          )}
        </svg>
      </div>
    </div>
  );
}
