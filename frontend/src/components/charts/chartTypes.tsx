// Chart types for KlinePriceChart (the TradingView-style "Bars / Candles / Line …" menu).
//
// klinecharts draws four of them natively (candle types + area). Heikin Ashi is a data
// transform drawn as normal candles. The rest are drawn by the CHART_TYPE indicator on the
// candle pane while the real candles are made transparent — they still set the price scale,
// the crosshair and the OHLC tooltip, so those keep working for every type.
import { useEffect, useRef, useState } from 'react';
import { ChevronDown } from 'lucide-react';
import { registerIndicator, type KLineData } from 'klinecharts';

export type ChartType =
  | 'bars' | 'candles' | 'hollow'
  | 'line' | 'line_markers' | 'step'
  | 'area' | 'hlc_area' | 'baseline'
  | 'columns' | 'high_low'
  | 'heikin_ashi';

const UP = '#22C55E';
const DOWN = '#EF4444';
const FLAT = '#64748B';
const LINE = '#3B82F6';
const TRANSPARENT = 'rgba(0,0,0,0)';

// ─── Icons (18×18, drawn in currentColor) ─────────────────────────────────────
const svg = (children: React.ReactNode) => (
  <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {children}
  </svg>
);

const ICONS: Record<ChartType, React.ReactNode> = {
  bars: svg(<><path d="M5 3v11M3 5h2M5 11h2" /><path d="M12 5v10M10 8h2M12 13h2" /></>),
  candles: svg(<><path d="M5 2v14" /><rect x="3" y="5" width="4" height="7" fill="currentColor" /><path d="M13 3v12" /><rect x="11" y="6" width="4" height="5" fill="currentColor" /></>),
  hollow: svg(<><path d="M5 2v3M5 12v4" /><rect x="3" y="5" width="4" height="7" /><path d="M13 3v3M13 11v4" /><rect x="11" y="6" width="4" height="5" /></>),
  line: svg(<path d="M2 13l4-5 3 3 4-6 3 3" />),
  line_markers: svg(<><path d="M2 13l4-5 3 3 4-6 3 3" /><circle cx="6" cy="8" r="1.3" fill="currentColor" /><circle cx="9" cy="11" r="1.3" fill="currentColor" /><circle cx="13" cy="5" r="1.3" fill="currentColor" /></>),
  step: svg(<path d="M2 13h3V8h4v3h3V5h4" />),
  area: svg(<><path d="M2 13l4-5 3 3 4-6 3 3v8H2z" fill="currentColor" fillOpacity="0.25" /><path d="M2 13l4-5 3 3 4-6 3 3" /></>),
  hlc_area: svg(<><path d="M2 9l4-4 4 2 6-4" /><path d="M2 14l4-3 4 2 6-4" /><path d="M2 9l4-4 4 2 6-4v6l-6 4-4-2-4 3z" fill="currentColor" fillOpacity="0.2" stroke="none" /></>),
  baseline: svg(<><path d="M2 9h14" strokeDasharray="1.5 1.5" /><path d="M2 12l3-5 3 2 3-5 2 6 3-2" /></>),
  columns: svg(<><rect x="2.5" y="9" width="2.5" height="7" /><rect x="7.5" y="5" width="2.5" height="11" /><rect x="12.5" y="7" width="2.5" height="9" /></>),
  high_low: svg(<><rect x="3" y="4" width="3" height="9" /><rect x="11" y="6" width="3" height="8" /></>),
  heikin_ashi: svg(<><path d="M5 2v14" /><rect x="3" y="5" width="4" height="7" /><path d="M13 3v12" /><rect x="11" y="5" width="4" height="7" fill="currentColor" /></>),
};

export const CHART_TYPES: { id: ChartType; label: string }[][] = [
  [{ id: 'bars', label: 'Bars' }, { id: 'candles', label: 'Candles' }, { id: 'hollow', label: 'Hollow candles' }],
  [{ id: 'line', label: 'Line' }, { id: 'line_markers', label: 'Line with markers' }, { id: 'step', label: 'Step line' }],
  [{ id: 'area', label: 'Area' }, { id: 'hlc_area', label: 'HLC area' }, { id: 'baseline', label: 'Baseline' }],
  [{ id: 'columns', label: 'Columns' }, { id: 'high_low', label: 'High-low' }],
  [{ id: 'heikin_ashi', label: 'Heikin Ashi' }],
];
const LABELS = Object.fromEntries(CHART_TYPES.flat().map((t) => [t.id, t.label])) as Record<ChartType, string>;

/** Types drawn by the CHART_TYPE indicator over transparent candles. */
export const CUSTOM_DRAWN: ReadonlySet<ChartType> = new Set(['line_markers', 'step', 'hlc_area', 'baseline', 'columns', 'high_low']);

