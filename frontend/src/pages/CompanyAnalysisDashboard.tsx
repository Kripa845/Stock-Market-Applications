// import { useCallback, useEffect, useMemo, useState } from 'react';
// import {
//   BarChart, Bar, ComposedChart, Line,
//   XAxis, YAxis, CartesianGrid,
//   Tooltip, ResponsiveContainer, Cell, Customized, ReferenceLine, useXAxisScale, useYAxisScale,
// } from 'recharts';
// import {
//   Activity, AlertTriangle,
//   Loader2, Newspaper,
//   RefreshCw, TrendingUp,
// } from 'lucide-react';
// import clsx from 'clsx';

// import PageHeader from '../components/common/PageHeader';
// import Badge from '../components/common/Badge';
// import VolumeAnomalyChart from '../components/analysis/VolumeAnomalyChart';
// import { NewsSentimentScatter } from '../components/analysis/NewsSentimentScatter';
// import { getCompanies } from '../api/companies';
// import {
//   analysisApi,
//   type BehaviorSummary,
//   type CategorizedCompanyNews,
//   type PricePoint,
//   type NewsSentimentForwardResponse,
//   type VolumeAnomaly,
//   type RvolPoint,
// } from '../api/analysis';
// import type { Company } from '../types/company';

// // ─── Shared chart style ───────────────────────────────────────────────────────
// const TT_STYLE = {
//   background: 'var(--trading-panel)',
//   border: '1px solid var(--trading-divider)',
//   borderRadius: 3,
//   fontSize: 12,
//   color: 'var(--trading-text-primary)',
// };

// const COLORS = {
//   buy:     'var(--trading-up)',
//   sell:    'var(--trading-down)',
//   neutral: 'var(--trading-muted)',
// };

// function fmt(n: number) {
//   if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
//   if (n >= 1_000)     return `${(n / 1_000).toFixed(1)}K`;
//   return String(n);
// }

// // ─── Sub-components ───────────────────────────────────────────────────────────

// function StatPill({
//   label, value, sub, color = 'text-text-primary',
// }: { label: string; value: string | number; sub?: string; color?: string }) {
//   return (
//     <div className="flex flex-col gap-0.5 min-w-[90px]">
//       <span className="text-[10px] uppercase tracking-widest text-text-muted">{label}</span>
//       <span className={clsx('text-base font-bold font-mono', color)}>{value}</span>
//       {sub && <span className="text-[11px] text-text-muted">{sub}</span>}
//     </div>
//   );
// }

// function SectionTitle({ icon: Icon, children }: { icon: React.ElementType; children: React.ReactNode }) {
//   return (
//     <div className="flex items-center gap-2 mb-3">
//       <Icon size={15} className="text-accent-light shrink-0" />
//       <h3 className="text-sm font-semibold text-text-primary">{children}</h3>
//     </div>
//   );
// }

// // ─── Price + VWAP combined chart ─────────────────────────────────────────────
// function CandleLayer({ data }: { data: PricePoint[] }) {
//   const xScale = useXAxisScale('date');
//   const yScale = useYAxisScale('price');
//   if (!xScale || !yScale || data.length === 0) return null;
//   const centers = data.map(d => xScale(d.date, { position: 'middle' }));
//   const pitches = centers.slice(1).flatMap((x, i) => x !== undefined && centers[i] !== undefined ? [Math.abs(x - centers[i])] : []);
//   const bodyWidth = Math.max(2, Math.min(12, (pitches.length ? Math.min(...pitches) : 10) * 0.62));
//   const vwapPoints = data.flatMap((point, i) => {
//     const x = centers[i];
//     const value = point.volume > 0 ? Number(point.turnover) / point.volume : Number(point.close);
//     const y = yScale(value);
//     return x !== undefined && y !== undefined ? [`${x},${y}`] : [];
//   }).join(' ');
//   return <g aria-hidden="true"><polyline points={vwapPoints} fill="none" stroke="var(--trading-accent)" strokeWidth={1.7} strokeLinejoin="round" strokeLinecap="round" />{data.map((point, i) => {
//     const x = centers[i];
//     const open = yScale(Number(point.open));
//     const close = yScale(Number(point.close));
//     const high = yScale(Number(point.high));
//     const low = yScale(Number(point.low));
//     if (x === undefined || open === undefined || close === undefined || high === undefined || low === undefined) return null;
//     const up = Number(point.close) >= Number(point.open);
//     const color = up ? COLORS.buy : COLORS.sell;
//     return <g key={point.id}><line x1={x} x2={x} y1={high} y2={low} stroke={color} strokeWidth={1} /><rect x={x - bodyWidth / 2} y={Math.min(open, close)} width={bodyWidth} height={Math.max(1, Math.abs(close - open))} fill={color} /></g>;
//   })}</g>;
// }

// function OhlcTooltip({ active, payload, label }: { active?: boolean; payload?: Array<{ payload?: PricePoint & { rvol?: number | null } }>; label?: string }) {
//   const point = payload?.[0]?.payload;
//   if (!active || !point) return null;
//   const up = Number(point.close) >= Number(point.open);
//   return <div className="rounded-sm border border-bg-border bg-bg-elevated px-3 py-2 text-xs shadow-lg">
//     <p className="mb-1 text-text-muted">{label}</p>
//     <div className="grid grid-cols-2 gap-x-4 gap-y-0.5 font-mono tabular-nums">
//       <span className="text-text-muted">O</span><span>{Number(point.open).toFixed(2)}</span>
//       <span className="text-text-muted">H</span><span>{Number(point.high).toFixed(2)}</span>
//       <span className="text-text-muted">L</span><span>{Number(point.low).toFixed(2)}</span>
//       <span className="text-text-muted">C</span><span style={{ color: up ? COLORS.buy : COLORS.sell }}>{Number(point.close).toFixed(2)}</span>
//       <span className="text-text-muted">VWAP</span><span className="text-accent-light">{(point.volume > 0 ? Number(point.turnover) / point.volume : Number(point.close)).toFixed(2)}</span>
//       <span className="text-text-muted">Vol</span><span>{fmt(point.volume)}</span>
//       {point.rvol !== undefined && <><span className="text-text-muted">RVOL</span><span>{point.rvol === null ? '—' : `${point.rvol.toFixed(2)}×`}</span></>}
//     </div>
//   </div>;
// }

