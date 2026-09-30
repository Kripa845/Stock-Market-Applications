import { useEffect, useMemo, useRef, useState } from 'react';
import {
  dispose, init, registerIndicator,
  type Chart, type KLineData,
} from 'klinecharts';

// Same shape as KlinePriceChart, so <TradingChart prices={...} symbol={...} /> is a drop-in swap.
interface ChartPrice {
  date: string;                       // "YYYY-MM-DD"
  open: string | number;
  high: string | number;
  low: string | number;
  close: string | number;
  volume: number;
  turnover?: string | number | null;
}
// One row of intraday data. `time` is an ISO string (with timezone) or epoch milliseconds.
export interface MinuteBar {
  time: string | number;
  open: string | number; high: string | number; low: string | number; close: string | number;
  volume: number;
}
interface Props {
  prices: ChartPrice[];               // daily bars; pass as many days as you have
  symbol: string;
  anomalyDates?: string[];
  // Optional. Returns 1-minute bars for the last `days` days. Every intraday interval is built from
  // these, so the backend only needs one endpoint. Without it, intraday intervals are disabled.
  fetchMinuteBars?: (days: number) => Promise<MinuteBar[]>;
}

// â”€â”€â”€ Custom indicators (module level, registered once) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// Same two as your KlinePriceChart, kept so nothing you already show is lost.
registerIndicator({
  name: 'DAILY_VWAP', shortName: 'VWAP', series: 'price',
  figures: [{ key: 'vwap', title: 'VWAP: ', type: 'line' }],
  calc: (list) => list.map((d) => ({ vwap: d.volume && d.turnover ? d.turnover / d.volume : d.close })),
});

registerIndicator({
  name: 'VOL_ANOMALY', shortName: 'VOL',
  figures: [{
    key: 'volume', title: 'VOL: ', type: 'bar', baseValue: 0,
    styles: (data: any) => {
      if (data.current?.indicatorData?.anomaly) return { color: '#d946ef' };
      const k = data.current?.kLineData;
      return { color: k && k.close >= k.open ? '#22C55E' : '#EF4444' };
    },
  }],
  calc: (list, ind: any) => {
    const flagged: string[] = ind.extendData ?? [];
    return list.map((d) => ({
      volume: d.volume ?? 0,
      anomaly: flagged.includes(new Date(d.timestamp).toISOString().slice(0, 10)),
    }));
  },
});

// Approximation of a "buy sell pressure" pane: 14-bar share of up-volume vs down-volume, 0-100.
// Replace calc() with your real formula when you have it.
registerIndicator({
  name: 'BSP', shortName: 'Buy/Sell pressure', calcParams: [14],
  figures: [
    { key: 'buy', title: 'Buy: ', type: 'line' },
    { key: 'sell', title: 'Sell: ', type: 'line' },
  ],
  calc: (list, ind: any) => {
    const n: number = ind.calcParams?.[0] ?? 14;
    return list.map((_, i) => {
      if (i < n - 1) return {};
      let up = 0, down = 0;
      for (let j = i - n + 1; j <= i; j++) {
        const x = (list[j].close - list[j].open) * (list[j].volume ?? 0);
        if (x > 0) up += x; else down -= x;
      }
      const buy = up + down ? (up / (up + down)) * 100 : 50;
      return { buy, sell: 100 - buy };
    });
  },
});

// â”€â”€â”€ Menu config â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
type Ind = { name: string; label: string; main: boolean; params?: number[] };
const INDICATORS: Ind[] = [
  { name: 'MA',         label: 'Moving Average',    main: true, params: [5, 10, 30, 60] },
  { name: 'EMA',        label: 'Exponential MA',    main: true },
  { name: 'BOLL',       label: 'Bollinger Bands',   main: true },
  { name: 'DAILY_VWAP', label: 'VWAP (daily)',      main: true },
  { name: 'VOL_ANOMALY',label: 'Volume',            main: false },
  { name: 'MACD',       label: 'MACD',              main: false },
  { name: 'RSI',        label: 'RSI',               main: false },
  { name: 'BSP',        label: 'Buy/Sell pressure', main: false },
];
const DEFAULT_ON = ['MA', 'DAILY_VWAP', 'VOL_ANOMALY'];