// ─── Remembered choice (per browser) ─────────────────────────────────────────
const STORAGE_KEY = 'technical-chart-type';
export function loadChartType(): ChartType {
  try {
    const saved = localStorage.getItem(STORAGE_KEY) as ChartType | null;
    if (saved && saved in LABELS) return saved;
  } catch { /* storage blocked: use the default */ }
  return 'candles';
}
export function saveChartType(type: ChartType) {
  try { localStorage.setItem(STORAGE_KEY, type); } catch { /* not remembered, still applied */ }
}

// ─── Candle-pane styles per type ─────────────────────────────────────────────
const solidBar = {
  upColor: UP, downColor: DOWN, noChangeColor: FLAT,
  upBorderColor: UP, downBorderColor: DOWN, noChangeBorderColor: FLAT,
  upWickColor: UP, downWickColor: DOWN, noChangeWickColor: FLAT,
};
const hiddenBar = Object.fromEntries(Object.keys(solidBar).map((k) => [k, TRANSPARENT])) as typeof solidBar;
const noPoint = { show: false };

/** The `candle` part of the chart styles for a chart type. */
export function candleStyles(type: ChartType) {
  switch (type) {
    case 'bars': return { type: 'ohlc' as const, bar: solidBar };
    case 'hollow': return { type: 'candle_up_stroke' as const, bar: solidBar };
    case 'line':
      return { type: 'area' as const, area: { lineColor: LINE, lineSize: 2, value: 'close', backgroundColor: TRANSPARENT, point: noPoint } };
    case 'area':
      return {
        type: 'area' as const,
        area: {
          lineColor: LINE, lineSize: 2, value: 'close', point: noPoint,
          backgroundColor: [{ offset: 0, color: 'rgba(59,130,246,0.02)' }, { offset: 1, color: 'rgba(59,130,246,0.28)' }],
        },
      };
    default:
      return { type: 'candle_solid' as const, bar: CUSTOM_DRAWN.has(type) ? hiddenBar : solidBar };
  }
}

/** Heikin Ashi bars from ordinary OHLC bars (volume / turnover unchanged). */
export function toHeikinAshi(bars: KLineData[]): KLineData[] {
  const out: KLineData[] = [];
  for (const b of bars) {
    const close = (b.open + b.high + b.low + b.close) / 4;
    const prev = out[out.length - 1];
    const open = prev ? (prev.open + prev.close) / 2 : (b.open + b.close) / 2;
    out.push({ ...b, open, close, high: Math.max(b.high, open, close), low: Math.min(b.low, open, close) });
  }
  return out;
}

// ─── CHART_TYPE indicator: draws the custom types ────────────────────────────
const alpha = (hex: string, a: number) => {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
};