// function buildIndicatorData(data: PricePoint[]) {
//   const raw = data.map(point => {
//     const high = Number(point.high);
//     const low = Number(point.low);
//     const close = Number(point.close);
//     const range = high - low;
//     return {
//       date: point.date,
//       close,
//       vwap: point.volume > 0 ? Number(point.turnover) / point.volume : close,
//       volume: point.volume,
//       buyShare: range > 0 ? Math.max(0, Math.min(1, (close - low) / range)) : 0.5,
//     };
//   });
//   return raw.map((point, index) => {
//     const window = raw.slice(Math.max(0, index - 13), index + 1);
//     const totalVolume = window.reduce((sum, row) => sum + row.volume, 0);
//     const buyingVolume = window.reduce((sum, row) => sum + row.volume * row.buyShare, 0);
//     const buyPressure = totalVolume > 0 ? buyingVolume / totalVolume : 0.5;
//     return { ...point, buyPressure, sellPressure: 1 - buyPressure };
//   });
// }

// type RvolTier = 'Dead' | 'Below Average' | 'Normal' | 'Above Average / High' | 'Extreme';
// type RvolSettings = { lookback: number; thresholds: [number, number, number, number] };
// const RVOL_LOOKBACK = 20;
// const RVOL_THRESHOLDS: [number, number, number, number] = [0.5, 0.8, 1.25, 4];

// const RVOL_TIER_COLORS: Record<RvolTier, string> = {
//   Dead: '#ef4444',
//   'Below Average': '#f59e0b',
//   Normal: 'var(--trading-muted)',
//   'Above Average / High': 'var(--trading-up)',
//   Extreme: '#d946ef',
// };

// function TradingViewChart({ data, rvolData, rvolSettings, volumeAnomalies }: { data: PricePoint[]; rvolData: RvolPoint[]; rvolSettings: RvolSettings; volumeAnomalies: VolumeAnomaly[] }) {
//   const indicators = buildIndicatorData(data);
//   const rvolByDate = new Map(rvolData.map(point => [point.date, point.rvol]));
//   const anomalyByDate = new Map(volumeAnomalies.map(point => [point.date, point.is_anomaly]));
//   const chartData = data.map(point => {
//     const rvol = rvolByDate.get(point.date) ?? null;
//     const thresholds = rvolSettings.thresholds;
//     const rvolTier: RvolTier | null = rvol === null ? null
//       : rvol < thresholds[0] ? 'Dead'
//       : rvol < thresholds[1] ? 'Below Average'
//       : rvol < thresholds[2] ? 'Normal'
//       : rvol < thresholds[3] ? 'Above Average / High'
//       : 'Extreme';
//     return { ...point, rvol, rvolTier };
//   });
//   const latestChartPoint = chartData[chartData.length - 1];
//   const latestIndicator = indicators[indicators.length - 1];
//   const lowest = data.length ? Math.min(...data.map(p => Number(p.low))) : 0;
//   const highest = data.length ? Math.max(...data.map(p => Number(p.high))) : 1;
//   const pad = (highest - lowest) * 0.04 || 1;
//   return <div className="space-y-0.5">
//     <div className="flex items-center gap-2 px-1 pb-1 text-[11px]"><span className="text-text-muted">O H L C</span>{data.length > 0 && <span className="font-mono tabular-nums text-text-primary">{Number(data[data.length - 1].close).toFixed(2)}</span>}<span className="ml-auto text-text-muted">VWAP <span className="font-mono tabular-nums text-accent-light">{latestIndicator?.vwap.toFixed(2) ?? '?'}</span></span></div>
//     <ResponsiveContainer width="100%" height={300}>
//       <ComposedChart data={chartData} syncId="company-ohlcv" syncMethod="value" margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
//         <CartesianGrid stroke="var(--trading-grid)" strokeOpacity={0.65} vertical />
//         <XAxis xAxisId="date" dataKey="date" hide />
//         <YAxis yAxisId="price" domain={[lowest - pad, highest + pad]} orientation="right" tick={{ fontSize: 10, fill: 'var(--trading-muted)' }} tickLine={false} axisLine={false} width={52} tickFormatter={v => Number(v).toFixed(2)} />
//         <Tooltip content={<OhlcTooltip />} cursor={{ stroke: 'var(--trading-muted)', strokeDasharray: '2 4', strokeWidth: 1 }} />
//         <Bar xAxisId="date" yAxisId="price" dataKey="close" fill="transparent" stroke="transparent" isAnimationActive={false} />
//         <Customized component={<CandleLayer data={chartData} />} />
//       </ComposedChart>
//     </ResponsiveContainer>
//     <div className="flex items-center gap-2 px-1 pt-1 text-[11px]">
//       <span className="text-text-muted">RVOL {rvolSettings.lookback} {rvolSettings.thresholds.join(' ')}</span>
//       <span className="ml-auto font-mono tabular-nums text-text-primary">
//         {!latestChartPoint || latestChartPoint.rvol === null ? '—' : `${latestChartPoint.rvol.toFixed(2)}×`}
//       </span>
//     </div>
//     <ResponsiveContainer width="100%" height={105}>
//       <ComposedChart data={chartData} syncId="company-ohlcv" syncMethod="value" margin={{ top: 2, right: 4, left: 0, bottom: 0 }}>
//         <CartesianGrid stroke="var(--trading-grid)" strokeOpacity={0.5} vertical={false} />
//         <XAxis dataKey="date" tick={{ fontSize: 9, fill: 'var(--trading-muted)' }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
//         <YAxis orientation="right" domain={[0, (max: number) => Math.max(4, max * 1.05)]} tick={{ fontSize: 9, fill: 'var(--trading-muted)' }} tickLine={false} axisLine={false} width={52} />
//         <Tooltip content={<OhlcTooltip />} cursor={{ stroke: 'var(--trading-muted)', strokeDasharray: '2 4' }} />
//         <ReferenceLine y={1} stroke="var(--trading-muted)" strokeDasharray="4 3" />
//         <Bar dataKey="rvol" name="RVOL" maxBarSize={10} isAnimationActive={false}>
//           {chartData.map(point => <Cell key={point.id} fill={point.rvolTier ? RVOL_TIER_COLORS[point.rvolTier] : 'transparent'} opacity={0.9} />)}
//         </Bar>
//       </ComposedChart>
//     </ResponsiveContainer>
//     <div className="flex items-center gap-2 px-1 pt-1 text-[11px]"><span className="text-text-muted">Volume</span><span style={{ color: '#d946ef' }}>◆ Anomaly ≥2.5× prior 20-session SMA</span>{data.length > 0 && <span className="ml-auto font-mono tabular-nums text-up">{fmt(data[data.length - 1].volume)}</span>}</div>
//     <ResponsiveContainer width="100%" height={90}>
//       <BarChart data={chartData} syncId="company-ohlcv" syncMethod="value" margin={{ top: 0, right: 4, left: 0, bottom: 0 }}>
//         <CartesianGrid stroke="var(--trading-grid)" strokeOpacity={0.5} vertical={false} />
//         <XAxis dataKey="date" tick={{ fontSize: 9, fill: 'var(--trading-muted)' }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
//         <YAxis orientation="right" tick={{ fontSize: 9, fill: 'var(--trading-muted)' }} tickLine={false} axisLine={false} width={52} tickFormatter={fmt} />
//         <Tooltip contentStyle={TT_STYLE} cursor={{ stroke: 'var(--trading-muted)', strokeDasharray: '2 4' }} formatter={(v: unknown) => [fmt(Number(v ?? 0)), 'Volume']} />
//         <Bar dataKey="volume" maxBarSize={10} isAnimationActive={false}>{data.map(point => <Cell key={point.id} fill={anomalyByDate.get(point.date) === true ? '#d946ef' : Number(point.close) >= Number(point.open) ? COLORS.buy : COLORS.sell} opacity={0.8} />)}</Bar>
//       </BarChart>
//     </ResponsiveContainer>