const TOOLS = [
  { id: 'cursor', icon: 'âœ›', title: 'Cursor',            overlay: null },
  { id: 'seg',    icon: 'â•±', title: 'Trend line',        overlay: 'segment' },
  { id: 'ray',    icon: 'â†—', title: 'Ray',               overlay: 'rayLine' },
  { id: 'hor',    icon: 'â€•', title: 'Horizontal line',   overlay: 'horizontalStraightLine' },
  { id: 'chan',   icon: 'â–¤', title: 'Parallel channel',  overlay: 'parallelStraightLine' },
  { id: 'fib',    icon: 'â‰¡', title: 'Fib retracement',   overlay: 'fibonacciLine' },
  { id: 'pchan',  icon: 'â‡•', title: 'Price channel',     overlay: 'priceChannelLine' },
  { id: 'clear',  icon: 'ðŸ—‘', title: 'Remove drawings',   overlay: null },
] as const;

type Interval = '1m' | '3m' | '5m' | '15m' | '30m' | '1h' | '2h' | '1D' | '1W' | '1M';
type Period = { span: number; type: 'minute' | 'hour' | 'day' | 'week' | 'month' };
const INTERVALS: { id: Interval; group: 'Minutes' | 'Hours' | 'Days'; minutes?: number; period: Period }[] = [
  { id: '1m',  group: 'Minutes', minutes: 1,   period: { span: 1,  type: 'minute' } },
  { id: '3m',  group: 'Minutes', minutes: 3,   period: { span: 3,  type: 'minute' } },
  { id: '5m',  group: 'Minutes', minutes: 5,   period: { span: 5,  type: 'minute' } },
  { id: '15m', group: 'Minutes', minutes: 15,  period: { span: 15, type: 'minute' } },
  { id: '30m', group: 'Minutes', minutes: 30,  period: { span: 30, type: 'minute' } },
  { id: '1h',  group: 'Hours',   minutes: 60,  period: { span: 1,  type: 'hour' } },
  { id: '2h',  group: 'Hours',   minutes: 120, period: { span: 2,  type: 'hour' } },
  { id: '1D',  group: 'Days',    period: { span: 1, type: 'day' } },
  { id: '1W',  group: 'Days',    period: { span: 1, type: 'week' } },
  { id: '1M',  group: 'Days',    period: { span: 1, type: 'month' } },
];
// Nepal Standard Time is UTC+5:45. Intraday buckets are aligned to local time so a 1h bar
// starts at 11:00, 12:00 ... and not at 05:15 UTC.
const NPT_OFFSET_MS = 345 * 60_000;
const NPT_SESSION_OPEN_MS = 11 * 60 * 60_000;
const MAX_INTRADAY_DAYS = 60;
const RANGES = [['1M', 30], ['3M', 90], ['6M', 180], ['YTD', -1], ['1Y', 365], ['All', 1e9]] as const;

// â”€â”€â”€ Helpers â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
function toBars(prices: ChartPrice[]): KLineData[] {
  return prices.map((p) => {
    const [y, m, d] = p.date.split('-').map(Number);
    return {
      timestamp: Date.UTC(y, m - 1, d),
      open: +p.open, high: +p.high, low: +p.low, close: +p.close,
      volume: p.volume, turnover: Number(p.turnover ?? 0),
    };
  }).sort((a, b) => a.timestamp - b.timestamp);
}