registerIndicator<unknown, unknown, { type: ChartType }>({
  name: 'CHART_TYPE',
  shortName: '',
  figures: [],
  calc: (list) => list.map(() => ({})),
  // No legend line on the price pane; the menu button already says which type is shown.
  createTooltipDataSource: () => ({ name: '', calcParamsText: '', features: [], legends: [] }),
  draw: ({ ctx, chart, indicator, bounding, xAxis, yAxis }) => {
    const type = indicator.extendData?.type;
    if (!type || !CUSTOM_DRAWN.has(type)) return true;
    const data = chart.getDataList();
    const { from, to } = chart.getVisibleRange();
    // One bar of overlap on each side so lines run off the edges instead of stopping short.
    const start = Math.max(0, from - 1);
    const end = Math.min(data.length, to + 1);
    if (end - start < 1) return true;
    const { gapBar, halfGapBar } = chart.getBarSpace();
    const x = (i: number) => xAxis.convertToPixel(i);
    const y = (v: number) => yAxis.convertToPixel(v);
    const idx = Array.from({ length: end - start }, (_, k) => start + k);

    const strokePath = (points: [number, number][], color: string, width = 2) => {
      ctx.beginPath();
      points.forEach(([px, py], k) => (k ? ctx.lineTo(px, py) : ctx.moveTo(px, py)));
      ctx.strokeStyle = color;
      ctx.lineWidth = width;
      ctx.lineJoin = 'round';
      ctx.stroke();
    };
    const closes = idx.map((i) => [x(i), y(data[i].close)] as [number, number]);

    ctx.save();
    switch (type) {
      case 'line_markers': {
        strokePath(closes, LINE);
        ctx.fillStyle = LINE;
        const r = Math.max(1.5, Math.min(3.5, halfGapBar / 2));
        for (const [px, py] of closes) {
          ctx.beginPath();
          ctx.arc(px, py, r, 0, Math.PI * 2);
          ctx.fill();
        }
        break;
      }
      case 'step': {
        const pts: [number, number][] = [];
        closes.forEach(([px, py], k) => {
          if (k) pts.push([px, closes[k - 1][1]]);
          pts.push([px, py]);
        });
        strokePath(pts, LINE);
        break;
      }
      case 'hlc_area': {
        const highs = idx.map((i) => [x(i), y(data[i].high)] as [number, number]);
        const lows = idx.map((i) => [x(i), y(data[i].low)] as [number, number]);
        const band = (top: [number, number][], bottom: [number, number][], color: string) => {
          ctx.beginPath();
          top.forEach(([px, py], k) => (k ? ctx.lineTo(px, py) : ctx.moveTo(px, py)));
          [...bottom].reverse().forEach(([px, py]) => ctx.lineTo(px, py));
          ctx.closePath();
          ctx.fillStyle = color;
          ctx.fill();
        };
        band(highs, closes, alpha(UP, 0.15));
        band(closes, lows, alpha(DOWN, 0.15));
        strokePath(highs, UP, 1);
        strokePath(lows, DOWN, 1);
        strokePath(closes, LINE, 1.5);
        break;
      }
      case 'baseline': {
        // Base level = close of the first bar on screen, like a "since the left edge" view.
        const baseY = y(data[Math.max(0, from)].close);
        const fillSide = (top: number, height: number, color: string) => {
          ctx.save();
          ctx.beginPath();
          ctx.rect(0, top, bounding.width, height);
          ctx.clip();
          ctx.beginPath();
          closes.forEach(([px, py], k) => (k ? ctx.lineTo(px, py) : ctx.moveTo(px, py)));
          ctx.lineTo(closes[closes.length - 1][0], baseY);
          ctx.lineTo(closes[0][0], baseY);
          ctx.closePath();
          ctx.fillStyle = alpha(color, 0.18);
          ctx.fill();
          strokePath(closes, color);
          ctx.restore();
        };
        fillSide(0, baseY, UP);
        fillSide(baseY, bounding.height - baseY, DOWN);
        ctx.setLineDash([4, 4]);
        strokePath([[0, baseY], [bounding.width, baseY]], FLAT, 1);
        ctx.setLineDash([]);
        break;
      }
      case 'columns': {
        const bottom = bounding.height;
        for (const i of idx) {
          const prev = data[i - 1]?.close ?? data[i].open;
          const top = y(data[i].close);
          ctx.fillStyle = alpha(data[i].close >= prev ? UP : DOWN, 0.6);
          ctx.fillRect(x(i) - halfGapBar, top, Math.max(1, gapBar), bottom - top);
        }
        break;
      }
      case 'high_low': {
        ctx.fillStyle = alpha(LINE, 0.65);
        for (const i of idx) {
          const top = y(data[i].high);
          ctx.fillRect(x(i) - halfGapBar, top, Math.max(1, gapBar), Math.max(1, y(data[i].low) - top));
        }
        break;
      }
    }
    ctx.restore();
    return true;
  },
});

// ─── Menu ────────────────────────────────────────────────────────────────────
export function ChartTypeMenu({ value, onChange }: { value: ChartType; onChange: (type: ChartType) => void }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (event: MouseEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  return (
    <div ref={rootRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        title={`Chart type: ${LABELS[value]}`}
        className={`flex h-9 items-center gap-2 rounded-lg border px-3 text-[13px] font-medium transition-colors ${open ? 'border-accent/60 bg-accent/10 text-accent-light' : 'border-bg-border text-text-primary hover:bg-blue-500/10'}`}
      >
        {ICONS[value]}
        <span className="hidden sm:inline">{LABELS[value]}</span>
        <ChevronDown size={13} className="text-text-muted" />
      </button>
      {open && (
        <div role="menu" className="absolute left-0 top-11 z-30 w-48 rounded-lg border border-bg-border bg-bg-card py-1 shadow-xl">
          {CHART_TYPES.map((group, g) => (
            <div key={g} className={g ? 'mt-1 border-t border-bg-border pt-1' : ''}>
              {group.map((t) => (
                <button
                  key={t.id}
                  type="button"
                  role="menuitemradio"
                  aria-checked={t.id === value}
                  onClick={() => { onChange(t.id); setOpen(false); }}
                  className={`flex w-full items-center gap-2.5 px-3 py-1.5 text-left text-xs transition-colors ${t.id === value ? 'bg-accent text-white' : 'text-text-primary hover:bg-blue-500/10'}`}
                >
                  {ICONS[t.id]}
                  {t.label}
                </button>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
