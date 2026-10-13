import { useMemo } from 'react';
import {
  Area, Bar, CartesianGrid, ComposedChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import type { ChartPoint } from '../../api/market';
import { formatCount, formatPrice } from './format';

// Price chart for the Market Overview card: area (default) or candles, volume bars along the bottom.

export type ChartMode = 'area' | 'candle';

const UP = '#26a69a';
const DOWN = '#ef5350';
const NPT = 'Asia/Kathmandu';

const timeLabel = (iso: string, intraday: boolean) =>
  intraday
    ? new Date(iso).toLocaleTimeString('en-GB', { timeZone: NPT, hour: '2-digit', minute: '2-digit' })
    : new Date(`${iso}T00:00:00`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: '2-digit' });

interface Row {
  t: string;
  close: number;
  open: number | null;
  high: number | null;
  low: number | null;
  volume: number | null;
  range: [number, number] | null;
}

interface CandleProps { x?: number; y?: number; width?: number; height?: number; payload?: Row }

/** One candle drawn inside the bar Recharts sizes for [low, high]. */
function Candle({ x = 0, y = 0, width = 0, height = 0, payload }: CandleProps) {
  if (!payload || payload.open == null || payload.high == null || payload.low == null) return null;
  const { open, close, high, low } = payload;
  const color = close >= open ? UP : DOWN;
  const span = high - low;
  const pixel = (price: number) => (span === 0 ? y : y + ((high - price) / span) * height);
  const top = pixel(Math.max(open, close));
  const bodyHeight = Math.max(1, pixel(Math.min(open, close)) - top);
  const centre = x + width / 2;
  const bodyWidth = Math.max(1, width * 0.7);
  return (
    <g>
      <line x1={centre} x2={centre} y1={y} y2={y + height} stroke={color} />
      <rect x={centre - bodyWidth / 2} y={top} width={bodyWidth} height={bodyHeight} fill={color} />
    </g>
  );
}

function ChartTooltip({ active, payload, intraday }: { active?: boolean; payload?: { payload: Row }[]; intraday: boolean }) {
  const row = payload?.[0]?.payload;
  if (!active || !row) return null;
  return (
    <div className="rounded-lg border border-bg-border bg-bg-elevated px-3 py-2 text-xs shadow-xl">
      <p className="mb-1 text-text-muted">{timeLabel(row.t, intraday)}</p>
      {row.open != null && (
        <p className="font-mono text-text-secondary">
          O {formatPrice(row.open)} · H {formatPrice(row.high)} · L {formatPrice(row.low)}
        </p>
      )}
      <p className="font-mono font-semibold text-text-primary">{formatPrice(row.close)}</p>
      {row.volume != null && <p className="text-text-muted">Vol {formatCount(row.volume)}</p>}
    </div>
  );
}

export default function OverviewPriceChart({ points, intraday, mode, previousClose }: {
  points: ChartPoint[];
  intraday: boolean;
  mode: ChartMode;
  previousClose: number | null;
}) {
  const rows = useMemo<Row[]>(() => points.map((p) => {
    const open = p.open == null ? null : Number(p.open);
    const high = p.high == null ? null : Number(p.high);
    const low = p.low == null ? null : Number(p.low);
    return {
      t: p.t, close: Number(p.close), open, high, low,
      volume: p.volume == null ? null : Number(p.volume),
      range: high != null && low != null ? [low, high] : null,
    };
  }), [points]);

  const first = rows[0]?.close ?? 0;
  const last = rows[rows.length - 1]?.close ?? 0;
  const reference = intraday && previousClose != null ? previousClose : first;
  const color = last >= reference ? UP : DOWN;
  const hasVolume = rows.some((r) => r.volume != null);
  const maxVolume = Math.max(0, ...rows.map((r) => r.volume ?? 0));
  const candles = mode === 'candle' && rows.every((r) => r.range != null);

  return (
    <ResponsiveContainer width="100%" height="100%">
      <ComposedChart data={rows} margin={{ top: 8, right: 0, left: 0, bottom: 0 }}>
        <defs>
          <linearGradient id="overview-area" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.35} />
            <stop offset="100%" stopColor={color} stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke="#242832" strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey="t" tickFormatter={(t: string) => timeLabel(t, intraday)} minTickGap={40}
          tick={{ fontSize: 10, fill: '#787b86' }} axisLine={false} tickLine={false} />
        <YAxis yAxisId="price" orientation="right" domain={['auto', 'auto']} width={48}
          tick={{ fontSize: 10, fill: '#787b86' }} axisLine={false} tickLine={false}
          tickFormatter={(v: number) => v.toLocaleString('en-IN', { maximumFractionDigits: 0 })} />
        {/* Volume uses the bottom quarter of the chart. */}
        <YAxis yAxisId="volume" hide domain={[0, maxVolume * 4 || 1]} />
        {hasVolume && <Bar yAxisId="volume" dataKey="volume" fill="#787b86" opacity={0.35} isAnimationActive={false} />}
        {intraday && previousClose != null && (
          <ReferenceLine yAxisId="price" y={previousClose} stroke={color} strokeDasharray="2 3" strokeOpacity={0.7} />
        )}
        {candles ? (
          <Bar yAxisId="price" dataKey="range" shape={<Candle />} isAnimationActive={false} />
        ) : (
          <Area yAxisId="price" type="monotone" dataKey="close" stroke={color} strokeWidth={1.5}
            fill="url(#overview-area)" dot={false} isAnimationActive={false} />
        )}
        <Tooltip content={<ChartTooltip intraday={intraday} />} cursor={{ stroke: '#787b86', strokeDasharray: '3 3' }} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
