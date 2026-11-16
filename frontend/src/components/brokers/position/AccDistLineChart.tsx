// One line per stock for the selected broker, on one shared time axis (one y-scale: shares).
// Tools: zoom in / out, drag-to-zoom into a region, drag-to-pan, reset, copy as CSV.  The zoom
// window is index-based; it resets whenever the time axis changes (new range or stocks).
// Stocks are identified by their company logo (right of the lines, in the legend and in the
// tooltip), so the chart keeps working when there are more stocks than distinct colours.
import { useEffect, useMemo, useRef, useState } from 'react';
import {
  CartesianGrid, Line, LineChart, ReferenceArea, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import type { MouseHandlerDataParam } from 'recharts';
import { ClipboardCopy, Hand, Minus, Plus, RotateCcw, ScanSearch } from 'lucide-react';

import CompanyLogo from '../../companies/CompanyLogo';
import { formatCount } from '../../market/format';
import { compact, seriesColor } from './format';

const GRID = 'var(--trading-grid)';
const MUTED = 'var(--trading-muted)';
const AXIS_W = 64;
const MIN_SPAN = 4;

// Layout numbers shared by the chart and the logo column, so the logos line up with the lines.
const CHART_H = 420;
const MARGIN = { top: 16, right: 52, bottom: 0, left: 0 };
const X_AXIS_H = 30;
const PLOT_H = CHART_H - MARGIN.top - MARGIN.bottom - X_AXIS_H;
const LOGO = 28;
const LOGO_GAP = 32;
const MAX_END_LOGOS = 10;
const MANY_LINES = 8;
const TOOLTIP_ROWS = 10;

export interface LineSeries {
  symbol: string;
  slot: number;
  values: number[];
  /** Shown in the legend: the final value (cumulative) or the range total (per-interval). */
  total: number;
  /** Company name and logo, shown instead of a colour dot. */
  name?: string;
  logoUrl?: string | null;
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

/** The first 8 stocks use the app's series colours; after that colours are generated, so any number works. */
function lineColour(slot: number) {
  return slot < 8 ? seriesColor(slot) : `hsl(${Math.round((slot * 137.5) % 360)} 65% 55%)`;
}

/** Round a positive number up to 1, 2, 5 or 10 times a power of ten, so the y axis gets tidy ticks. */
function niceCeil(x: number) {
  if (x <= 0) return 0;
  const exp = 10 ** Math.floor(Math.log10(x));
  const f = x / exp;
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * exp;
}

function ChartTooltip({ active, label, payload, longLabel, series }: {
  active?: boolean; label?: number; payload?: { dataKey: string; value: number; color: string }[];
  longLabel: (index: number) => string;
  series: LineSeries[];
}) {
  if (!active || !payload?.length || label == null) return null;
  const rows = [...payload].sort((a, b) => b.value - a.value);
  const shown = rows.slice(0, TOOLTIP_ROWS);
  return (
    <div className="min-w-[180px] rounded-lg border border-bg-border bg-bg-elevated px-3 py-2 text-xs shadow-xl">
      <p className="mb-1.5 font-semibold text-text-muted">{longLabel(label)}</p>
      {shown.map((row) => {
        const info = series.find((s) => s.symbol === row.dataKey);
        return (
          <p key={row.dataKey} className="flex items-center gap-2 py-0.5 font-mono">
            <CompanyLogo symbol={String(row.dataKey)} name={info?.name} logoUrl={info?.logoUrl} size="sm" />
            <span className="font-sans text-text-secondary">{row.dataKey}</span>
            <span className="ml-auto pl-4 text-text-primary">{formatCount(row.value)}</span>
          </p>
        );
      })}
      {rows.length > shown.length && (
        <p className="mt-1 text-text-muted">+ {rows.length - shown.length} more stocks</p>
      )}
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
  const visible = useMemo(() => series.filter((s) => !hidden.has(s.symbol)), [series, hidden]);
  const hasNegative = visible.some((s) => s.values.some((v) => v < 0));
  const many = series.length > MANY_LINES;

  // The y axis is fixed to the visible lines, so the logo column can sit exactly at each line's end.
  const yDomain = useMemo<[number, number]>(() => {
    let lo = 0;
    let hi = 0;
    visible.forEach((s) => {
      for (let i = view[0]; i <= view[1]; i += 1) {
        const v = s.values[i];
        if (typeof v === 'number') {
          if (v > hi) hi = v;
          if (v < lo) lo = v;
        }
      }
    });
    const top = niceCeil(hi);
    const bottom = -niceCeil(-lo);
    return top === bottom ? [0, 1] : [bottom, top];
  }, [visible, view]);

  // Logos at the right end of the biggest lines (and the hovered one), spread out so they never overlap.
  const endLogos = useMemo(() => {
    const [lo, hi] = yDomain;
    const span = hi - lo || 1;
    const items = visible
      .map((s) => ({ s, value: s.values[view[1]] }))
      .filter((item): item is { s: LineSeries; value: number } => typeof item.value === 'number');
    const chosen = [...items].sort((a, b) => Math.abs(b.value) - Math.abs(a.value)).slice(0, MAX_END_LOGOS);
    if (highlight && !chosen.some((c) => c.s.symbol === highlight)) {
      const extra = items.find((item) => item.s.symbol === highlight);
      if (extra) chosen.push(extra);
    }
    const placed = chosen
      .map((c) => ({ ...c, y: ((hi - c.value) / span) * PLOT_H }))
      .sort((a, b) => a.y - b.y);
    placed.forEach((p, i) => { if (i > 0 && p.y < placed[i - 1].y + LOGO_GAP) p.y = placed[i - 1].y + LOGO_GAP; });
    for (let i = placed.length - 1; i >= 0; i -= 1) {
      const maxY = PLOT_H - (placed.length - 1 - i) * LOGO_GAP;
      if (placed[i].y > maxY) placed[i].y = maxY;
    }
    return placed;
  }, [visible, view, yDomain, highlight]);

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
      const width = box.current.clientWidth - AXIS_W - MARGIN.right;
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

      <div ref={box} className={`relative select-none ${tool === 'zoom' ? 'cursor-crosshair' : drag.current ? 'cursor-grabbing' : 'cursor-grab'}`}>
        <ResponsiveContainer width="100%" height={CHART_H}>
          <LineChart data={rows} margin={MARGIN}
            onMouseDown={onDown} onMouseMove={onMove} onMouseUp={onUp} onMouseLeave={onUp}>
            <CartesianGrid vertical={false} stroke={GRID} strokeOpacity={0.35} strokeDasharray="3 3" />
            <XAxis dataKey="i" type="number" domain={view} allowDataOverflow tickFormatter={(v: number) => shortLabel(v)}
              height={X_AXIS_H} tick={{ fill: MUTED, fontSize: 11 }} tickLine={false} axisLine={{ stroke: GRID }} minTickGap={36} allowDecimals={false} />
            <YAxis width={AXIS_W} domain={yDomain} allowDataOverflow tickFormatter={compact} tick={{ fill: MUTED, fontSize: 11 }} tickLine={false} axisLine={false}
              label={{ value: yTitle, angle: -90, position: 'insideLeft', fill: MUTED, fontSize: 11, dx: 4, style: { textAnchor: 'middle' } }} />
            <Tooltip content={<ChartTooltip longLabel={longLabel} series={series} />} cursor={{ stroke: MUTED, strokeDasharray: '3 3' }} />
            {hasNegative && <ReferenceLine y={0} stroke={MUTED} />}
            {visible.map((s) => {
              const dim = highlight != null && highlight !== s.symbol;
              const lit = highlight === s.symbol;
              return (
                <Line key={s.symbol} dataKey={s.symbol} stroke={lineColour(s.slot)} type="linear" dot={false}
                  strokeWidth={lit ? 3 : many ? 1.5 : 2} strokeOpacity={dim ? (many ? 0.12 : 0.2) : 1} isAnimationActive={false}
                  activeDot={{ r: 4, stroke: 'var(--trading-panel)', strokeWidth: 2 }} />
              );
            })}
            {selecting && (
              <ReferenceArea x1={Math.min(...selecting)} x2={Math.max(...selecting)} fill="var(--trading-accent)" fillOpacity={0.15}
                stroke="var(--trading-accent)" strokeOpacity={0.6} />
            )}
          </LineChart>
        </ResponsiveContainer>

        {/* Logo column: one logo per big line, level with where that line ends. The ring keeps the line colour. */}
        <div className="pointer-events-none absolute right-0" style={{ top: MARGIN.top, height: PLOT_H, width: MARGIN.right }}>
          {endLogos.map((p) => {
            const dim = highlight != null && highlight !== p.s.symbol;
            return (
              <div key={p.s.symbol}
                className="absolute left-3 rounded-lg transition-[top,opacity] duration-150"
                style={{
                  top: p.y - LOGO / 2, width: LOGO, height: LOGO, opacity: dim ? 0.3 : 1,
                  boxShadow: `0 0 0 2px ${lineColour(p.s.slot)}`,
                }}>
                <CompanyLogo symbol={p.s.symbol} name={p.s.name} logoUrl={p.s.logoUrl} size="sm" />
              </div>
            );
          })}
        </div>
      </div>

      <div className={`flex flex-wrap justify-center gap-x-4 gap-y-1 ${many ? 'max-h-28 overflow-y-auto pr-1' : ''}`}>
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
              <span className={off ? 'opacity-50 grayscale' : ''}>
                <CompanyLogo symbol={s.symbol} name={s.name} logoUrl={s.logoUrl} size="sm" />
              </span>
              <span className="font-semibold">{s.symbol}</span>
              <span className="font-mono">{formatCount(s.total)}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}