//     <div className="flex items-center gap-3 border-t border-bg-border px-1 pt-2 text-[11px]">
//       <span className="text-text-muted">Buy / Sell Pressure</span>
//       <span className="font-mono tabular-nums text-up">Buy {latestIndicator ? (latestIndicator.buyPressure * 100).toFixed(0) : '—'}%</span>
//       <span className="font-mono tabular-nums text-down">Sell {latestIndicator ? (latestIndicator.sellPressure * 100).toFixed(0) : '—'}%</span>
//       <span className="ml-auto text-[10px] text-text-muted">14-bar OHLCV estimate</span>
//     </div>
//     <ResponsiveContainer width="100%" height={120}>
//       <ComposedChart data={indicators} syncId="company-ohlcv" syncMethod="value" margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
//         <CartesianGrid stroke="var(--trading-grid)" strokeOpacity={0.55} vertical={false} />
//         <XAxis dataKey="date" tick={{ fontSize: 9, fill: 'var(--trading-muted)' }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
//         <YAxis orientation="right" domain={[0, 1]} ticks={[0, 0.5, 1]} tick={{ fontSize: 9, fill: 'var(--trading-muted)' }} tickLine={false} axisLine={false} width={52} tickFormatter={v => `${Math.round(Number(v) * 100)}%`} />
//         <Tooltip contentStyle={TT_STYLE} cursor={{ stroke: 'var(--trading-muted)', strokeDasharray: '2 4' }} formatter={(v: unknown, name: unknown) => [`${(Number(v ?? 0) * 100).toFixed(1)}%`, String(name)]} />
//         <Line type="monotone" dataKey="buyPressure" name="Buy pressure" stroke="var(--trading-up)" strokeWidth={1.5} dot={false} isAnimationActive={false} />
//         <Line type="monotone" dataKey="sellPressure" name="Sell pressure" stroke="var(--trading-down)" strokeWidth={1.5} dot={false} isAnimationActive={false} />
//       </ComposedChart>
//     </ResponsiveContainer>
//   </div>;
// }

// // ─── Helpers ──────────────────────────────────────────────────────────────────

// function computeVwap(prices: PricePoint[]) {
//   const totalTurnover = prices.reduce((s, p) => s + parseFloat(p.turnover), 0);
//   const totalVolume   = prices.reduce((s, p) => s + p.volume, 0);
//   return totalVolume ? totalTurnover / totalVolume : 0;
// }

// // ─── Main page ────────────────────────────────────────────────────────────────

// export default function CompanyAnalysisDashboard() {
//   const [companies,   setCompanies]   = useState<Company[]>([]);
//   const [selectedId,  setSelectedId]  = useState<number | null>(null);
//   const [prices,      setPrices]      = useState<PricePoint[]>([]);
//   const [rvolData, setRvolData] = useState<RvolPoint[]>([]);
//   const [behavior,    setBehavior]    = useState<BehaviorSummary | null>(null);
//   const [categorizedNews, setCategorizedNews] = useState<CategorizedCompanyNews[] | null>(null);
//   const [newsForward, setNewsForward] = useState<NewsSentimentForwardResponse | null>(null);
//   const [loadingNewsForward, setLoadingNewsForward] = useState(false);
//   const [newsForwardError, setNewsForwardError] = useState('');
//   const [volumeAnomalies, setVolumeAnomalies] = useState<VolumeAnomaly[]>([]);
//   const [volumeAnomalyRefresh, setVolumeAnomalyRefresh] = useState(0);
//   const [loadingVolumeAnomalies, setLoadingVolumeAnomalies] = useState(false);
//   const [volumeAnomalyError, setVolumeAnomalyError] = useState('');
//   const [priceRange,  setPriceRange]  = useState<'7d' | '30d' | '90d'>('30d');
//   const [loading,     setLoading]     = useState(true);
//   const [loadingData, setLoadingData] = useState(false);
//   const [error,       setError]       = useState('');

//   // Load company list once
//   useEffect(() => {
//     getCompanies({ status: 'active' })
//       .then(r => {
//         setCompanies(r.results);
//         setSelectedId(r.results[0]?.id ?? null);
//       })
//       .catch(() => setError('Unable to load companies.'))
//       .finally(() => setLoading(false));
//   }, []);

//   // Load extended historical prices once per company; the selected range is filtered from this history.
//   const loadData = useCallback(() => {
//     if (!selectedId) return;
//     setVolumeAnomalyRefresh(value => value + 1);
//     setLoadingData(true);
//     setError('');
//     setPrices([]);
//     setCategorizedNews(null);
//     Promise.allSettled([
//       analysisApi.getPrices(selectedId, '180d', { source: 'crawled' }),
//       analysisApi.getBehavior(selectedId),
//       analysisApi.getCategorizedCompanyNews(selectedId),
//     ]).then(([prRes, bhRes, newsRes]) => {
//       if (prRes.status   === 'fulfilled') setPrices(prRes.value.prices);
//       if (bhRes.status   === 'fulfilled') setBehavior(bhRes.value);
//       if (newsRes.status === 'fulfilled') setCategorizedNews(newsRes.value.results);
//       // surface any hard errors
//       const failed = [prRes, bhRes, newsRes].filter(r => r.status === 'rejected');
//       if (failed.length === 3) setError('Unable to load company data. Check your permissions.');
//     }).finally(() => setLoadingData(false));
//   }, [selectedId]);