function toMinuteBars(rows: MinuteBar[]): KLineData[] {
  return rows.map((r) => {
    const close = +r.close, volume = r.volume ?? 0;
    return {
      timestamp: typeof r.time === 'number' ? r.time : Date.parse(r.time),
      open: +r.open, high: +r.high, low: +r.low, close, volume,
      turnover: close * volume,        // approximation, so DAILY_VWAP still draws on intraday bars
    };
  }).filter((b) => Number.isFinite(b.timestamp)).sort((a, b) => a.timestamp - b.timestamp);
}

function aggregateIntraday(bars: KLineData[], minutes: number): KLineData[] {
  if (minutes <= 1) return bars;
  const size = minutes * 60_000;
  const groups = new Map<number, KLineData>();
  for (const b of bars) {
    const bucket = Math.floor((b.timestamp + NPT_OFFSET_MS - NPT_SESSION_OPEN_MS) / size);
    const g = groups.get(bucket);
    if (!g) groups.set(bucket, { ...b, timestamp: bucket * size + NPT_SESSION_OPEN_MS - NPT_OFFSET_MS });
    else {
      g.high = Math.max(g.high, b.high); g.low = Math.min(g.low, b.low);
      g.close = b.close; g.volume = (g.volume ?? 0) + (b.volume ?? 0);
      g.turnover = (g.turnover ?? 0) + (b.turnover ?? 0);
    }
  }
  return [...groups.values()];
}

function aggregate(bars: KLineData[], mode: '1D' | '1W' | '1M'): KLineData[] {
  if (mode === '1D') return bars;
  const key = (t: number) => {
    const d = new Date(t);
    return mode === '1M' ? d.getUTCFullYear() * 12 + d.getUTCMonth() : Math.floor((t / 864e5 + 4) / 7);
  };
  const groups = new Map<number, KLineData>();
  for (const b of bars) {
    const k = key(b.timestamp), g = groups.get(k);
    if (!g) groups.set(k, { ...b });
    else {
      g.high = Math.max(g.high, b.high); g.low = Math.min(g.low, b.low);
      g.close = b.close; g.volume = (g.volume ?? 0) + (b.volume ?? 0);
      g.turnover = (g.turnover ?? 0) + (b.turnover ?? 0);
    }
  }
  return [...groups.values()];
}

const themeColors = (dark: boolean) => dark
  ? { grid: '#2a2e39', axis: '#3a3f4b', text: '#b2b5be', tipBg: '#1e222d', tipBorder: '#2a2e39' }
  : { grid: '#E5E7EB', axis: '#CBD5E1', text: '#64748B', tipBg: '#FFFFFF', tipBorder: '#E2E8F0' };

const isDarkTheme = () => document.documentElement.dataset.theme === 'dark';

function buildStyles(dark: boolean) {
  const c = themeColors(dark);
  const axis = { axisLine: { color: c.axis }, tickLine: { color: c.axis }, tickText: { color: c.text } };
  return {
    grid: {
      horizontal: { color: c.grid, style: 'dashed' as const, dashedValue: [3, 3] },
      vertical:   { color: c.grid, style: 'dashed' as const, dashedValue: [3, 3] },
    },
    candle: {
      bar: {
        upColor: '#22C55E', downColor: '#EF4444', noChangeColor: '#64748B',
        upBorderColor: '#22C55E', downBorderColor: '#EF4444', noChangeBorderColor: '#64748B',
        upWickColor: '#22C55E', downWickColor: '#EF4444', noChangeWickColor: '#64748B',
      },
      tooltip: {
        showRule: 'always' as const, showType: 'standard' as const,
        rect: { position: 'fixed' as const, color: c.tipBg, borderColor: c.tipBorder },
        title: { color: c.text }, legend: { color: c.text },
      },
    },
    indicator: {
      lines: [
        { color: '#F59E0B', size: 1.5 }, { color: '#A855F7', size: 1.5 },
        { color: '#3B82F6', size: 1.5 }, { color: '#EC4899', size: 1.5 },
      ],
      bars: [{ upColor: '#22C55E', downColor: '#EF4444', noChangeColor: '#94A3B8' }],
    },
    xAxis: axis, yAxis: axis,
    separator: { color: c.axis },
  };
}

