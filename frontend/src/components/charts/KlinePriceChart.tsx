
import { useEffect, useMemo, useRef, useState } from 'react';
import {
  dispose, init,
  type Chart, type KLineData,
} from 'klinecharts';
import { paneOf } from './customIndicators';
import {
  CUSTOM_DRAWN, ChartTypeMenu, candleStyles, loadChartType, saveChartType, toHeikinAshi, type ChartType,
} from './chartTypes';
import RangeBar, { type AxisMode } from './RangeBar';
import DrawingToolbar from './DrawingToolbar';
import {
  defaultRange, rangeAvailable, rangeCalendarDays, rangeStart as rangeStartFor, type RangeId,
} from './chartRanges';
import IndicatorPicker, { PICKER_TOGGLE_ATTR, type ActiveIndicator } from './IndicatorPicker';
import { Camera, ChevronDown, LineChart, Loader2, Maximize, Minimize } from 'lucide-react';
import { ensureRegistered, toSeries, type RegistrySeries } from './registryIndicators';
import {
  marketIntelligenceApi, type IndicatorDef, type IndicatorParams, type IndicatorRegistry,
} from '../../api/marketIntelligence';

// Same shape as KlinePriceChart, so <TradingChart prices={...} symbol={...} /> is a drop-in swap.
interface ChartPrice {
  date: string;                       // "YYYY-MM-DD"
  open: string | number | null;       // null (index rows NEPSE did not publish) -> the bar is skipped, never drawn at 0
  high: string | number | null;
  low: string | number | null;
  close: string | number | null;
  volume: number | null;
  turnover?: string | number | null;
}
// A dotted horizontal line with its value tagged on the price axis (e.g. 52-week high / low).
export interface PriceLine {
  label: string;
  value: number | null;               // null -> not drawn
  color?: string;
  // false -> drawn only when the price axis already reaches it (the axis is not stretched to fit it).
  // Default true, e.g. 52-week high / low should always be visible.
  scale?: boolean;
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
  // Enables the indicator library (server-calculated, daily bars only).
  companyId?: number;
  // Optional reference lines, computed by the caller (the chart only draws them).
  priceLines?: PriceLine[];
  // Optional text under the latest-close label on the price axis, e.g. "+21.33 (+0.82%)".
  lastPriceNote?: string;
  // Optional extra controls for the top bar (e.g. the S & R toggle on Technical Charts).
  toolbarExtra?: React.ReactNode;
}

// ─── Menu config ──────────────────────────────────────────────────────────────
type Ind = { name: string; label: string; main: boolean; params?: number[] };
// Chart-native extras. Everything else comes from the server indicator library (see IndicatorPicker).
const INDICATORS: Ind[] = [
  { name: 'DAILY_VWAP', label: 'VWAP (daily, from turnover)', main: true },
  { name: 'VOL_ANOMALY',label: 'Volume (anomalies highlighted)', main: false },
  { name: 'BSP',        label: 'Buy/Sell pressure (approximation)', main: false },
];
const DEFAULT_ON = ['VOL_ANOMALY'];
// Library indicators shown on first load: EMA + Bollinger on the price, RSI and MACD below.
const DEFAULT_LIBRARY = ['ema', 'bollinger', 'rsi', 'macd'];
const MAX_PER_REQUEST = 20;
// Fixed heights keep the price pane readable when several lower panes are open.
const VOLUME_PANE_HEIGHT = 70;
const LIBRARY_PANE_HEIGHT = 90;

function sizePane(chart: Chart, paneId: string, height = VOLUME_PANE_HEIGHT) {
  if (paneId !== 'candle_pane') chart.setPaneOptions({ id: paneId, height });
}

// The registry is the same for every chart, so it is fetched once per page load.
let registryRequest: Promise<IndicatorRegistry> | null = null;
const loadRegistry = () => {
  registryRequest ??= marketIntelligenceApi.getIndicatorRegistry().catch((err) => {
    registryRequest = null;
    throw err;
  });
  return registryRequest;
};

const defaultParams = (def: IndicatorDef): IndicatorParams =>
  Object.fromEntries(def.params.map((p) => [p.name, p.default]));

const isoDay = (ts: number) => new Date(ts).toISOString().slice(0, 10);
let uidCounter = 0;
const newUid = () => `ind${++uidCounter}`;