//   useEffect(() => { loadData(); }, [loadData]);

//   // ── Derived values ──────────────────────────────────────────────────────────
//   const company  = companies.find(c => c.id === selectedId);
//   const chartPrices = useMemo(() => {
//     const days = priceRange === '7d' ? 7 : priceRange === '30d' ? 30 : 90;
//     const start = new Date();
//     start.setDate(start.getDate() - days);
//     const startDate = `${start.getFullYear()}-${String(start.getMonth() + 1).padStart(2, '0')}-${String(start.getDate()).padStart(2, '0')}`;
//     return prices.filter(point => point.date >= startDate);
//   }, [prices, priceRange]);
//   const vwap30   = useMemo(() => computeVwap(chartPrices), [chartPrices]);

//   useEffect(() => {
//     if (!company) return;
//     let cancelled = false;
//     const start = new Date();
//     start.setDate(start.getDate() - 180);
//     const startDate = `${start.getFullYear()}-${String(start.getMonth() + 1).padStart(2, '0')}-${String(start.getDate()).padStart(2, '0')}`;
//     setVolumeAnomalies([]);
//     setLoadingVolumeAnomalies(true);
//     setVolumeAnomalyError('');
//     analysisApi.getVolumeAnomalies(company.symbol, { start_date: startDate, lookback: 20 })
//       .then((result) => { if (!cancelled) setVolumeAnomalies(result); })
//       .catch(() => { if (!cancelled) setVolumeAnomalyError('Unable to load volume anomaly history.'); })
//       .finally(() => { if (!cancelled) setLoadingVolumeAnomalies(false); });
//     return () => { cancelled = true; };
//   }, [company, volumeAnomalyRefresh]);

//   useEffect(() => {
//     if (!company) return;
//     let cancelled = false;
//     const start = new Date();
//     start.setDate(start.getDate() - 180);
//     const startDate = `${start.getFullYear()}-${String(start.getMonth() + 1).padStart(2, '0')}-${String(start.getDate()).padStart(2, '0')}`;
//     setRvolData([]);
//     analysisApi.getRvol(company.symbol, { start_date: startDate, ma_length: RVOL_LOOKBACK, ma_type: 'SMA' })
//       .then(result => { if (!cancelled) setRvolData(result); })
//       .catch(() => { if (!cancelled) setRvolData([]); });
//     return () => { cancelled = true; };
//   }, [company, volumeAnomalyRefresh]);

//   useEffect(() => {
//     if (!company) return;
//     let cancelled = false;
//     const days = priceRange === '7d' ? 7 : priceRange === '30d' ? 30 : 90;
//     const start = new Date();
//     start.setDate(start.getDate() - days);
//     const startDate = `${start.getFullYear()}-${String(start.getMonth() + 1).padStart(2, '0')}-${String(start.getDate()).padStart(2, '0')}`;
//     setLoadingNewsForward(true);
//     setNewsForwardError('');
//     analysisApi.getNewsSentimentForward(company.symbol, { start_date: startDate })
//       .then((result) => { if (!cancelled) setNewsForward(result); })
//       .catch(() => { if (!cancelled) setNewsForwardError('Unable to load news sentiment correlation.'); })
//       .finally(() => { if (!cancelled) setLoadingNewsForward(false); });
//     return () => { cancelled = true; };
//   }, [company, priceRange]);

//   const latestClose = chartPrices.length ? parseFloat(chartPrices[chartPrices.length - 1].close) : 0;
//   const firstClose  = chartPrices.length ? parseFloat(chartPrices[0].close) : 0;
//   const positive    = latestClose >= firstClose;
//   const spreadPct   = vwap30 ? ((latestClose - vwap30) / vwap30 * 100) : 0;

//   // ── Render ──────────────────────────────────────────────────────────────────
//   if (loading) {
//     return (
//       <div className="flex items-center justify-center py-32">
//         <Loader2 size={28} className="animate-spin text-accent" />
//       </div>
//     );
//   }

//   return (
//     <div className="trading-terminal-page space-y-6">

//       {/* ── Page header ──────────────────────────────────────────────────── */}
//       <PageHeader
//         title="Company Behavior Analysis"
//         subtitle="Price / volume trends, VWAP, broker activity, and categorized company news."
//         actions={
//           <button
//             onClick={loadData}
//             disabled={loadingData}
//             className="btn-ghost flex items-center gap-2 text-xs"
//           >
//             <RefreshCw size={13} className={loadingData ? 'animate-spin' : ''} />
//             Refresh
//           </button>
//         }
//       />

//       {error && (
//         <div className="flex items-center gap-2 text-sm text-down">
//           <AlertTriangle size={14} /> {error}
//         </div>
//       )}

//       {/* ── Company selector ─────────────────────────────────────────────── */}
//       <div className="flex flex-wrap gap-2">
//         {companies.map(c => (
//           <button
//             key={c.id}
//             onClick={() => setSelectedId(c.id)}
//             className={clsx(
//               'px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-all',
//               c.id === selectedId
//                 ? 'bg-accent text-white shadow-md'
//                 : 'bg-bg-elevated text-text-secondary hover:text-text-primary hover:bg-bg-card',
//             )}
//           >
//             {c.symbol}
//           </button>
//         ))}
//       </div>

//       {/* ── Company header card ───────────────────────────────────────────── */}
//       {company && (
//         <div className="card flex flex-wrap items-center gap-6 py-4">
//           <div className="flex items-center gap-3">
//             <div className="w-11 h-11 rounded-xl bg-accent/20 flex items-center justify-center font-bold font-mono text-accent-light text-sm">
//               {company.symbol.slice(0, 3)}
//             </div>
//             <div>
//               <p className="font-semibold text-text-primary text-base">{company.symbol}</p>
//               <p className="text-xs text-text-muted">{company.name}</p>
//             </div>
//           </div>

//           <Badge variant="gray">{company.sector}</Badge>

