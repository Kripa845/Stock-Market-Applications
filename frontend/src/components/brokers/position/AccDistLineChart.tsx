// One line per stock for the selected broker, on one shared time axis (one y-scale: shares).
// Tools: zoom in / out, drag-to-zoom into a region, drag-to-pan, reset, copy as CSV.  The zoom
// window is index-based; it resets whenever the time axis changes (new range or stocks).
import { useEffect, useMemo, useRef, useState } from 'react';
import {
  CartesianGrid, Line, LineChart, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import type { MouseHandlerDataParam } from 'recharts';
import { ClipboardCopy, Hand, Minus, Plus, RotateCcw, ScanSearch } from 'lucide-react';

import { formatCount } from '../../market/format';
import { compact, seriesColor } from './format';

const GRID = 'var(--trading-grid)';
const MUTED = 'var(--trading-muted)';
const AXIS_W = 64;
const MIN_SPAN = 4;

export interface LineSeries {
  symbol: string;
  slot: number;
  values: number[];
  /** Shown in the legend: the final value (cumulative) or the range total (per-interval). */
  total: number;
}

interface Props {
  times: string[];
  shortLabel: (index: number) => string;
  longLabel: (index: number) => string;
  series: LineSeries[];
  hidden: Set<string>;
  highlight: string | null;
  yTitle: string;
  onToggle: (symbol: string) => void;
  /** Legend hover: shares the page's highlight with the chips and the stock picker. */
  onHighlight: (symbol: string | null) => void;
}

type Tool = 'pan' | 'zoom';

function ChartTooltip({ active, label, payload, longLabel }: {
  active?: boolean; label?: number; payload?: { dataKey: string; value: number; color: string }[];
  longLabel: (index: number) => string;
}) {
  if (!active || !payload?.length || label == null) return null;
  const rows = [...payload].sort((a, b) => b.value - a.value);
  return (
    <div className="min-w-[160px] rounded-lg border border-bg-border bg-bg-elevated px-3 py-2 text-xs shadow-xl">
      <p className="mb-1.5 font-semibold text-text-muted">{longLabel(label)}</p>
      {rows.map((row) => (
        <p key={row.dataKey} className="flex items-center gap-2 py-0.5 font-mono">
          <span className="h-2 w-2 rounded-full" style={{ background: row.color }} />
          <span className="font-sans text-text-secondary">{row.dataKey}</span>
          <span className="ml-auto pl-4 text-text-primary">{formatCount(row.value)}</span>
        </p>
      ))}
    </div>
  );
}

export default function AccDistLineChart({ times, shortLabel, longLabel, series, hidden, highlight, yTitle, onToggle, onHighlight }: Props) {
  const last = Math.max(0, times.length - 1);
  const [view, setView] = useState<[number, number]>([0, last]);
  const [tool, setTool] = useState<Tool>('pan');
  const [selecting, setSelecting] = useState<[number, number] | null>(null);
  const [copied, setCopied] = useState('');
  const drag = useRef<{ x: number; view: [number, number] } | null>(null);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => { setView([0, last]); }, [times, last]);

  const rows = useMemo(() => times.map((_, i) => {
    const row: Record<string, number> = { i };
    series.forEach((s) => { row[s.symbol] = s.values[i]; });
    return row;
  }), [times, series]);
  const visible = series.filter((s) => !hidden.has(s.symbol));
  const hasNegative = visible.some((s) => s.values.some((v) => v < 0));

  const clampView = (a: number, b: number): [number, number] => {
    let lo = a, hi = b;
    if (hi - lo < MIN_SPAN) { const c = (lo + hi) / 2; lo = c - MIN_SPAN / 2; hi = c + MIN_SPAN / 2; }
    if (lo < 0) { hi -= lo; lo = 0; }
    if (hi > last) { lo -= hi - last; hi = last; }
    return [Math.max(0, Math.round(lo)), Math.min(last, Math.round(hi))];
  };
  const zoomBy = (factor: number) => {
    const [a, b] = view;
    const c = (a + b) / 2, half = ((b - a) / 2) * factor;
    setView(clampView(c - half, c + half));
  };

  const onDown = (state: MouseHandlerDataParam, event: React.SyntheticEvent) => {
    const index = typeof state.activeLabel === 'number' ? state.activeLabel : Number(state.activeLabel);
    if (tool === 'zoom' && Number.isFinite(index)) setSelecting([index, index]);
    if (tool === 'pan') drag.current = { x: (event as React.MouseEvent).clientX, view };
  };
  const onMove = (state: MouseHandlerDataParam, event: React.SyntheticEvent) => {
    if (selecting) {
      const index = Number(state.activeLabel);
      if (Number.isFinite(index)) setSelecting([selecting[0], index]);
    } else if (drag.current && box.current) {
      const width = box.current.clientWidth - AXIS_W - 16;
      const [a, b] = drag.current.view;
      const shift = -(((event as React.MouseEvent).clientX - drag.current.x) / width) * (b - a);
      setView(clampView(a + shift, b + shift));
    }
  };
  const onUp = () => {
    if (selecting) {
      const [a, b] = selecting;
      if (Math.abs(b - a) >= 2) setView(clampView(Math.min(a, b), Math.max(a, b)));
      setSelecting(null);
    }
    drag.current = null;
  };

  const copyCsv = async () => {
    const header = ['time', ...series.map((s) => s.symbol)].join(',');
    const lines = times.map((_, i) => [`"${longLabel(i)}"`, ...series.map((s) => s.values[i])].join(','));
    try {
      await navigator.clipboard.writeText([header, ...lines].join('\n'));
      setCopied('Copied');
    } catch {
      setCopied('Copy blocked');
    }
    window.setTimeout(() => setCopied(''), 1200);
  };

  const toolButton = (label: string, icon: React.ReactNode, onClick: () => void, pressed?: boolean) => (
    <button type="button" aria-label={label} title={label} onClick={onClick} aria-pressed={pressed}
      className={`flex h-8 w-8 items-center justify-center rounded-md transition ${
        pressed ? 'bg-accent/20 text-accent' : 'text-text-secondary hover:bg-bg-elevated hover:text-text-primary'
      }`}>
      {icon}
    </button>
  );
  const zoomed = view[0] > 0 || view[1] < last;

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-[11px] text-text-muted">
          {tool === 'pan' ? 'Drag the chart to pan' : 'Drag across the chart to zoom into a region'}
          {zoomed && ` · showing ${shortLabel(view[0])} – ${shortLabel(view[1])}`}
        </span>
        <div className="flex items-center gap-0.5 rounded-lg border border-bg-border bg-bg-card p-1">
          {toolButton('Zoom in', <Plus size={15} />, () => zoomBy(0.6))}
          {toolButton('Zoom out', <Minus size={15} />, () => zoomBy(1 / 0.6))}
          {toolButton('Drag to zoom into a region', <ScanSearch size={15} />, () => setTool('zoom'), tool === 'zoom')}
          {toolButton('Drag to pan', <Hand size={15} />, () => setTool('pan'), tool === 'pan')}
          {toolButton('Reset zoom', <RotateCcw size={15} />, () => setView([0, last]))}
          {toolButton('Copy data as CSV', <ClipboardCopy size={15} />, copyCsv)}
          {copied && <span className="px-1 text-[11px] text-text-muted">{copied}</span>}
        </div>
      </div>

      <div ref={box} className={`select-none ${tool === 'zoom' ? 'cursor-crosshair' : drag.current ? 'cursor-grabbing' : 'cursor-grab'}`}>
        <ResponsiveContainer width="100%" height={420}>
          <LineChart data={rows} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}
            onMouseDown={onDown} onMouseMove={onMove} onMouseUp={onUp} onMouseLeave={onUp}>
            <CartesianGrid vertical={false} stroke={GRID} strokeOpacity={0.35} strokeDasharray="3 3" />
            <XAxis dataKey="i" type="number" domain={view} allowDataOverflow tickFormatter={(v: number) => shortLabel(v)}
              tick={{ fill: MUTED, fontSize: 11 }} tickLine={false} axisLine={{ stroke: GRID }} minTickGap={36} allowDecimals={false} />
            <YAxis width={AXIS_W} tickFormatter={compact} tick={{ fill: MUTED, fontSize: 11 }} tickLine={false} axisLine={false}
              label={{ value: yTitle, angle: -90, position: 'insideLeft', fill: MUTED, fontSize: 11, dx: 4, style: { textAnchor: 'middle' } }} />
            <Tooltip content={<ChartTooltip longLabel={longLabel} />} cursor={{ stroke: MUTED, strokeDasharray: '3 3' }} />
            {hasNegative && <ReferenceLine y={0} stroke={MUTED} />}
            {visible.map((s) => {
              const dim = highlight != null && highlight !== s.symbol;
              return (
                <Line key={s.symbol} dataKey={s.symbol} stroke={seriesColor(s.slot)} type="linear" dot={false}
                  strokeWidth={highlight === s.symbol ? 3 : 2} strokeOpacity={dim ? 0.2 : 1} isAnimationActive={false}
                  activeDot={{ r: 4, stroke: 'var(--trading-panel)', strokeWidth: 2 }} />
              );
            })}
            {selecting && (
              <ReferenceArea x1={Math.min(...selecting)} x2={Math.max(...selecting)} fill="var(--trading-accent)" fillOpacity={0.15}
                stroke="var(--trading-accent)" strokeOpacity={0.6} />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>

      <div className="flex flex-wrap justify-center gap-x-4 gap-y-1">
        {series.map((s) => {
          const off = hidden.has(s.symbol);
          const lit = !off && highlight === s.symbol;
          return (
            <button key={s.symbol} type="button" onClick={() => onToggle(s.symbol)} aria-pressed={!off}
              title={off ? `Show ${s.symbol}` : `Hide ${s.symbol}`}
              onMouseEnter={() => !off && onHighlight(s.symbol)} onMouseLeave={() => onHighlight(null)}
              onFocus={() => !off && onHighlight(s.symbol)} onBlur={() => onHighlight(null)}
              className={`flex items-center gap-1.5 py-1 text-xs transition ${
                off ? 'text-text-muted line-through opacity-50' : lit ? 'text-text-primary' : 'text-text-secondary hover:text-text-primary'
              }`}>
              <span className="h-2.5 w-2.5 rounded-full" style={{ background: seriesColor(s.slot) }} />
              <span className="font-semibold">{s.symbol}</span>
              <span className="font-mono">{formatCount(s.total)}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