type Interval = '1m' | '3m' | '5m' | '15m' | '30m' | '1h' | '2h' | '1D' | '1W' | '1M';
// Candle size, worded differently from the 1D / 5D / 1M *ranges* in the bottom bar so the two never look alike.
const INTERVAL_LABELS: Record<Interval, string> = {
  '1m': '1 min', '3m': '3 min', '5m': '5 min', '15m': '15 min', '30m': '30 min',
  '1h': '1 hour', '2h': '2 hours', '1D': 'Daily', '1W': 'Weekly', '1M': 'Monthly',
};
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
const MAX_INTRADAY_DAYS = 60;

// ─── Helpers ──────────────────────────────────────────────────────────────────
function toBars(prices: ChartPrice[]): KLineData[] {
  return prices.filter((p) => p.open != null && p.high != null && p.low != null && p.close != null).map((p) => {
    const [y, m, d] = p.date.split('-').map(Number);
    return {
      timestamp: Date.UTC(y, m - 1, d),
      open: +p.open!, high: +p.high!, low: +p.low!, close: +p.close!,
      volume: p.volume ?? undefined, turnover: Number(p.turnover ?? 0),
    };
  }).sort((a, b) => a.timestamp - b.timestamp);
}

const PRICE_LINE_GROUP = 'price-lines';
const PRICE_LINE_COLOR = '#94A3B8';
// Same look as the library's own last-price label, one size smaller.
const LAST_PRICE_NOTE_STYLE = {
  show: true, position: 'below_price' as const, updateInterval: 0,
  style: 'fill' as const, size: 11, family: 'Helvetica Neue', weight: 'normal', color: '#FFFFFF',
  paddingLeft: 4, paddingTop: 2, paddingRight: 4, paddingBottom: 2,
  borderStyle: 'solid' as const, borderSize: 0, borderColor: 'transparent', borderDashedValue: [2, 2], borderRadius: 2,
};

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
    const bucket = Math.floor((b.timestamp + NPT_OFFSET_MS) / size);
    const g = groups.get(bucket);
    if (!g) groups.set(bucket, { ...b, timestamp: bucket * size - NPT_OFFSET_MS });
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
  ? { grid: '#2E2654', axis: '#3A3166', text: '#A1A1C2', tipBg: '#1A1433', tipBorder: '#2E2654' }
  : { grid: '#E5E7EB', axis: '#CBD5E1', text: '#64748B', tipBg: '#FFFFFF', tipBorder: '#E2E8F0' };

const isDarkTheme = () => document.documentElement.dataset.theme === 'dark';

const LEGEND_FONT = 'IBM Plex Mono, SFMono-Regular, Consolas, monospace';
const UP = '#26a69a';
const DOWN = '#ef5350';
const legendNumber = (value: number) => value.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

// "O 181.69  H 182.36  L 181.31  C 182.05  +0.42 (+0.23%)" for the bar under the crosshair (else the latest).
function legendTemplate(dark: boolean) {
  const label = dark ? '#A1A1C2' : '#64748B';
  const value = dark ? '#E2E8F0' : '#0f172a';
  return ({ prev, current }: { prev: KLineData | null; current: KLineData | null }) => {
    if (!current) return [];
    const legends = (['open', 'high', 'low', 'close'] as const).map((key) => ({
      title: { text: `${key[0].toUpperCase()} `, color: label },
      value: { text: legendNumber(current[key]), color: value },
    }));
    if (prev?.close) {
      const change = current.close - prev.close;
      const color = change > 0 ? UP : change < 0 ? DOWN : label;
      const sign = change > 0 ? '+' : '';
      legends.push({
        title: { text: '', color },
        value: { text: `${sign}${legendNumber(change)} (${sign}${((change / prev.close) * 100).toFixed(2)}%)`, color },
      });
    }
    return legends;
  };
}