//           <div className="flex flex-wrap gap-5 ml-auto">
//             <StatPill
//               label="Latest close"
//               value={`Rs. ${latestClose.toFixed(2)}`}
//               color={positive ? 'text-up' : 'text-down'}
//             />
//             <StatPill
//               label={`${priceRange} change`}
//               value={`${positive ? '+' : ''}${firstClose ? ((latestClose - firstClose) / firstClose * 100).toFixed(2) : 0}%`}
//               color={positive ? 'text-up' : 'text-down'}
//             />
//             <StatPill
//               label="VWAP 30d"
//               value={`Rs. ${vwap30.toFixed(2)}`}
//               color="text-yellow-400"
//             />
//             <StatPill
//               label="vs VWAP"
//               value={`${spreadPct >= 0 ? '+' : ''}${spreadPct.toFixed(2)}%`}
//               color={spreadPct >= 0 ? 'text-up' : 'text-down'}
//               sub={spreadPct >= 0 ? 'Above VWAP' : 'Below VWAP'}
//             />
//           </div>
//         </div>
//       )}

//       {loadingData && (
//         <div className="flex items-center gap-2 text-xs text-text-muted">
//           <Loader2 size={12} className="animate-spin" /> Loading data…
//         </div>
//       )}

//       {/* ── Range selector ───────────────────────────────────────────────── */}
//       <div className="flex items-center gap-1 bg-bg-elevated rounded-lg p-0.5 w-fit">
//         {(['7d', '30d', '90d'] as const).map(r => (
//           <button
//             key={r}
//             onClick={() => setPriceRange(r)}
//             className={clsx(
//               'px-4 py-1.5 rounded text-xs font-medium transition-all',
//               priceRange === r
//                 ? 'bg-accent text-white'
//                 : 'text-text-secondary hover:text-text-primary',
//             )}
//           >
//             {r === '7d' ? '1W' : r === '30d' ? '1M' : '3M'}
//           </button>
//         ))}
//       </div>

//       {chartPrices.length === 0 && !loadingData ? (
//         <div className="card py-16 text-center">
//           <p className="text-sm text-text-muted">No price data available for this company.</p>
//         </div>
//       ) : (
//         <>
//           {/* TradingView-style price and volume chart */}
//           <div className="card space-y-2">
//             <SectionTitle icon={TrendingUp}>Price Action</SectionTitle>
//             <TradingViewChart data={chartPrices} rvolData={rvolData} rvolSettings={{ lookback: RVOL_LOOKBACK, thresholds: RVOL_THRESHOLDS }} volumeAnomalies={volumeAnomalies} />
//           </div>

//           <VolumeAnomalyChart data={volumeAnomalies} loading={loadingVolumeAnomalies} error={volumeAnomalyError} />
//           <NewsSentimentScatter data={newsForward} priceData={chartPrices} loading={loadingNewsForward} error={newsForwardError} />

//           {/* ── Row 3: Behavior AI summary ───────────────────────────────── */}
//           {behavior && (
//             <div className="card">
//               <SectionTitle icon={Activity}>Behavior Analysis Summary</SectionTitle>
//               <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3 mb-4">
//                 <div className="bg-bg-elevated rounded-lg p-3">
//                   <p className="text-[10px] text-text-muted uppercase tracking-wider mb-1">Pressure</p>
//                   <p className={clsx('text-sm font-semibold capitalize',
//                     behavior.pressure === 'buying' ? 'text-up'
//                     : behavior.pressure === 'selling' ? 'text-down'
//                     : 'text-text-secondary')}>
//                     {behavior.pressure === 'buying' ? '▲ ' : behavior.pressure === 'selling' ? '▼ ' : '— '}
//                     {behavior.pressure}
//                   </p>
//                 </div>
//                 <div className="bg-bg-elevated rounded-lg p-3">
//                   <p className="text-[10px] text-text-muted uppercase tracking-wider mb-1">Volume Anomaly</p>
//                   <p className={clsx('text-sm font-semibold', behavior.volume_anomaly ? 'text-down' : 'text-up')}>
//                     {behavior.volume_anomaly ? `⚡ Yes (${behavior.volume_ratio !== null ? Number(behavior.volume_ratio).toFixed(2) : '?'}×)` : '✓ Normal'}
//                   </p>
//                 </div>
//                 <div className="bg-bg-elevated rounded-lg p-3">
//                   <p className="text-[10px] text-text-muted uppercase tracking-wider mb-1">News Sentiment</p>
//                   <p className={clsx('text-sm font-semibold',
//                     behavior.news_sentiment_score > 0.1 ? 'text-up'
//                     : behavior.news_sentiment_score < -0.1 ? 'text-down'
//                     : 'text-text-secondary')}>
//                     {behavior.news_sentiment_score.toFixed(3)} ({behavior.news_count_30d} articles)
//                   </p>
//                 </div>
//                 <div className="bg-bg-elevated rounded-lg p-3">
//                   <p className="text-[10px] text-text-muted uppercase tracking-wider mb-1">Spread vs VWAP</p>
//                   <p className={clsx('text-sm font-semibold',
//                     behavior.price_to_vwap_spread_pct === null ? 'text-text-secondary'
//                     : behavior.price_to_vwap_spread_pct >= 0 ? 'text-up' : 'text-down')}>
//                     {behavior.price_to_vwap_spread_pct !== null
//                       ? `${behavior.price_to_vwap_spread_pct >= 0 ? '+' : ''}${behavior.price_to_vwap_spread_pct.toFixed(2)}%`
//                       : '—'}
//                   </p>
//                 </div>
//               </div>
//               <p className="text-sm text-text-secondary leading-relaxed border-l-2 border-accent-dim pl-3">
//                 {behavior.summary_text}
//               </p>
//             </div>
//           )}