// â”€â”€â”€ Component â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
export default function TradingChart({ prices, symbol, anomalyDates, fetchMinuteBars }: Props) {
  const hostRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<Chart | null>(null);
  const paneIds = useRef<Record<string, string>>({});   // indicator name -> pane id
  const anomalyKey = (anomalyDates ?? []).join(',');

  const [interval, setIntervalMode] = useState<Interval>('1D');
  const [range, setRange] = useState<(typeof RANGES)[number][0]>('All');
  const [tool, setTool] = useState<string>('cursor');
  const [menuOpen, setMenuOpen] = useState(false);
  const [active, setActive] = useState<string[]>(DEFAULT_ON);

  const [ivOpen, setIvOpen] = useState(false);
  const [minuteBars, setMinuteBars] = useState<KLineData[]>([]);
  const [loadingMin, setLoadingMin] = useState(false);
  const fetchRef = useRef(fetchMinuteBars);
  fetchRef.current = fetchMinuteBars;
  const activeIndicatorsRef = useRef(active);
  activeIndicatorsRef.current = active;

  const cfg = INTERVALS.find((i) => i.id === interval)!;
  const intraday = cfg.group !== 'Days';
  const rangeSpec = RANGES.find((r) => r[0] === range)![1];
  const rangeDays = rangeSpec === -1 ? 365 : rangeSpec;

  // Intraday: fetch 1-minute bars whenever the interval group, range or symbol changes.
  useEffect(() => {
    if (!intraday || !fetchRef.current) { setMinuteBars([]); return; }
    let cancelled = false;
    setLoadingMin(true);
    fetchRef.current(Math.min(rangeDays, MAX_INTRADAY_DAYS))
      .then((rows) => { if (!cancelled) setMinuteBars(toMinuteBars(rows)); })
      .catch(() => { if (!cancelled) setMinuteBars([]); })
      .finally(() => { if (!cancelled) setLoadingMin(false); });
    return () => { cancelled = true; };
  }, [intraday, rangeDays, symbol]);

  const bars = useMemo(() => {
    if (intraday) return aggregateIntraday(minuteBars, cfg.minutes!);
    const all = toBars(prices);
    if (!all.length) return all;
    const last = all[all.length - 1].timestamp;
    const from = rangeSpec === -1 ? Date.UTC(new Date(last).getUTCFullYear(), 0, 1) : last - rangeSpec * 864e5;
    return aggregate(all.filter((b) => b.timestamp >= from), interval as '1D' | '1W' | '1M');
  }, [prices, minuteBars, intraday, cfg, interval, rangeSpec]);

  const status = intraday
    ? !fetchMinuteBars ? 'Intraday data is not connected yet'
      : loadingMin ? 'Loading intraday data...'
      : bars.length === 0 ? 'No intraday data for this range' : ''
    : '';

  // Create the chart once per symbol.
  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const chart = init(host, { locale: 'en-US', timezone: 'Asia/Kathmandu', styles: buildStyles(isDarkTheme()) });
    if (!chart) return;
    chartRef.current = chart;
    paneIds.current = {};
    chart.setSymbol({ ticker: symbol });
    chart.setPeriod({ span: 1, type: 'day' });

    for (const name of activeIndicatorsRef.current) {
      const ind = INDICATORS.find((i) => i.name === name)!;
      const id = chart.createIndicator(
        { name, paneId: ind.main ? 'candle_pane' : undefined, calcParams: ind.params, extendData: name === 'VOL_ANOMALY' ? anomalyKey.split(',').filter(Boolean) : undefined } as any,
        ind.main,
      );
      paneIds.current[name] = ind.main ? 'candle_pane' : (id as string);
    }

    // Follow the app's light/dark switch (html[data-theme]).
    const obs = new MutationObserver(() => chart.setStyles(buildStyles(isDarkTheme())));
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });

    return () => { obs.disconnect(); dispose(host); chartRef.current = null; };
  }, [symbol]);

  // The Volume checkbox is the source of truth for the separate volume pane.
  // Remove by indicator id so a stale pane id cannot leave volume visible.
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    const volume = chart.getIndicators({ name: 'VOL_ANOMALY' });
    if (active.includes('VOL_ANOMALY')) {
      if (volume.length === 0) {
        const indicator = INDICATORS.find((item) => item.name === 'VOL_ANOMALY')!;
        chart.createIndicator({
          name: indicator.name,
          calcParams: indicator.params,
          extendData: anomalyKey.split(',').filter(Boolean),
        } as any, false);
      } else {
        volume.slice(1).forEach((indicator) => chart.removeIndicator({ id: indicator.id }));
      }
      const paneId = chart.getIndicators({ name: 'VOL_ANOMALY' })[0]?.paneId;
      if (paneId) paneIds.current.VOL_ANOMALY = paneId;
    } else {
      volume.forEach((indicator) => chart.removeIndicator({ id: indicator.id }));
      delete paneIds.current.VOL_ANOMALY;
    }
  }, [active, symbol]);

  // Keep custom indicator metadata in sync without recreating the chart.
  useEffect(() => {
    const chart = chartRef.current;
    const paneId = paneIds.current.VOL_ANOMALY;
    if (chart && paneId && activeIndicatorsRef.current.includes('VOL_ANOMALY')) {
      chart.overrideIndicator({
        name: 'VOL_ANOMALY',
        paneId,
        extendData: anomalyKey.split(',').filter(Boolean),
      } as any);
    }
  }, [anomalyKey]);

  // Reload data whenever range / interval / prices change.
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    chart.setPeriod(cfg.period);       // makes the x-axis show times (11:15) instead of dates
    chart.setDataLoader({ getBars: ({ callback }) => callback(bars) });
    chart.resetData();
  }, [bars, cfg, symbol, anomalyKey]);

  const toggleIndicator = (ind: Ind, on: boolean) => {
    if (ind.name === 'VOL_ANOMALY') {
      setActive((a) => (on
        ? a.includes(ind.name) ? a : [...a, ind.name]
        : a.filter((n) => n !== ind.name)));
      return;
    }

    const chart = chartRef.current;
    if (!chart) return;
    if (on) {
      const id = chart.createIndicator(
        {
          name: ind.name,
          paneId: ind.main ? 'candle_pane' : undefined,
          calcParams: ind.params,
          extendData: ind.name === 'VOL_ANOMALY' ? anomalyKey.split(',').filter(Boolean) : undefined,
        } as any,
        ind.main,
      );
      paneIds.current[ind.name] = ind.main ? 'candle_pane' : (id as string);
    } else {
      chart.removeIndicator({ name: ind.name, paneId: paneIds.current[ind.name] } as any);
      delete paneIds.current[ind.name];
    }
    setActive((a) => (on
      ? a.includes(ind.name) ? a : [...a, ind.name]
      : a.filter((n) => n !== ind.name)));
  };

  const pickTool = (t: (typeof TOOLS)[number]) => {
    const chart = chartRef.current;
    if (!chart) return;
    if (t.id === 'clear') { chart.removeOverlay(); setTool('cursor'); return; }
    setTool(t.id);
    if (t.overlay) chart.createOverlay({ name: t.overlay, onDrawEnd: () => { setTool('cursor'); return false; } } as any);
  };

  const btn = (on: boolean) =>
    `px-2.5 py-1 rounded text-xs font-medium transition-all ${on ? 'bg-accent text-white' : 'text-text-secondary hover:text-text-primary hover:bg-bg-elevated'}`;

  return (
    <div className="flex h-full w-full flex-col">
      {/* Top bar: symbol, indicators, interval */}
      <div className="relative flex flex-wrap items-center gap-1 border-b border-bg-border px-2 py-1">
        <span className="pr-2 text-sm font-bold text-text-primary">{symbol}</span>
        <button className={btn(menuOpen)} onClick={() => setMenuOpen((o) => !o)}>Indicators</button>
        <span className="mx-1 h-4 w-px bg-bg-border" />
        <div className="relative">
          <button className={btn(ivOpen)} onClick={() => setIvOpen((o) => !o)}>{interval} â–¾</button>
          {ivOpen && (
            <div className="absolute left-0 top-8 z-20 min-w-[130px] rounded-lg border border-bg-border bg-bg-card p-1 shadow-lg">
              {(['Minutes', 'Hours', 'Days'] as const).map((g) => (
                <div key={g}>
                  <p className="px-2 pb-0.5 pt-1.5 text-[11px] font-semibold text-text-secondary">{g}</p>
                  {INTERVALS.filter((i) => i.group === g).map((i) => {
                    const disabled = i.group !== 'Days' && !fetchMinuteBars;
                    return (
                      <button key={i.id} disabled={disabled}
                        title={disabled ? 'Needs an intraday data source' : undefined}
                        onClick={() => { setIntervalMode(i.id); setIvOpen(false); }}
                        className={`block w-full rounded px-2 py-1 text-left text-xs ${interval === i.id ? 'bg-accent text-white' : 'text-text-primary hover:bg-bg-elevated'} disabled:cursor-not-allowed disabled:opacity-40`}>
                        {i.id}
                      </button>
                    );
                  })}
                </div>
              ))}
            </div>
          )}
        </div>
        {(['1D', '1W', '1M'] as const).map((i) => (
          <button key={i} className={btn(interval === i)} onClick={() => setIntervalMode(i)}>{i}</button>
        ))}

        {menuOpen && (
          <div className="absolute left-2 top-9 z-20 min-w-[210px] rounded-lg border border-bg-border bg-bg-card p-2 shadow-lg">
            {[true, false].map((main) => (
              <div key={String(main)}>
                <p className="px-2 pb-1 pt-1.5 text-[11px] font-semibold text-text-secondary">
                  {main ? 'On price chart' : 'In separate pane'}
                </p>
                {INDICATORS.filter((i) => i.main === main).map((ind) => (
                  <label key={ind.name} className="flex cursor-pointer items-center gap-2 rounded px-2 py-1 text-xs text-text-primary hover:bg-bg-elevated">
                    <input type="checkbox" checked={active.includes(ind.name)}
                      onChange={(e) => toggleIndicator(ind, e.target.checked)} />
                    {ind.label}
                  </label>
                ))}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Middle: left drawing toolbar + chart */}
      <div className="flex min-h-0 flex-1">
        <div className="flex flex-col gap-0.5 border-r border-bg-border p-1">
          {TOOLS.map((t) => (
            <button key={t.id} title={t.title} onClick={() => pickTool(t)}
              className={`h-8 w-8 rounded text-base ${tool === t.id ? 'bg-accent text-white' : 'text-text-secondary hover:bg-bg-elevated'}`}>
              {t.icon}
            </button>
          ))}
        </div>
        <div className="relative min-w-0 flex-1">
          <div ref={hostRef} className="h-full w-full" aria-label={`${symbol} candlestick chart`} />
          {status && (
            <div className="pointer-events-none absolute inset-0 flex items-center justify-center text-xs text-text-secondary">
              {status}
            </div>
          )}
        </div>
      </div>

      {/* Bottom bar: date ranges */}
      <div className="flex items-center gap-1 border-t border-bg-border px-2 py-1">
        {RANGES.map(([label]) => (
          <button key={label} className={btn(range === label)} onClick={() => setRange(label)}>{label}</button>
        ))}
      </div>
    </div>
  );
}