function buildStyles(dark: boolean, chartType: ChartType) {
  const c = themeColors(dark);
  const axis = { axisLine: { color: c.axis }, tickLine: { color: c.axis }, tickText: { color: c.text } };
  return {
    grid: {
      horizontal: { color: c.grid, style: 'dashed' as const, dashedValue: [3, 3] },
      vertical:   { color: c.grid, style: 'dashed' as const, dashedValue: [3, 3] },
    },
    candle: {
      // Bars / candles / line / area… (see chartTypes.tsx)
      ...candleStyles(chartType, dark),
      tooltip: {
        showRule: 'always' as const, showType: 'standard' as const,
        rect: { position: 'fixed' as const, color: c.tipBg, borderColor: c.tipBorder },
        title: {
          show: true, size: 14, weight: '600', family: 'Inter, system-ui, sans-serif',
          color: dark ? '#E2E8F0' : '#0f172a', template: '{ticker} · {period}',
          marginLeft: 12, marginTop: 10, marginRight: 8, marginBottom: 4,
        },
        legend: {
          size: 12, family: LEGEND_FONT, color: c.text,
          marginLeft: 12, marginTop: 4, marginRight: 4, marginBottom: 4,
          template: legendTemplate(dark),
        },
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

// ─── Component ────────────────────────────────────────────────────────────────
export default function TradingChart({ prices, symbol, anomalyDates, fetchMinuteBars, companyId, priceLines, lastPriceNote, toolbarExtra }: Props) {
  const hostRef = useRef<HTMLDivElement>(null);
  const rootRef = useRef<HTMLDivElement>(null);
  const [fullscreen, setFullscreen] = useState(false);
  const [axisMode, setAxisMode] = useState<AxisMode>('normal');
  const chartRef = useRef<Chart | null>(null);
  const paneIds = useRef<Record<string, string>>({});   // indicator name -> pane id
  const anomalyKey = (anomalyDates ?? []).join(',');

  const [interval, setIntervalMode] = useState<Interval>('1D');
  const [rangeChoice, setRange] = useState<RangeId | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);
  const [active, setActive] = useState<string[]>(DEFAULT_ON);
  const [chartType, setChartTypeState] = useState<ChartType>(loadChartType);
  const chartTypeRef = useRef(chartType);
  chartTypeRef.current = chartType;
  const setChartType = (type: ChartType) => { saveChartType(type); setChartTypeState(type); };

  const [ivOpen, setIvOpen] = useState(false);
  const [minuteBars, setMinuteBars] = useState<KLineData[]>([]);
  const [loadingMin, setLoadingMin] = useState(false);
  const fetchRef = useRef(fetchMinuteBars);
  fetchRef.current = fetchMinuteBars;
  const activeIndicatorsRef = useRef(active);
  activeIndicatorsRef.current = active;

  const cfg = INTERVALS.find((i) => i.id === interval)!;
  const intraday = cfg.group !== 'Days';
  // Ranges are measured against the real trading dates in `prices` (see chartRanges.ts).
  const dailyDates = useMemo(() => [...new Set(prices.map((p) => p.date))].sort(), [prices]);
  const range: RangeId = rangeChoice && rangeAvailable(dailyDates, rangeChoice) ? rangeChoice : defaultRange(dailyDates);
  const rangeFrom = rangeStartFor(dailyDates, range);
  const shownCount = rangeFrom ? dailyDates.filter((d) => d >= rangeFrom).length : 0;
  const rangeDays = Math.max(1, rangeCalendarDays(dailyDates, rangeFrom));

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
    const ohlc = (() => {
      if (intraday) return aggregateIntraday(minuteBars, cfg.minutes!);
      const all = toBars(prices);
      if (!all.length || !rangeFrom) return all;
      const from = Date.UTC(+rangeFrom.slice(0, 4), +rangeFrom.slice(5, 7) - 1, +rangeFrom.slice(8, 10));
      return aggregate(all.filter((b) => b.timestamp >= from), interval as '1D' | '1W' | '1M');
    })();
    // Heikin Ashi is computed after aggregation, from the candles actually shown.
    return chartType === 'heikin_ashi' ? toHeikinAshi(ohlc) : ohlc;
  }, [prices, minuteBars, intraday, cfg, interval, rangeFrom, chartType]);

  const status = intraday
    ? !fetchMinuteBars ? 'Intraday data is not connected yet'
      : loadingMin ? 'Loading intraday data...'
      : bars.length === 0 ? 'No timestamped trade data available for this range' : ''
    : '';

  // ─── Indicator library ────────────────────────────────────────────────────────
  const [registry, setRegistry] = useState<IndicatorRegistry | null>(null);
  const [registryError, setRegistryError] = useState('');
  const [library, setLibrary] = useState<ActiveIndicator[]>([]);
  const [seriesVersion, setSeriesVersion] = useState(0);
  const [loadingSeries, setLoadingSeries] = useState(false);
  const [chartGeneration, setChartGeneration] = useState(0);
  // Calculated series by request key, so removing and re-adding an indicator never refetches it.
  const seriesCache = useRef(new Map<string, RegistrySeries>());
  const errorCache = useRef(new Map<string, string>());
  // What is currently drawn: library uid -> chart indicator id + the series key it shows.
  const mounted = useRef(new Map<string, { chartId: string; key: string }>());
  const defs = useMemo(() => new Map((registry?.indicators ?? []).map((d) => [d.id, d])), [registry]);
  const libraryActive = interval === '1D';
  const rangeStart = interval === '1D' && bars.length ? isoDay(bars[0].timestamp) : '';

  useEffect(() => {
    let cancelled = false;
    loadRegistry()
      .then((r) => {
        if (cancelled) return;
        setRegistry(r);
        setLibrary((current) => current.length ? current : DEFAULT_LIBRARY
          .map((id) => r.indicators.find((d) => d.id === id))
          .filter((d): d is IndicatorDef => !!d)
          .map((d) => ({ uid: newUid(), id: d.id, params: defaultParams(d) })));
      })
      .catch(() => { if (!cancelled) setRegistryError('Unable to load the indicator list.'); });
    return () => { cancelled = true; };
  }, []);

  const keyFor = (a: ActiveIndicator) => {
    const def = defs.get(a.id);
    return [companyId, def?.scope === 'range' ? rangeStart : '', a.id, JSON.stringify(a.params)].join('|');
  };

  // Fetch whatever the active indicators need that is not cached yet.
  useEffect(() => {
    if (!companyId || !registry || !libraryActive) return;
    const missing = library.filter((a) => {
      if (a.hidden) return false;
      const key = keyFor(a);
      return !seriesCache.current.has(key) && !errorCache.current.has(key);
    });
    if (!missing.length) return;
    let cancelled = false;
    // Range-scoped indicators (anchored VWAP, volume profile) are computed for the visible range only;
    // everything else over the full history so the warm-up is never cut short.
    const groups = [
      { start: undefined, items: missing.filter((a) => defs.get(a.id)?.scope !== 'range') },
      { start: rangeStart || undefined, items: missing.filter((a) => defs.get(a.id)?.scope === 'range') },
    ].flatMap(({ start, items }) => Array.from(
      { length: Math.ceil(items.length / MAX_PER_REQUEST) },
      (_, i) => ({ start, items: items.slice(i * MAX_PER_REQUEST, (i + 1) * MAX_PER_REQUEST) }),
    ));
    setLoadingSeries(true);
    Promise.all(groups.map(({ start, items }) => marketIntelligenceApi
      .getIndicatorSeries(companyId, items.map((a) => ({ id: a.id, params: a.params })), { start_date: start })
      .then((response) => {
        response.results.forEach((result, i) => {
          const key = keyFor(items[i]);
          if (result.error) errorCache.current.set(key, result.error);
          else seriesCache.current.set(key, toSeries(response.dates, result));
        });
      })
      .catch((err) => {
        const detail = err?.response?.data?.detail;
        // Not cached, so a later change retries.
        if (!cancelled) setRegistryError(typeof detail === 'string' ? detail : 'Unable to load indicator values.');
      })))
      .finally(() => {
        if (cancelled) return;
        setLoadingSeries(false);
        setSeriesVersion((v) => v + 1);
      });
    return () => { cancelled = true; };
    // keyFor reads defs/rangeStart/companyId, which are all listed.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [companyId, registry, library, rangeStart, libraryActive, defs]);

  // Draw / replace / remove library indicators to match the active list.
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    const wanted = new Set(libraryActive ? library.filter((a) => !a.hidden).map((a) => a.uid) : []);
    for (const [uid, m] of mounted.current) {
      if (!wanted.has(uid)) {
        chart.removeIndicator({ id: m.chartId });
        mounted.current.delete(uid);
      }
    }
    if (!libraryActive) return;
    for (const a of library) {
      if (a.hidden) continue;
      const def = defs.get(a.id);
      const key = keyFor(a);
      const series = seriesCache.current.get(key);
      const current = mounted.current.get(a.uid);
      if (!def || !series || current?.key === key) continue;
      const paneId = def.display === 'overlay' ? 'candle_pane' : `pane_${a.uid}`;
      const chartId = `${a.uid}_${Date.now()}`;
      // Stack the new version into the same pane before removing the old one, so the pane keeps its place.
      chart.createIndicator({
        name: ensureRegistered(def), id: chartId, paneId,
        calcParams: def.params.map((p) => a.params[p.name]), extendData: series,
      } as any, true);
      if (current) chart.removeIndicator({ id: current.chartId });
      else sizePane(chart, paneId, LIBRARY_PANE_HEIGHT);
      mounted.current.set(a.uid, { chartId, key });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [seriesVersion, library, libraryActive, defs, chartGeneration, rangeStart, companyId]);

  const indicatorErrors = Object.fromEntries(
    library.map((a) => [a.uid, errorCache.current.get(keyFor(a)) ?? '']).filter(([, e]) => e),
  );

  // Create the chart once per symbol.
  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    const chart = init(host, { locale: 'en-US', timezone: 'Asia/Kathmandu', styles: buildStyles(isDarkTheme(), chartTypeRef.current) });
    if (!chart) return;
    chartRef.current = chart;
    paneIds.current = {};
    mounted.current = new Map();
    chart.setSymbol({ ticker: symbol });
    chart.setPeriod({ span: 1, type: 'day' });

    for (const name of activeIndicatorsRef.current) {
      const ind = INDICATORS.find((i) => i.name === name)!;
      const id = chart.createIndicator(
        { name, paneId: ind.main ? 'candle_pane' : undefined, calcParams: ind.params, extendData: name === 'VOL_ANOMALY' ? anomalyKey.split(',').filter(Boolean) : undefined } as any,
        ind.main,
      );
      paneIds.current[name] = paneOf(chart, id);
      sizePane(chart, paneIds.current[name]);
    }

    // Follow the app's light/dark switch (html[data-theme]).
    const obs = new MutationObserver(() => chart.setStyles(buildStyles(isDarkTheme(), chartTypeRef.current)));
    obs.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });

    setChartGeneration((g) => g + 1);   // redraw library indicators on the new chart

    return () => { obs.disconnect(); dispose(host); chartRef.current = null; };
  }, [symbol]);

  // Chart type: candle-pane styles, plus the CHART_TYPE overlay for the custom-drawn types.
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    chart.setStyles(buildStyles(isDarkTheme(), chartType));
    const drawn = chart.getIndicators({ name: 'CHART_TYPE' });
    if (CUSTOM_DRAWN.has(chartType)) {
      if (drawn.length === 0) {
        chart.createIndicator({ name: 'CHART_TYPE', paneId: 'candle_pane', extendData: { type: chartType } } as any, true);
      } else {
        chart.overrideIndicator({ name: 'CHART_TYPE', paneId: 'candle_pane', extendData: { type: chartType } } as any);
      }
    } else {
      drawn.forEach((indicator) => chart.removeIndicator({ id: indicator.id }));
    }
  }, [chartType, chartGeneration]);

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
      if (paneId) {
        paneIds.current.VOL_ANOMALY = paneId;
        sizePane(chart, paneId);
      }
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

  // Reference lines: a dotted line across the price pane plus its value on the price axis.
  const priceLinesKey = JSON.stringify(priceLines ?? []);
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;
    chart.removeOverlay({ groupId: PRICE_LINE_GROUP });
    const lines = (JSON.parse(priceLinesKey) as PriceLine[])
      .filter((line) => line.value != null && Number.isFinite(line.value));
    const values = lines.filter((line) => line.scale !== false).map((line) => line.value!);
    // Stretch the price axis so the lines stay on screen even when the visible candles do not reach them.
    // Only on the plain (Auto) axis: % and log axes keep the library's own range.
    chart.overrideYAxis({
      paneId: 'candle_pane',
      name: axisMode,
      createRange: ({ defaultRange }) => {
        if (!values.length || axisMode !== 'normal') return defaultRange;
        const low = Math.min(...values), high = Math.max(...values);
        if (low >= defaultRange.from && high <= defaultRange.to) return defaultRange;
        const pad = (Math.max(high, defaultRange.to) - Math.min(low, defaultRange.from)) * 0.03;
        const from = low < defaultRange.from ? low - pad : defaultRange.from;
        const to = high > defaultRange.to ? high + pad : defaultRange.to;
        const span = to - from;
        return {
          ...defaultRange, from, to, realFrom: from, realTo: to, displayFrom: from, displayTo: to,
          range: span, realRange: span, displayRange: span,
        };
      },
    });
    for (const line of lines) {
      const color = line.color ?? PRICE_LINE_COLOR;
      chart.createOverlay({
        name: 'simpleTag', groupId: PRICE_LINE_GROUP, lock: true,
        points: [{ value: line.value }], extendData: line.label,
        styles: {
          line: { style: 'dashed', dashedValue: [2, 3], color },
          text: { color: '#FFFFFF', backgroundColor: color, borderColor: color },
        },
      } as any);
    }
  }, [priceLinesKey, chartGeneration, axisMode]);

  // Fullscreen is entered on the chart's root element; Esc leaves it without our button.
  useEffect(() => {
    const onChange = () => {
      setFullscreen(document.fullscreenElement === rootRef.current);
      chartRef.current?.resize();
    };
    document.addEventListener('fullscreenchange', onChange);
    return () => document.removeEventListener('fullscreenchange', onChange);
  }, []);

  // Extra text under the latest-close label; the label is coloured against the previous close.
  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || !lastPriceNote) return;
    chart.setFormatter({ formatExtendText: () => lastPriceNote });
    chart.setStyles({
      candle: { priceMark: { last: { compareRule: 'previous_close', extendTexts: [LAST_PRICE_NOTE_STYLE] } } },
    });
  }, [lastPriceNote, chartGeneration]);

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
      paneIds.current[ind.name] = paneOf(chart, id);
      sizePane(chart, paneIds.current[ind.name]);
    } else {
      chart.removeIndicator({ name: ind.name, paneId: paneIds.current[ind.name] } as any);
      delete paneIds.current[ind.name];
    }
    setActive((a) => (on
      ? a.includes(ind.name) ? a : [...a, ind.name]
      : a.filter((n) => n !== ind.name)));
  };

  const segment = (on: boolean) =>
    `flex h-7 items-center gap-1 rounded-md px-3 text-[13px] font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
      on ? 'bg-bg-card text-accent-light shadow-sm' : 'text-text-secondary enabled:hover:text-text-primary'}`;
  const iconBtn = 'flex h-9 w-9 items-center justify-center rounded-lg text-text-secondary transition-colors hover:bg-blue-500/10 hover:text-text-primary';
  const shownIndicators = library.filter((a) => !a.hidden).length + active.filter((name) => name !== 'VOL_ANOMALY').length;

  const saveImage = () => {
    const chart = chartRef.current;
    if (!chart) return;
    const link = document.createElement('a');
    link.href = chart.getConvertPictureUrl(true, 'png', isDarkTheme() ? '#0A0718' : '#ffffff');
    link.download = `${symbol.replace(/\s+/g, '_')}_${INTERVAL_LABELS[interval].replace(/\s+/g, '')}_${new Date().toISOString().slice(0, 10)}.png`;
    link.click();
  };
  const toggleFullscreen = () => {
    if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
    else rootRef.current?.requestFullscreen?.().catch(() => {});
  };

  return (
    <div ref={rootRef} className="flex h-full w-full flex-col bg-bg-primary">
      {/* Top bar: chart type, interval, indicators, extras; image and fullscreen on the right */}
      <div className="relative flex min-h-[56px] flex-wrap items-center gap-2 border-b border-bg-border px-3 py-2">
        <ChartTypeMenu value={chartType} onChange={setChartType} />

        <div className="flex items-center rounded-lg bg-bg-elevated p-1" role="group" aria-label="Candle size">
          <div className="relative">
            <button
              type="button"
              className={segment(intraday || ivOpen)}
              onClick={() => setIvOpen((o) => !o)}
              disabled={!fetchMinuteBars}
              aria-haspopup="menu"
              aria-expanded={ivOpen}
              title={fetchMinuteBars ? 'Intraday candles (minutes / hours)' : 'Intraday candles need an intraday data source'}
            >
              {intraday ? INTERVAL_LABELS[interval] : 'Intraday'}
              <ChevronDown size={12} className="text-text-muted" />
            </button>
            {ivOpen && (
              <div role="menu" className="absolute left-0 top-9 z-30 min-w-[140px] rounded-lg border border-bg-border bg-bg-card p-1 shadow-xl">
                {(['Minutes', 'Hours'] as const).map((g) => (
                  <div key={g}>
                    <p className="px-2 pb-0.5 pt-1.5 text-[11px] font-semibold text-text-secondary">{g}</p>
                    {INTERVALS.filter((i) => i.group === g).map((i) => (
                      <button key={i.id} type="button" role="menuitem"
                        onClick={() => { setIntervalMode(i.id); setIvOpen(false); }}
                        className={`block w-full rounded px-2 py-1.5 text-left text-xs ${interval === i.id ? 'bg-accent/15 text-accent-light' : 'text-text-primary hover:bg-blue-500/10'}`}>
                        {INTERVAL_LABELS[i.id]}
                      </button>
                    ))}
                  </div>
                ))}
              </div>
            )}
          </div>
          {(['1D', '1W', '1M'] as const).map((i) => (
            <button key={i} type="button" className={segment(interval === i)} onClick={() => { setIntervalMode(i); setIvOpen(false); }}
              title={`Each candle = 1 ${i === '1D' ? 'day' : i === '1W' ? 'week' : 'month'}`}>
              {INTERVAL_LABELS[i]}
            </button>
          ))}
        </div>

        <span className="mx-0.5 hidden h-6 w-px bg-bg-border md:block" />

        <button {...{ [PICKER_TOGGLE_ATTR]: '' }} type="button" onClick={() => setMenuOpen((o) => !o)}
          aria-expanded={menuOpen} aria-haspopup="dialog"
          className={`flex h-9 items-center gap-2 rounded-lg border px-3 text-[13px] font-medium transition-colors ${
            menuOpen ? 'border-accent/60 bg-accent/10 text-accent-light' : 'border-bg-border text-text-primary hover:bg-blue-500/10'}`}>
          <LineChart size={15} />
          Indicators
          {shownIndicators > 0 && (
            <span className="rounded-md bg-accent/15 px-1.5 font-mono text-[11px] tabular-nums text-accent-light">{shownIndicators}</span>
          )}
          {loadingSeries && <Loader2 size={12} className="animate-spin text-text-muted" />}
        </button>

        {toolbarExtra}

        <div className="ml-auto flex items-center gap-1">
          <button type="button" onClick={saveImage} className={iconBtn} title="Save chart as image (PNG)" aria-label="Save chart as image">
            <Camera size={17} />
          </button>
          <button type="button" onClick={toggleFullscreen} className={iconBtn}
            title={fullscreen ? 'Exit full screen' : 'Full screen'} aria-label={fullscreen ? 'Exit full screen' : 'Full screen'}>
            {fullscreen ? <Minimize size={17} /> : <Maximize size={17} />}
          </button>
        </div>

        {menuOpen && (
          <IndicatorPicker
            registry={registry}
            registryError={registryError}
            active={library}
            errors={indicatorErrors}
            builtins={INDICATORS.map((ind) => ({ name: ind.name, label: ind.label, on: active.includes(ind.name) }))}
            dailyOnly={!libraryActive}
            onAdd={(def) => setLibrary((l) => [...l, { uid: newUid(), id: def.id, params: defaultParams(def) }])}
            onRemove={(uid) => setLibrary((l) => l.filter((x) => x.uid !== uid))}
            onParams={(uid, params) => setLibrary((l) => l.map((x) => (x.uid === uid ? { ...x, params } : x)))}
            onToggleHidden={(uid) => setLibrary((l) => l.map((x) => (x.uid === uid ? { ...x, hidden: !x.hidden } : x)))}
            onBuiltin={(name, on) => toggleIndicator(INDICATORS.find((i) => i.name === name)!, on)}
            onClose={() => setMenuOpen(false)}
          />
        )}
      </div>

      {/* Middle: left drawing toolbar + chart */}
      <div className="flex min-h-0 flex-1">
        <DrawingToolbar key={symbol} getChart={() => chartRef.current} />
        <div className="relative min-w-0 flex-1">
          <div ref={hostRef} className="h-full w-full" aria-label={`${symbol} candlestick chart`} />
          {status && (
            <div className="pointer-events-none absolute inset-0 flex items-center justify-center text-xs text-text-secondary">
              {status}
            </div>
          )}
        </div>
      </div>

      {/* Bottom bar: date ranges, measured against the real trading dates */}
      <RangeBar dates={dailyDates} value={range} onChange={setRange} shownFrom={rangeFrom} shownCount={shownCount}
        axisMode={axisMode} onAxisMode={setAxisMode} />
    </div>
  );
}