//           {/* Categorized articles tagged to the selected company */}
//           <div className="card">
//             <div className="mb-3 flex items-center justify-between gap-3">
//               <SectionTitle icon={Newspaper}>{company?.symbol ?? 'Company'} News</SectionTitle>
//               <span className="text-[10px] text-text-muted">{categorizedNews?.length ?? 0} categorized articles</span>
//             </div>
//             {categorizedNews === null ? (
//               <p className="py-4 text-center text-xs text-text-muted">
//                 {loadingData ? 'Loading categorized company news…' : 'Unable to load categorized news.'}
//               </p>
//             ) : categorizedNews.length === 0 ? (
//               <p className="py-4 text-center text-xs text-text-muted">
//                 No categorized news is linked to this company yet.
//               </p>
//             ) : (
//               <div className="divide-y divide-bg-border">
//                 {categorizedNews.map(article => (
//                   <article key={article.id} className="flex flex-wrap items-start justify-between gap-3 py-3 first:pt-0 last:pb-0">
//                     <div className="min-w-0 flex-1">
//                       <a href={article.url} target="_blank" rel="noreferrer" className="text-sm font-medium text-text-primary hover:text-accent-light">
//                         {article.headline}
//                       </a>
//                       <p className="mt-1 text-[10px] text-text-muted">
//                         {article.source}{article.published_at ? ` · ${new Date(article.published_at).toLocaleString()}` : ''}
//                         {' · '}Company match {Math.round(article.confidence * 100)}%{article.is_manual ? ' · Manually categorized' : ''}
//                       </p>
//                     </div>
//                     <span className={clsx(
//                       'rounded px-2 py-1 text-[10px] uppercase',
//                       article.sentiment_label === 'positive' ? 'bg-up/10 text-up'
//                         : article.sentiment_label === 'negative' ? 'bg-down/10 text-down'
//                         : 'bg-bg-elevated text-text-muted',
//                     )}>
//                       {article.sentiment_label || 'Sentiment unavailable'}
//                     </span>
//                   </article>
//                 ))}
//               </div>
//             )}
//           </div>
//         </>
//       )}
//     </div>
//   );
// }
import { useCallback, useEffect, useMemo, useState } from 'react';
import KlinePriceChart from '../components/charts/KlinePriceChart';
import {
  Activity, AlertTriangle,
  Loader2, Newspaper,
  RefreshCw, TrendingUp,
} from 'lucide-react';
import clsx from 'clsx';

import PageHeader from '../components/common/PageHeader';
import Badge from '../components/common/Badge';
import VolumeAnomalyChart from '../components/analysis/VolumeAnomalyChart';
import { NewsSentimentScatter } from '../components/analysis/NewsSentimentScatter';
import { getCompanies } from '../api/companies';
import {
  analysisApi,
  type BehaviorSummary,
  type CategorizedCompanyNews,
  type PricePoint,
  type NewsSentimentForwardResponse,
  type VolumeAnomaly,
  type RvolPoint,
} from '../api/analysis';
import type { Company } from '../types/company';

// ─── Sub-components ───────────────────────────────────────────────────────────

function StatPill({
  label, value, sub, color = 'text-text-primary',
}: { label: string; value: string | number; sub?: string; color?: string }) {
  return (
    <div className="flex flex-col gap-0.5 min-w-[90px]">
      <span className="text-[10px] uppercase tracking-widest text-text-muted">{label}</span>
      <span className={clsx('text-base font-bold font-mono', color)}>{value}</span>
      {sub && <span className="text-[11px] text-text-muted">{sub}</span>}
    </div>
  );
}

function SectionTitle({ icon: Icon, children }: { icon: React.ElementType; children: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2 mb-3">
      <Icon size={15} className="text-accent-light shrink-0" />
      <h3 className="text-sm font-semibold text-text-primary">{children}</h3>
    </div>
  );
}

const RVOL_LOOKBACK = 20;
const RVOL_THRESHOLDS: [number, number, number, number] = [0.5, 0.8, 1.25, 4];

// ─── Helpers ──────────────────────────────────────────────────────────────────

