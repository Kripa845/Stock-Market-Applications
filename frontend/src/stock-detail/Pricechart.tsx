// import { useEffect, useRef } from "react";
// import { init, dispose } from "klinecharts";
// import type { Candle } from "./types";

// const UP = "#10b981";
// const DOWN = "#ef4444";

// export default function PriceChart({ data, height = 170 }: { data: Candle[]; height?: number }) {
//   const ref = useRef<HTMLDivElement>(null);

//   useEffect(() => {
//     const el = ref.current;
//     if (!el) return;
//     const chart = init(el);
//     if (!chart) return;

//     chart.setStyles({
//       grid: { show: false },
//       candle: {
//         bar: {
//           upColor: UP,
//           downColor: DOWN,
//           noChangeColor: "#64748b",
//           upBorderColor: UP,
//           downBorderColor: DOWN,
//           noChangeBorderColor: "#64748b",
//           upWickColor: UP,
//           downWickColor: DOWN,
//           noChangeWickColor: "#64748b",
//         },
//         priceMark: { show: false, last: { show: false } },
//         tooltip: { showRule: "none" },
//       },
//       xAxis: { show: false },
//       yAxis: { show: false },
//       crosshair: { show: false },
//       separator: { size: 0 },
//     });

//     chart.setDataLoader({
//       getBars: ({ callback }) => {
//         callback(data as any, false);
//       },
//     });
//     return () => dispose(el);
//   }, [data]);

//   return <div ref={ref} style={{ height }} className="w-full" />;
// }

import type { Candle } from "./types";

const UP = "#10b981";
const DOWN = "#ef4444";
const FLAT = "#64748b";
const STEP = 8; // horizontal units per candle (the SVG scales to fit the panel width)

/** Dependency-free candlestick strip. Hover a candle to see its OHLC. */
export default function PriceChart({ data, height = 170 }: { data: Candle[]; height?: number }) {
  if (!data || data.length === 0) {
    return (
      <div style={{ height }} className="flex items-center justify-center text-[10px] text-slate-500">
        No price data available
      </div>
    );
  }

  const pad = 6;
  const width = data.length * STEP;
  const hi = Math.max(...data.map((c) => c.high));
  const lo = Math.min(...data.map((c) => c.low));
  const y = (v: number) => pad + ((hi - v) / (hi - lo || 1)) * (height - pad * 2);
  const bodyW = STEP * 0.62;

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      width="100%"
      height={height}
      role="img"
      aria-label="Candlestick price chart, last 6 months"
    >
      {data.map((c, i) => {
        const x = i * STEP + STEP / 2;
        const color = c.close > c.open ? UP : c.close < c.open ? DOWN : FLAT;
        const top = y(Math.max(c.open, c.close));
        const h = Math.max(1, Math.abs(y(c.open) - y(c.close)));
        return (
          <g key={c.timestamp}>
            <title>
              {`${new Date(c.timestamp).toLocaleDateString()}  O ${c.open}  H ${c.high}  L ${c.low}  C ${c.close}`}
            </title>
            <line
              x1={x}
              x2={x}
              y1={y(c.high)}
              y2={y(c.low)}
              stroke={color}
              strokeWidth={1}
              vectorEffect="non-scaling-stroke"
            />
            <rect x={x - bodyW / 2} y={top} width={bodyW} height={h} fill={color} />
          </g>
        );
      })}
    </svg>
  );
}