function computeVwap(prices: PricePoint[]) {
  const totalTurnover = prices.reduce((s, p) => s + parseFloat(p.turnover), 0);
  const totalVolume   = prices.reduce((s, p) => s + p.volume, 0);
  return totalVolume ? totalTurnover / totalVolume : 0;
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function CompanyAnalysisDashboard() {
  const [companies,   setCompanies]   = useState<Company[]>([]);
  const [selectedId,  setSelectedId]  = useState<number | null>(null);
  const [prices,      setPrices]      = useState<PricePoint[]>([]);
  const [rvolData, setRvolData] = useState<RvolPoint[]>([]);
  const [behavior,    setBehavior]    = useState<BehaviorSummary | null>(null);
  const [categorizedNews, setCategorizedNews] = useState<CategorizedCompanyNews[] | null>(null);
  const [newsForward, setNewsForward] = useState<NewsSentimentForwardResponse | null>(null);
  const [loadingNewsForward, setLoadingNewsForward] = useState(false);
  const [newsForwardError, setNewsForwardError] = useState('');
  const [volumeAnomalies, setVolumeAnomalies] = useState<VolumeAnomaly[]>([]);
  const [volumeAnomalyRefresh, setVolumeAnomalyRefresh] = useState(0);
  const [loadingVolumeAnomalies, setLoadingVolumeAnomalies] = useState(false);
  const [volumeAnomalyError, setVolumeAnomalyError] = useState('');
  const [priceRange,  setPriceRange]  = useState<'7d' | '30d' | '90d'>('30d');
  const [loading,     setLoading]     = useState(true);
  const [loadingData, setLoadingData] = useState(false);
  const [error,       setError]       = useState('');

  // Load company list once
  useEffect(() => {
    getCompanies({ status: 'active' })
      .then(r => {
        setCompanies(r.results);
        setSelectedId(r.results[0]?.id ?? null);
      })
      .catch(() => setError('Unable to load companies.'))
      .finally(() => setLoading(false));
  }, []);

  // Load extended historical prices once per company; the selected range is filtered from this history.
  const loadData = useCallback(() => {
    if (!selectedId) return;
    setVolumeAnomalyRefresh(value => value + 1);
    setLoadingData(true);
    setError('');
    setPrices([]);
    setCategorizedNews(null);
    Promise.allSettled([
      analysisApi.getPrices(selectedId, '180d', { source: 'crawled' }),
      analysisApi.getBehavior(selectedId),
      analysisApi.getCategorizedCompanyNews(selectedId),
    ]).then(([prRes, bhRes, newsRes]) => {
      if (prRes.status   === 'fulfilled') setPrices(prRes.value.prices);
      if (bhRes.status   === 'fulfilled') setBehavior(bhRes.value);
      if (newsRes.status === 'fulfilled') setCategorizedNews(newsRes.value.results);
      // surface any hard errors
      const failed = [prRes, bhRes, newsRes].filter(r => r.status === 'rejected');
      if (failed.length === 3) setError('Unable to load company data. Check your permissions.');
    }).finally(() => setLoadingData(false));
  }, [selectedId]);

  useEffect(() => { loadData(); }, [loadData]);

  // ── Derived values ──────────────────────────────────────────────────────────
  const company  = companies.find(c => c.id === selectedId);
  const chartPrices = useMemo(() => {
    const days = priceRange === '7d' ? 7 : priceRange === '30d' ? 30 : 90;
    const start = new Date();
    start.setDate(start.getDate() - days);
    const startDate = `${start.getFullYear()}-${String(start.getMonth() + 1).padStart(2, '0')}-${String(start.getDate()).padStart(2, '0')}`;
    return prices.filter(point => point.date >= startDate);
  }, [prices, priceRange]);
  const vwap30   = useMemo(() => computeVwap(chartPrices), [chartPrices]);
  const anomalyDates = useMemo(
    () => volumeAnomalies.filter(v => v.is_anomaly).map(v => v.date),
    [volumeAnomalies],
  );

  useEffect(() => {
    if (!company) return;
    let cancelled = false;
    const start = new Date();
    start.setDate(start.getDate() - 180);
    const startDate = `${start.getFullYear()}-${String(start.getMonth() + 1).padStart(2, '0')}-${String(start.getDate()).padStart(2, '0')}`;
    setVolumeAnomalies([]);
    setLoadingVolumeAnomalies(true);
    setVolumeAnomalyError('');
    analysisApi.getVolumeAnomalies(company.symbol, { start_date: startDate, lookback: 20 })
      .then((result) => { if (!cancelled) setVolumeAnomalies(result); })
      .catch(() => { if (!cancelled) setVolumeAnomalyError('Unable to load volume anomaly history.'); })
      .finally(() => { if (!cancelled) setLoadingVolumeAnomalies(false); });
    return () => { cancelled = true; };
  }, [company, volumeAnomalyRefresh]);

  useEffect(() => {
    if (!company) return;
    let cancelled = false;
    const start = new Date();
    start.setDate(start.getDate() - 180);
    const startDate = `${start.getFullYear()}-${String(start.getMonth() + 1).padStart(2, '0')}-${String(start.getDate()).padStart(2, '0')}`;
    setRvolData([]);
    analysisApi.getRvol(company.symbol, { start_date: startDate, ma_length: RVOL_LOOKBACK, ma_type: 'SMA' })
      .then(result => { if (!cancelled) setRvolData(result); })
      .catch(() => { if (!cancelled) setRvolData([]); });
    return () => { cancelled = true; };
  }, [company, volumeAnomalyRefresh]);

  useEffect(() => {
    if (!company) return;
    let cancelled = false;
    const days = priceRange === '7d' ? 7 : priceRange === '30d' ? 30 : 90;
    const start = new Date();
    start.setDate(start.getDate() - days);
    const startDate = `${start.getFullYear()}-${String(start.getMonth() + 1).padStart(2, '0')}-${String(start.getDate()).padStart(2, '0')}`;
    setLoadingNewsForward(true);
    setNewsForwardError('');
    analysisApi.getNewsSentimentForward(company.symbol, { start_date: startDate })
      .then((result) => { if (!cancelled) setNewsForward(result); })
      .catch(() => { if (!cancelled) setNewsForwardError('Unable to load news sentiment correlation.'); })
      .finally(() => { if (!cancelled) setLoadingNewsForward(false); });
    return () => { cancelled = true; };
  }, [company, priceRange]);

  const latestClose = chartPrices.length ? parseFloat(chartPrices[chartPrices.length - 1].close) : 0;
  const firstClose  = chartPrices.length ? parseFloat(chartPrices[0].close) : 0;
  const positive    = latestClose >= firstClose;
  const spreadPct   = vwap30 ? ((latestClose - vwap30) / vwap30 * 100) : 0;

  // ── Render ──────────────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className="flex items-center justify-center py-32">
        <Loader2 size={28} className="animate-spin text-accent" />
      </div>
    );
  }

  return (
    <div className="trading-terminal-page space-y-6">

      {/* ── Page header ──────────────────────────────────────────────────── */}
      <PageHeader
        title="Company Behavior Analysis"
        subtitle="Price / volume trends, VWAP, broker activity, and categorized company news."
        actions={
          <button
            onClick={loadData}
            disabled={loadingData}
            className="btn-ghost flex items-center gap-2 text-xs"
          >
            <RefreshCw size={13} className={loadingData ? 'animate-spin' : ''} />
            Refresh
          </button>
        }
      />

      {error && (
        <div className="flex items-center gap-2 text-sm text-down">
          <AlertTriangle size={14} /> {error}
        </div>
      )}

      {/* ── Company selector ─────────────────────────────────────────────── */}
      <div className="flex flex-wrap gap-2">
        {companies.map(c => (
          <button
            key={c.id}
            onClick={() => setSelectedId(c.id)}
            className={clsx(
              'px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-all',
              c.id === selectedId
                ? 'bg-accent text-white shadow-md'
                : 'bg-bg-elevated text-text-secondary hover:text-text-primary hover:bg-bg-card',
            )}
          >
            {c.symbol}
          </button>
        ))}
      </div>

      {/* ── Company header card ───────────────────────────────────────────── */}
      {company && (
        <div className="card flex flex-wrap items-center gap-6 py-4">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-xl bg-accent/20 flex items-center justify-center font-bold font-mono text-accent-light text-sm">
              {company.symbol.slice(0, 3)}
            </div>
            <div>
              <p className="font-semibold text-text-primary text-base">{company.symbol}</p>
              <p className="text-xs text-text-muted">{company.name}</p>
            </div>
          </div>

          <Badge variant="gray">{company.sector}</Badge>

          <div className="flex flex-wrap gap-5 ml-auto">
            <StatPill
              label="Latest close"
              value={`Rs. ${latestClose.toFixed(2)}`}
              color={positive ? 'text-up' : 'text-down'}
            />
            <StatPill
              label={`${priceRange} change`}
              value={`${positive ? '+' : ''}${firstClose ? ((latestClose - firstClose) / firstClose * 100).toFixed(2) : 0}%`}
              color={positive ? 'text-up' : 'text-down'}
            />
            <StatPill
              label="VWAP 30d"
              value={`Rs. ${vwap30.toFixed(2)}`}
              color="text-yellow-400"
            />
            <StatPill
              label="vs VWAP"
              value={`${spreadPct >= 0 ? '+' : ''}${spreadPct.toFixed(2)}%`}
              color={spreadPct >= 0 ? 'text-up' : 'text-down'}
              sub={spreadPct >= 0 ? 'Above VWAP' : 'Below VWAP'}
            />
          </div>
        </div>
      )}

      {loadingData && (
        <div className="flex items-center gap-2 text-xs text-text-muted">
          <Loader2 size={12} className="animate-spin" /> Loading data…
        </div>
      )}

      {/* ── Range selector ───────────────────────────────────────────────── */}
      <div className="flex items-center gap-1 bg-bg-elevated rounded-lg p-0.5 w-fit">
        {(['7d', '30d', '90d'] as const).map(r => (
          <button
            key={r}
            onClick={() => setPriceRange(r)}
            className={clsx(
              'px-4 py-1.5 rounded text-xs font-medium transition-all',
              priceRange === r
                ? 'bg-accent text-white'
                : 'text-text-secondary hover:text-text-primary',
            )}
          >
            {r === '7d' ? '1W' : r === '30d' ? '1M' : '3M'}
          </button>
        ))}
      </div>

      {chartPrices.length === 0 && !loadingData ? (
        <div className="card py-16 text-center">
          <p className="text-sm text-text-muted">No price data available for this company.</p>
        </div>
      ) : (
        <>
          {/* TradingView-style price and volume chart */}
          <div className="card space-y-2">
            <SectionTitle icon={TrendingUp}>Price Action</SectionTitle>
            <div className="h-[560px]">
              <KlinePriceChart
                prices={chartPrices}
                symbol={company?.symbol ?? ''}
                anomalyDates={anomalyDates}
                rvol={rvolData}
                rvolThresholds={RVOL_THRESHOLDS}
              />
            </div>
          </div>

          <VolumeAnomalyChart data={volumeAnomalies} loading={loadingVolumeAnomalies} error={volumeAnomalyError} />
          <NewsSentimentScatter data={newsForward} priceData={chartPrices} loading={loadingNewsForward} error={newsForwardError} />

          {/* ── Row 3: Behavior AI summary ───────────────────────────────── */}
          {behavior && (
            <div className="card">
              <SectionTitle icon={Activity}>Behavior Analysis Summary</SectionTitle>
              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3 mb-4">
                <div className="bg-bg-elevated rounded-lg p-3">
                  <p className="text-[10px] text-text-muted uppercase tracking-wider mb-1">Pressure</p>
                  <p className={clsx('text-sm font-semibold capitalize',
                    behavior.pressure === 'buying' ? 'text-up'
                    : behavior.pressure === 'selling' ? 'text-down'
                    : 'text-text-secondary')}>
                    {behavior.pressure === 'buying' ? '▲ ' : behavior.pressure === 'selling' ? '▼ ' : '— '}
                    {behavior.pressure}
                  </p>
                </div>
                <div className="bg-bg-elevated rounded-lg p-3">
                  <p className="text-[10px] text-text-muted uppercase tracking-wider mb-1">Volume Anomaly</p>
                  <p className={clsx('text-sm font-semibold', behavior.volume_anomaly ? 'text-down' : 'text-up')}>
                    {behavior.volume_anomaly ? `⚡ Yes (${behavior.volume_ratio !== null ? Number(behavior.volume_ratio).toFixed(2) : '?'}×)` : '✓ Normal'}
                  </p>
                </div>
                <div className="bg-bg-elevated rounded-lg p-3">
                  <p className="text-[10px] text-text-muted uppercase tracking-wider mb-1">News Sentiment</p>
                  <p className={clsx('text-sm font-semibold',
                    behavior.news_sentiment_score > 0.1 ? 'text-up'
                    : behavior.news_sentiment_score < -0.1 ? 'text-down'
                    : 'text-text-secondary')}>
                    {behavior.news_sentiment_score.toFixed(3)} ({behavior.news_count_30d} articles)
                  </p>
                </div>
                <div className="bg-bg-elevated rounded-lg p-3">
                  <p className="text-[10px] text-text-muted uppercase tracking-wider mb-1">Spread vs VWAP</p>
                  <p className={clsx('text-sm font-semibold',
                    behavior.price_to_vwap_spread_pct === null ? 'text-text-secondary'
                    : behavior.price_to_vwap_spread_pct >= 0 ? 'text-up' : 'text-down')}>
                    {behavior.price_to_vwap_spread_pct !== null
                      ? `${behavior.price_to_vwap_spread_pct >= 0 ? '+' : ''}${behavior.price_to_vwap_spread_pct.toFixed(2)}%`
                      : '—'}
                  </p>
                </div>
              </div>
              <p className="text-sm text-text-secondary leading-relaxed border-l-2 border-accent-dim pl-3">
                {behavior.summary_text}
              </p>
            </div>
          )}

          {/* Categorized articles tagged to the selected company */}
          <div className="card">
            <div className="mb-3 flex items-center justify-between gap-3">
              <SectionTitle icon={Newspaper}>{company?.symbol ?? 'Company'} News</SectionTitle>
              <span className="text-[10px] text-text-muted">{categorizedNews?.length ?? 0} categorized articles</span>
            </div>
            {categorizedNews === null ? (
              <p className="py-4 text-center text-xs text-text-muted">
                {loadingData ? 'Loading categorized company news…' : 'Unable to load categorized news.'}
              </p>
            ) : categorizedNews.length === 0 ? (
              <p className="py-4 text-center text-xs text-text-muted">
                No categorized news is linked to this company yet.
              </p>
            ) : (
              <div className="divide-y divide-bg-border">
                {categorizedNews.map(article => (
                  <article key={article.id} className="flex flex-wrap items-start justify-between gap-3 py-3 first:pt-0 last:pb-0">
                    <div className="min-w-0 flex-1">
                      <a href={article.url} target="_blank" rel="noreferrer" className="text-sm font-medium text-text-primary hover:text-accent-light">
                        {article.headline}
                      </a>
                      <p className="mt-1 text-[10px] text-text-muted">
                        {article.source}{article.published_at ? ` · ${new Date(article.published_at).toLocaleString()}` : ''}
                        {' · '}Company match {Math.round(article.confidence * 100)}%{article.is_manual ? ' · Manually categorized' : ''}
                      </p>
                    </div>
                    <span className={clsx(
                      'rounded px-2 py-1 text-[10px] uppercase',
                      article.sentiment_label === 'positive' ? 'bg-up/10 text-up'
                        : article.sentiment_label === 'negative' ? 'bg-down/10 text-down'
                        : 'bg-bg-elevated text-text-muted',
                    )}>
                      {article.sentiment_label || 'Sentiment unavailable'}
                    </span>
                  </article>
                ))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}