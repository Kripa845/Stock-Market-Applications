// import { useMemo, type ReactNode } from 'react';
// import { useSearchParams } from 'react-router-dom';
// import { isAxiosError } from 'axios';
// import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
// import { AlertTriangle, Info, Loader2, Plus, X } from 'lucide-react';
// import clsx from 'clsx';

// import PageHeader from '../components/common/PageHeader';
// import EmptyState from '../components/common/EmptyState';
// import Sparkline from '../components/common/Sparkline';
// import { selectClass } from '../components/market/TopListControls';
// import { seriesColor } from '../components/brokers/position/format';
// import {
//   changeTone, formatCount, formatNprArab, formatPct, formatPrice, formatTradeDate,
// } from '../components/market/format';
// import { useCompare, useCompareCompanies } from '../hooks/useCompare';
// import {
//   MAX_SYMBOLS, MIN_SYMBOLS, NULL_REASON_LABELS,
//   type BrokerRow, type CompareError, type CompareProfile,
// } from '../api/compare';

// // Stock comparison (/compare?symbols=ADBL,CHCL).  2-5 tracked companies side by side; every
// // number comes from /api/compare/.  A missing figure shows "—" with the backend's reason.

// type Num = number | string | null | undefined;
// const toNumber = (value: Num) => (value === null || value === undefined || value === '' ? null : Number(value));

// const GRID = 'var(--trading-grid)';
// const MUTED = 'var(--trading-muted)';

// /** 6.88% without a sign (ratios, yields); formatPct adds one for changes. */
// function plainPct(value: Num) {
//   const n = toNumber(value);
//   return n === null || Number.isNaN(n) ? '—' : `${n.toFixed(2)}%`;
// }

// function ratio(value: Num) {
//   const n = toNumber(value);
//   return n === null || Number.isNaN(n) ? '—' : n.toFixed(2);
// }

// interface MetricRow {
//   label: string;
//   /** Path in data_quality.null_fields, e.g. "fundamentals.pe". */
//   field: string;
//   value: (p: CompareProfile) => Num;
//   format: (value: Num) => string;
//   /** Highlight the best non-null value. */
//   best?: 'high' | 'low';
//   hint?: string;
// }

// const SECTIONS: { title: string; rows: MetricRow[] }[] = [
//   {
//     title: 'Price',
//     rows: [
//       { label: 'LTP', field: 'general.ltp', value: (p) => p.general.ltp, format: formatPrice },
//       { label: 'Previous close', field: 'general.previous_close', value: (p) => p.general.previous_close, format: formatPrice },
//       { label: 'Change', field: 'general.change_pct', value: (p) => p.general.change_pct, format: (v) => formatPct(v) },
//       { label: '52-week low', field: 'general.week52_low', value: (p) => p.general.week52_low, format: formatPrice },
//       { label: '52-week high', field: 'general.week52_high', value: (p) => p.general.week52_high, format: formatPrice },
//     ],
//   },
//   {
//     title: 'Size',
//     rows: [
//       { label: 'Market cap', field: 'general.market_cap', value: (p) => p.general.market_cap, format: (v) => formatNprArab(v) },
//       { label: 'Listed shares', field: 'general.listed_shares', value: (p) => p.general.listed_shares, format: formatCount },
//       { label: 'Paid-up capital', field: 'general.paid_up_capital', value: (p) => p.general.paid_up_capital, format: (v) => formatNprArab(v),
//         hint: 'Listed shares × face value' },
//       { label: 'Reserve & surplus', field: 'general.reserve_surplus', value: (p) => p.general.reserve_surplus, format: (v) => formatNprArab(v),
//         hint: 'Book value × listed shares − paid-up capital' },
//     ],
//   },
//   {
//     title: 'Valuation',
//     rows: [
//       { label: 'EPS (TTM)', field: 'general.eps_ttm', value: (p) => p.general.eps_ttm, format: formatPrice, best: 'high' },
//       { label: 'EPS (as filed)', field: 'general.eps_reported', value: (p) => p.general.eps_reported, format: formatPrice },
//       { label: 'P/E', field: 'fundamentals.pe', value: (p) => p.fundamentals.pe, format: ratio, best: 'low' },
//       { label: 'P/B', field: 'fundamentals.pb', value: (p) => p.fundamentals.pb, format: ratio, best: 'low' },
//       { label: 'ROE', field: 'fundamentals.roe', value: (p) => p.fundamentals.roe, format: plainPct, best: 'high' },
//       { label: 'Dividend (total)', field: 'fundamentals.dividend', value: (p) => p.fundamentals.dividend?.total_pct ?? null, format: plainPct },
//       { label: 'Dividend yield', field: 'fundamentals.dividend_yield', value: (p) => p.fundamentals.dividend_yield, format: plainPct, best: 'high',
//         hint: '(Cash + bonus) × face value / LTP' },
//       { label: 'P/S', field: 'fundamentals.ps', value: (p) => p.fundamentals.ps, format: ratio },
//       { label: 'ROA', field: 'fundamentals.roa', value: (p) => p.fundamentals.roa, format: plainPct },
//       { label: 'Debt / equity', field: 'fundamentals.debt_equity', value: (p) => p.fundamentals.debt_equity, format: ratio },
//       { label: 'YoY profit growth', field: 'fundamentals.yoy_profit_growth', value: (p) => p.fundamentals.yoy_profit_growth, format: plainPct },
//       { label: 'PEG', field: 'fundamentals.peg', value: (p) => p.fundamentals.peg, format: ratio },
//     ],
//   },
//   {
//     title: 'Technicals',
//     rows: [
//       { label: 'RSI (14)', field: 'technicals.rsi', value: (p) => p.technicals.rsi, format: ratio },
//       { label: 'MACD', field: 'technicals.macd', value: (p) => p.technicals.macd, format: ratio },
//       { label: 'MACD signal', field: 'technicals.macd_signal', value: (p) => p.technicals.macd_signal, format: ratio },
//       { label: 'SMA 50', field: 'technicals.sma50', value: (p) => p.technicals.sma50?.value ?? null, format: formatPrice },
//       { label: 'SMA 200', field: 'technicals.sma200', value: (p) => p.technicals.sma200?.value ?? null, format: formatPrice },
//     ],
//   },
// ];

// function parseSymbols(raw: string | null) {
//   const seen = new Set<string>();
//   return (raw ?? '').split(',').map((s) => s.trim().toUpperCase())
//     .filter((s) => s && !seen.has(s) && seen.add(s)).slice(0, MAX_SYMBOLS);
// }

// function errorMessage(error: unknown) {
//   if (isAxiosError<CompareError>(error) && error.response?.data?.detail) return error.response.data.detail;
//   return 'The comparison could not be loaded.';
// }

// export default function StockComparisonPage() {
//   const [params, setParams] = useSearchParams();
//   const symbols = useMemo(() => parseSymbols(params.get('symbols')), [params]);
//   const companies = useCompareCompanies();
//   const compare = useCompare(symbols);

//   const setSymbols = (next: string[]) => {
//     const updated = new URLSearchParams(params);
//     if (next.length) updated.set('symbols', next.join(','));
//     else updated.delete('symbols');
//     setParams(updated, { replace: true });
//   };

//   const profiles = symbols.length >= MIN_SYMBOLS ? compare.data?.results ?? [] : [];
//   const slot = (symbol: string) => Math.max(0, symbols.indexOf(symbol));

//   return (
//     <div className="space-y-4">
//       <PageHeader title="Stock Comparison"
//         subtitle="Compare 2 to 5 tracked companies side by side, from crawled prices, filings and the floorsheet" />

//       <Picker symbols={symbols} onChange={setSymbols} companies={companies.data?.results ?? []}
//         loading={companies.isPending} />

//       {symbols.length < MIN_SYMBOLS ? (
//         <div className="card">
//           <EmptyState title="Pick at least two companies"
//             description={`Add ${MIN_SYMBOLS} to ${MAX_SYMBOLS} tracked companies above to compare them.`} />
//         </div>
//       ) : compare.isError ? (
//         <div className="card flex items-start gap-3 text-sm text-down">
//           <AlertTriangle size={18} className="mt-0.5 shrink-0" />
//           <p>{errorMessage(compare.error)}</p>
//         </div>
//       ) : compare.isPending ? (
//         <div className="card flex items-center justify-center gap-2 py-16 text-sm text-text-secondary">
//           <Loader2 size={16} className="animate-spin" /> Loading comparison…
//         </div>
//       ) : (
//         <>
//           <SummaryCards profiles={profiles} slot={slot} />
//           <TrendChart profiles={profiles} slot={slot} />
//           <MetricsTable profiles={profiles} slot={slot} />
//           <BrokersSection profiles={profiles} slot={slot} />
//           <DataNotes profiles={profiles} />
//         </>
//       )}
//     </div>
//   );
// }

// function Picker({ symbols, onChange, companies, loading }: {
//   symbols: string[]; onChange: (next: string[]) => void;
//   companies: { symbol: string; name: string; sector: string }[]; loading: boolean;
// }) {
//   const bySector = useMemo(() => {
//     const groups = new Map<string, typeof companies>();
//     companies.filter((c) => !symbols.includes(c.symbol)).forEach((c) => {
//       groups.set(c.sector, [...(groups.get(c.sector) ?? []), c]);
//     });
//     return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b));
//   }, [companies, symbols]);
//   const full = symbols.length >= MAX_SYMBOLS;

//   return (
//     <div className="card flex flex-wrap items-center gap-2">
//       {symbols.map((symbol, i) => (
//         <span key={symbol}
//           className="inline-flex items-center gap-1.5 rounded-full border border-bg-border bg-bg-border py-1 pl-2.5 pr-1 text-xs font-semibold text-text-primary">
//           <span className="h-2 w-2 rounded-full" style={{ background: seriesColor(i) }} />
//           {symbol}
//           <button type="button" aria-label={`Remove ${symbol}`} onClick={() => onChange(symbols.filter((s) => s !== symbol))}
//             className="rounded-full p-0.5 text-text-muted hover:bg-bg-card hover:text-text-primary">
//             <X size={12} />
//           </button>
//         </span>
//       ))}
//       <label className="inline-flex items-center gap-1.5 text-xs text-text-secondary">
//         <Plus size={14} />
//         <select value="" disabled={full || loading} aria-label="Add a company"
//           onChange={(e) => e.target.value && onChange([...symbols, e.target.value])}
//           className={`${selectClass} min-w-[170px]`}>
//           <option value="">{loading ? 'Loading…' : full ? `Up to ${MAX_SYMBOLS} companies` : 'Add company'}</option>
//           {bySector.map(([sector, list]) => (
//             <optgroup key={sector} label={sector}>
//               {list.map((c) => <option key={c.symbol} value={c.symbol}>{c.symbol} · {c.name}</option>)}
//             </optgroup>
//           ))}
//         </select>
//       </label>
//       {symbols.length > 0 && (
//         <button type="button" onClick={() => onChange([])} className="ml-auto text-xs text-text-muted hover:text-text-primary">
//           Clear
//         </button>
//       )}
//     </div>
//   );
// }

// function SummaryCards({ profiles, slot }: { profiles: CompareProfile[]; slot: (s: string) => number }) {
//   return (
//     <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">
//       {profiles.map((p) => {
//         if (p.error) {
//           return (
//             <div key={p.symbol} className="card text-sm">
//               <p className="font-semibold text-text-primary">{p.symbol}</p>
//               <p className="mt-1 text-xs text-down">{p.detail}</p>
//             </div>
//           );
//         }
//         const tone = changeTone(p.general.change_pct);
//         return (
//           <div key={p.symbol} className="card space-y-1">
//             <div className="flex items-center gap-2">
//               <span className="h-2.5 w-2.5 rounded-full" style={{ background: seriesColor(slot(p.symbol)) }} />
//               <span className="font-semibold text-text-primary">{p.symbol}</span>
//               <span className="ml-auto truncate text-[11px] text-text-muted">{p.sector}</span>
//             </div>
//             <p className="truncate text-xs text-text-secondary" title={p.name}>{p.name}</p>
//             <p className="font-mono text-lg font-semibold text-text-primary">
//               {formatPrice(p.general.ltp)}
//               <span className={clsx('ml-2 text-sm', tone === 'up' && 'text-up', tone === 'down' && 'text-down',
//                 tone === 'flat' && 'text-text-muted')}>
//                 {formatPct(p.general.change_pct)}
//               </span>
//             </p>
//             <p className="text-[11px] text-text-muted">
//               Close of {formatTradeDate(p.data_quality.price_as_of)}
//               {p.general.ltp_source === 'company_live_feed' && ' · live feed'}
//             </p>
//           </div>
//         );
//       })}
//     </div>
//   );
// }

// function TrendChart({ profiles, slot }: { profiles: CompareProfile[]; slot: (s: string) => number }) {
//   // Each line is % change from that company's first close in the window, so prices of
//   // different sizes share one axis.
//   const { rows, series } = useMemo(() => {
//     const byDate = new Map<string, Record<string, number | string>>();
//     const series: string[] = [];
//     profiles.forEach((p) => {
//       const points = p.error ? null : p.general.price_trend_3m;
//       const base = toNumber(points?.[0]?.close);
//       if (!points || !base) return;
//       series.push(p.symbol);
//       points.forEach((point) => {
//         const close = toNumber(point.close);
//         if (close === null) return;
//         const row = byDate.get(point.date) ?? { date: point.date };
//         row[p.symbol] = ((close - base) / base) * 100;
//         byDate.set(point.date, row);
//       });
//     });
//     return { rows: [...byDate.values()].sort((a, b) => String(a.date).localeCompare(String(b.date))), series };
//   }, [profiles]);

//   return (
//     <div className="card">
//       <h2 className="mb-3 text-sm font-semibold text-text-primary">3-month price trend <span className="font-normal text-text-muted">(% from first close)</span></h2>
//       {rows.length === 0 ? (
//         <p className="py-8 text-center text-xs text-text-muted">No crawled prices in the last 3 months.</p>
//       ) : (
//         <div className="h-64">
//           <ResponsiveContainer width="100%" height="100%">
//             <LineChart data={rows} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
//               <CartesianGrid stroke={GRID} vertical={false} />
//               <XAxis dataKey="date" tick={{ fill: MUTED, fontSize: 11 }} tickLine={false} axisLine={false} minTickGap={40}
//                 tickFormatter={(d: string) => formatTradeDate(d).replace(/ \d{4}$/, '')} />
//               <YAxis tick={{ fill: MUTED, fontSize: 11 }} tickLine={false} axisLine={false} width={48}
//                 tickFormatter={(v: number) => `${v.toFixed(0)}%`} />
//               <Tooltip content={<TrendTooltip />} />
//               {series.map((symbol) => (
//                 <Line key={symbol} dataKey={symbol} stroke={seriesColor(slot(symbol))} dot={false} strokeWidth={1.75}
//                   connectNulls isAnimationActive={false} />
//               ))}
//             </LineChart>
//           </ResponsiveContainer>
//         </div>
//       )}
//     </div>
//   );
// }

// function TrendTooltip({ active, label, payload }: {
//   active?: boolean; label?: string; payload?: { dataKey: string; value: number; color: string }[];
// }) {
//   if (!active || !payload?.length || !label) return null;
//   return (
//     <div className="min-w-[150px] rounded-lg border border-bg-border bg-bg-elevated px-3 py-2 text-xs shadow-xl">
//       <p className="mb-1.5 font-semibold text-text-muted">{formatTradeDate(label)}</p>
//       {[...payload].sort((a, b) => b.value - a.value).map((row) => (
//         <p key={row.dataKey} className="flex items-center gap-2 py-0.5 font-mono">
//           <span className="h-2 w-2 rounded-full" style={{ background: row.color }} />
//           <span className="font-sans text-text-secondary">{row.dataKey}</span>
//           <span className="ml-auto pl-4 text-text-primary">{formatPct(row.value)}</span>
//         </p>
//       ))}
//     </div>
//   );
// }

// function nullReason(p: CompareProfile, field: string) {
//   const entry = p.data_quality.null_fields.find((e) => e.field === field);
//   return entry ? NULL_REASON_LABELS[entry.reason] ?? entry.reason : null;
// }

// function bestSymbol(row: MetricRow, profiles: CompareProfile[]) {
//   if (!row.best) return null;
//   const values = profiles.filter((p) => !p.error)
//     .map((p) => ({ symbol: p.symbol, n: toNumber(row.value(p)) }))
//     .filter((v): v is { symbol: string; n: number } => v.n !== null && !Number.isNaN(v.n));
//   if (values.length < 2) return null;
//   values.sort((a, b) => (row.best === 'high' ? b.n - a.n : a.n - b.n));
//   return values[0].n === values[1].n ? null : values[0].symbol;
// }

// // function MetricsTable({ profiles, slot }: { profiles: CompareProfile[]; slot: (s: string) => number }) {
// //   const ok = profiles.filter((p) => !p.error);
// //   if (ok.length === 0) return null;
// //   const cell = 'px-3 py-2 text-right';
// //   return (
// //     <div className="card overflow-x-auto !p-0">
// //       <table className="w-full min-w-[640px] table-fixed text-xs">
// //         <thead>
// //           <tr className="border-b border-bg-border bg-bg-card text-text-secondary">
// //             <th className="sticky left-0 bg-bg-card px-3 py-2.5 text-left font-semibold">Metric</th>
// //             {ok.map((p) => (
// //               <th key={p.symbol} className={clsx(cell, 'font-semibold text-text-primary')}>
// //                 <span className="inline-flex items-center gap-1.5">
// //                   <span className="h-2 w-2 rounded-full" style={{ background: seriesColor(slot(p.symbol)) }} />
// //                   {p.symbol}
// //                 </span>
// //               </th>
// //             ))}
// //           </tr>
// //         </thead>
// //         <tbody>
// //           {SECTIONS.map((section) => (
// //             <SectionRows key={section.title} title={section.title} rows={section.rows} profiles={ok} span={ok.length + 1} />
// //           ))}
// //           <tr className="border-t border-bg-border">
// //             <td className="sticky left-0 bg-bg-card px-3 py-2 text-text-secondary">MACD trend</td>
// //             {ok.map((p) => (
// //               <td key={p.symbol} className={clsx(cell, 'font-semibold',
// //                 p.technicals.macd_label === 'Bullish' ? 'text-up' : p.technicals.macd_label === 'Bearish' ? 'text-down' : 'text-text-muted')}>
// //                 {p.technicals.macd_label ?? '—'}
// //               </td>
// //             ))}
// //           </tr>
// //           {(['sma50', 'sma200'] as const).map((key) => (
// //             <tr key={key} className="border-t border-bg-border">
// //               <td className="sticky left-0 bg-bg-card px-3 py-2 text-text-secondary">LTP vs {key === 'sma50' ? 'SMA 50' : 'SMA 200'}</td>
// //               {ok.map((p) => {
// //                 const block = p.technicals[key];
// //                 return (
// //                   <td key={p.symbol} className="px-6 py-2 text-right">
// //                     {block ? (block.above ? 'Above' : 'Below') : '—'}
// //                   </td>
// //                 );
// //               })}
// //             </tr>
// //           ))}
// //           <tr className="border-t border-bg-border">
// //             <td className="sticky left-0 bg-bg-card px-3 py-2 text-text-secondary">Volume, last 10 sessions</td>
// //             {ok.map((p) => {
// //               const volumes = (p.technicals.volume_trend ?? []).map((v) => v.volume);
// //               return (
// //                 <td key={p.symbol} className={cell}>
// //                   {volumes.length >= 2 ? (
// //                     <span className="inline-flex flex-col items-end gap-0.5">
// //                       <Sparkline data={volumes} width={88} height={24} positive={volumes[volumes.length - 1] >= volumes[0]} />
// //                       <span className="font-mono text-[11px] text-text-muted">{formatCount(volumes[volumes.length - 1])}</span>
// //                     </span>
// //                   ) : '—'}
// //                 </td>
// //               );
// //             })}
// //           </tr>
// //         </tbody>
// //       </table>
// //     </div>
// //   );
// // }
// const LABEL_W = 168; // px, Metric column
// const COL_W = 112;   // px, min per symbol column
// const labelCell =
//   'sticky left-0 z-10 truncate border-r border-bg-border bg-bg-card px-3 py-2 text-left text-text-secondary';
// const valueCell = 'px-3 py-2 text-right align-middle tabular-nums';

// function SimpleRow({ label, profiles, render }: {
//   label: string;
//   profiles: CompareProfile[];
//   render: (p: CompareProfile) => ReactNode;
// }) {
//   return (
//     <tr className="border-t border-bg-border">
//       <td className={labelCell} title={label}>{label}</td>
//       {profiles.map((p) => (
//         <td key={p.symbol} className={valueCell}>{render(p)}</td>
//       ))}
//     </tr>
//   );
// }
// const dash = <span className="font-mono text-text-muted">—</span>;

// function MetricsTable({ profiles, slot }: { profiles: CompareProfile[]; slot: (s: string) => number }) {
//   const ok = profiles.filter((p) => !p.error);
//   if (ok.length === 0) return null;

//   return (
//     <div className="card overflow-x-auto !p-0">
//       <table
//         className="w-full table-fixed text-xs"
//         style={{ minWidth: LABEL_W + ok.length * COL_W }}
//       >
//         <colgroup>
//           <col style={{ width: LABEL_W }} />
//           {ok.map((p) => (
//             <col key={p.symbol} />
//           ))}
//         </colgroup>

//         <thead>
//           <tr className="border-b border-bg-border bg-bg-card text-text-secondary">
//             <th className="sticky left-0 z-20 border-r border-bg-border bg-bg-card px-3 py-2.5 text-left font-semibold">
//               Metric
//             </th>
//             {ok.map((p) => (
//               <th key={p.symbol} className="px-3 py-2.5 text-right font-semibold text-text-primary">
//                 <span className="inline-flex max-w-full items-center justify-end gap-1.5">
//                   <span
//                     className="h-2 w-2 shrink-0 rounded-full"
//                     style={{ background: seriesColor(slot(p.symbol)) }}
//                   />
//                   <span className="truncate" title={p.symbol}>{p.symbol}</span>
//                 </span>
//               </th>
//             ))}
//           </tr>
//         </thead>

//         <tbody>
//           {SECTIONS.map((section) => (
//             <SectionRows
//               key={section.title}
//               title={section.title}
//               rows={section.rows}
//               profiles={ok}
//               span={ok.length + 1}
//             />
//           ))}

//           <SimpleRow
//             label="MACD trend"
//             profiles={ok}
//             render={(p) => {
//               const l = p.technicals.macd_label;
//               return (
//                 <span
//                   className={clsx(
//                     'font-semibold',
//                     l === 'Bullish' ? 'text-up' : l === 'Bearish' ? 'text-down' : 'text-text-muted',
//                   )}
//                 >
//                   {l ?? '—'}
//                 </span>
//               );
//             }}
//           />

//           {(['sma50', 'sma200'] as const).map((key) => (
//             <SimpleRow
//               key={key}
//               label={`LTP vs ${key === 'sma50' ? 'SMA 50' : 'SMA 200'}`}
//               profiles={ok}
//               render={(p) => {
//                 const block = p.technicals[key];
//                 if (!block) return <span className="text-text-muted">—</span>;
//                 return (
//                   <span className={clsx('font-semibold', block.above ? 'text-up' : 'text-down')}>
//                     {block.above ? 'Above' : 'Below'}
//                   </span>
//                 );
//               }}
//             />
//           ))}

//           <SimpleRow
//             label="Volume (10 sessions)"
//             profiles={ok}
//             render={(p) => {
//               const volumes = (p.technicals.volume_trend ?? []).map((v) => v.volume);
//               if (volumes.length < 2) return <span className="text-text-muted">—</span>;
//               return (
//                 <span className="inline-flex flex-col items-end gap-0.5">
//                   <Sparkline
//                     data={volumes}
//                     width={80}
//                     height={24}
//                     positive={volumes[volumes.length - 1] >= volumes[0]}
//                   />
//                   <span className="font-mono text-[11px] text-text-muted">
//                     {formatCount(volumes[volumes.length - 1])}
//                   </span>
//                 </span>
//               );
//             }}
//           />
//         </tbody>
//       </table>
//     </div>
//   );
// }
// // function SectionRows({ title, rows, profiles, span }: { title: string; rows: MetricRow[]; profiles: CompareProfile[]; span: number }) {
// //   return (
// //     <>
// //       <tr className="bg-bg-card text-text-secondary">
// //         <td colSpan={span} className="px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-text-secondary">{title}</td>
// //       </tr>
// //       {rows.map((row) => {
// //         const best = bestSymbol(row, profiles);
// //         return (
// //           <tr key={row.field} className="border-t border-bg-border">
// //             <td className={labelCell} title={row.hint}>
// //               {row.label}
// //             </td>
// //             {profiles.map((p) => {
// //               const value = row.value(p);
// //               const reason = toNumber(value) === null ? nullReason(p, row.field) : null;
// //               return (
// //                 <td key={p.symbol} className={valueCell}>
// //                   {reason !== null || toNumber(value) === null ? (
// //                     <span className="inline-flex flex-col items-end">
// //                       <span className="font-mono text-text-muted">—</span>
// //                       {reason && <span className="text-[10px] text-text-muted">{reason}</span>}
// //                     </span>
// //                   ) : (
// //                     <span className={clsx('font-mono', best === p.symbol ? 'font-semibold text-accent-light' : 'text-text-primary')}>
// //                       {row.format(value)}
// //                     </span>
// //                   )}
// //                 </td>
// //               );
// //             })}
// //           </tr>
// //         );
// //       })}
// //     </>
// //   );
// // }
// function SectionRows({ title, rows, profiles, span }: {
//   title: string; rows: MetricRow[]; profiles: CompareProfile[]; span: number;
// }) {
//   return (
//     <>
//       {/* Title lives in the sticky first cell so it stays visible on horizontal scroll */}
//       <tr className="border-t border-bg-border bg-purple-400">
//         <td className="sticky left-0 z-10 truncate bg-purple-400 px-3 py-1.5 text-left text-[11px] font-semibold uppercase tracking-wide text-white">{title}</td>
//         <td colSpan={span - 1} className="bg-purple-400" />
//       </tr>
//       {rows.map((row) => {
//         const best = bestSymbol(row, profiles);
//         return (
//           <tr key={row.field} className="border-t border-bg-border">
//             <td className={labelCell} title={row.hint ?? row.label}>{row.label}</td>
//             {profiles.map((p) => {
//               const value = row.value(p);
//               const missing = toNumber(value) === null;
//               const reason = missing ? nullReason(p, row.field) : null;
//               return (
//                 <td key={p.symbol} className={valueCell}>
//                   {missing ? (
//                     <span className="inline-flex max-w-full flex-col items-end">
//                       <span className="font-mono text-text-muted">—</span>
//                       {reason && (
//                         <span className="text-right text-[10px] leading-tight text-text-muted">{reason}</span>
//                       )}
//                     </span>
//                   ) : (
//                     <span className={clsx('font-mono',
//                       best === p.symbol ? 'font-semibold text-accent-light' : 'text-text-primary')}>
//                       {row.format(value)}
//                     </span>
//                   )}
//                 </td>
//               );
//             })}
//           </tr>
//         );
//       })}
//     </>
//   );
// }
// function BrokerList({ title, rows }: { title: string; rows: BrokerRow[] | null }) {
//   return (
//     <div>
//       <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-text-muted">{title}</p>
//       {!rows?.length ? <p className="text-xs text-text-muted">—</p> : (
//         <ol className="space-y-0.5">
//           {rows.map((b) => (
//             <li key={String(b.broker_no)} className="flex items-baseline gap-2 text-xs">
//               <span className="w-7 font-mono text-text-primary">{b.broker_no}</span>
//               <span className="min-w-0 flex-1 truncate text-text-secondary" title={b.broker_name ?? undefined}>{b.broker_name ?? 'Unknown broker'}</span>
//               <span className="font-mono text-text-muted">{plainPct(b.pct_of_day_volume)}</span>
//             </li>
//           ))}
//         </ol>
//       )}
//     </div>
//   );
// }

// function BrokersSection({ profiles, slot }: { profiles: CompareProfile[]; slot: (s: string) => number }) {
//   const ok = profiles.filter((p) => !p.error);
//   if (ok.length === 0) return null;
//   return (
//     <div className="card">
//       <h2 className="mb-3 text-sm font-semibold text-text-primary">Top brokers <span className="font-normal text-text-muted">(share of the day's volume)</span></h2>
//       <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
//         {ok.map((p) => (
//           <div key={p.symbol} className="space-y-3 rounded-lg border border-bg-border p-3">
//             <p className="flex items-center gap-2 text-xs font-semibold text-text-primary">
//               <span className="h-2 w-2 rounded-full" style={{ background: seriesColor(slot(p.symbol)) }} />
//               {p.symbol}
//               <span className="ml-auto font-normal text-text-muted">{formatTradeDate(p.general.brokers_date)}</span>
//             </p>
//             <BrokerList title="Buyers" rows={p.general.top_buy_brokers} />
//             <BrokerList title="Sellers" rows={p.general.top_sell_brokers} />
//           </div>
//         ))}
//       </div>
//     </div>
//   );
// }

// function DataNotes({ profiles }: { profiles: CompareProfile[] }) {
//   const ok = profiles.filter((p) => !p.error);
//   const sectorNote = ok.flatMap((p) => p.data_quality.null_fields).find((e) => e.note)?.note;
//   const anyWarnings = ok.some((p) => p.data_quality.warnings.length > 0);
//   if (!anyWarnings && !sectorNote) return null;
//   return (
//     <div className="card space-y-3 text-xs">
//       <h2 className="flex items-center gap-2 text-sm font-semibold text-text-primary"><Info size={15} /> Data notes</h2>
//       {sectorNote && <p className="text-text-secondary">{sectorNote}</p>}
//       {ok.map((p) => p.data_quality.warnings.length > 0 && (
//         <div key={p.symbol}>
//           <p className="font-semibold text-text-primary">{p.symbol}</p>
//           <ul className="mt-1 list-disc space-y-0.5 pl-5 text-text-secondary">
//             {p.data_quality.warnings.map((w) => (
//               <li key={w.code}>
//                 {w.detail}
//                 {w.sessions && ` (${w.sessions.map((s) => formatTradeDate(s.date)).join(', ')})`}
//               </li>
//             ))}
//           </ul>
//         </div>
//       ))}
//       <p className="text-text-muted">Tracked companies only. Prices are crawled closes, not adjusted for bonus or right shares.</p>
//     </div>
//   );
// }
import { useMemo, type ReactNode } from 'react';
import { useSearchParams } from 'react-router-dom';
import { isAxiosError } from 'axios';
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { AlertTriangle, ArrowDownRight, ArrowUpRight, Info, Loader2, Minus, Plus, X } from 'lucide-react';
import clsx from 'clsx';

import PageHeader from '../components/common/PageHeader';
import EmptyState from '../components/common/EmptyState';
import Sparkline from '../components/common/Sparkline';
import { selectClass } from '../components/market/TopListControls';
import { seriesColor } from '../components/brokers/position/format';
import {
  changeTone, formatCount, formatNprArab, formatPct, formatPrice, formatTradeDate,
} from '../components/market/format';
import { useCompare, useCompareCompanies } from '../hooks/useCompare';
import {
  MAX_SYMBOLS, MIN_SYMBOLS, NULL_REASON_LABELS,
  type BrokerRow, type CompareError, type CompareProfile,
} from '../api/compare';

// Stock comparison (/compare?symbols=ADBL,CHCL).  2-5 tracked companies side by side; every
// number comes from /api/compare/.  A missing figure shows "—" with the backend's reason.

type Num = number | string | null | undefined;
const toNumber = (value: Num) => (value === null || value === undefined || value === '' ? null : Number(value));

const GRID = 'var(--trading-grid)';
const MUTED = 'var(--trading-muted)';

/** 6.88% without a sign (ratios, yields); formatPct adds one for changes. */
function plainPct(value: Num) {
  const n = toNumber(value);
  return n === null || Number.isNaN(n) ? '—' : `${n.toFixed(2)}%`;
}

function ratio(value: Num) {
  const n = toNumber(value);
  return n === null || Number.isNaN(n) ? '—' : n.toFixed(2);
}

interface MetricRow {
  label: string;
  /** Path in data_quality.null_fields, e.g. "fundamentals.pe". */
  field: string;
  value: (p: CompareProfile) => Num;
  format: (value: Num) => string;
  /** Highlight the best non-null value. */
  best?: 'high' | 'low';
  /**
   * Draw a small comparison bar under the value.  `true` scales to the largest value in the
   * group; a number scales to that fixed maximum (e.g. 100 for RSI).  Negative values get no bar.
   */
  bar?: boolean | number;
  hint?: string;
}

const SECTIONS: { title: string; rows: MetricRow[] }[] = [
  {
    title: 'Price',
    rows: [
      { label: 'LTP', field: 'general.ltp', value: (p) => p.general.ltp, format: formatPrice },
      { label: 'Previous close', field: 'general.previous_close', value: (p) => p.general.previous_close, format: formatPrice },
      { label: 'Change', field: 'general.change_pct', value: (p) => p.general.change_pct, format: (v) => formatPct(v) },
      { label: '52-week low', field: 'general.week52_low', value: (p) => p.general.week52_low, format: formatPrice },
      { label: '52-week high', field: 'general.week52_high', value: (p) => p.general.week52_high, format: formatPrice },
    ],
  },
  {
    title: 'Size',
    rows: [
      { label: 'Market cap', field: 'general.market_cap', value: (p) => p.general.market_cap, format: (v) => formatNprArab(v) },
      { label: 'Listed shares', field: 'general.listed_shares', value: (p) => p.general.listed_shares, format: formatCount },
      { label: 'Paid-up capital', field: 'general.paid_up_capital', value: (p) => p.general.paid_up_capital, format: (v) => formatNprArab(v),
        hint: 'Listed shares × face value' },
      { label: 'Reserve & surplus', field: 'general.reserve_surplus', value: (p) => p.general.reserve_surplus, format: (v) => formatNprArab(v),
        hint: 'Book value × listed shares − paid-up capital' },
    ],
  },
  {
    title: 'Valuation',
    rows: [
      { label: 'EPS (TTM)', field: 'general.eps_ttm', value: (p) => p.general.eps_ttm, format: formatPrice, best: 'high', bar: true },
      { label: 'EPS (as filed)', field: 'general.eps_reported', value: (p) => p.general.eps_reported, format: formatPrice, bar: true },
      { label: 'P/E', field: 'fundamentals.pe', value: (p) => p.fundamentals.pe, format: ratio, best: 'low', bar: true },
      { label: 'P/B', field: 'fundamentals.pb', value: (p) => p.fundamentals.pb, format: ratio, best: 'low', bar: true },
      { label: 'ROE', field: 'fundamentals.roe', value: (p) => p.fundamentals.roe, format: plainPct, best: 'high', bar: true },
      { label: 'Dividend (total)', field: 'fundamentals.dividend', value: (p) => p.fundamentals.dividend?.total_pct ?? null, format: plainPct, bar: true },
      { label: 'Dividend yield', field: 'fundamentals.dividend_yield', value: (p) => p.fundamentals.dividend_yield, format: plainPct, best: 'high', bar: true,
        hint: '(Cash + bonus) × face value / LTP' },
      { label: 'P/S', field: 'fundamentals.ps', value: (p) => p.fundamentals.ps, format: ratio },
      { label: 'ROA', field: 'fundamentals.roa', value: (p) => p.fundamentals.roa, format: plainPct },
      { label: 'Debt / equity', field: 'fundamentals.debt_equity', value: (p) => p.fundamentals.debt_equity, format: ratio },
      { label: 'YoY profit growth', field: 'fundamentals.yoy_profit_growth', value: (p) => p.fundamentals.yoy_profit_growth, format: plainPct },
      { label: 'PEG', field: 'fundamentals.peg', value: (p) => p.fundamentals.peg, format: ratio },
    ],
  },
  {
    title: 'Technicals',
    rows: [
      { label: 'RSI (14)', field: 'technicals.rsi', value: (p) => p.technicals.rsi, format: ratio, bar: 100 },
      { label: 'MACD', field: 'technicals.macd', value: (p) => p.technicals.macd, format: ratio },
      { label: 'MACD signal', field: 'technicals.macd_signal', value: (p) => p.technicals.macd_signal, format: ratio },
      { label: 'SMA 50', field: 'technicals.sma50', value: (p) => p.technicals.sma50?.value ?? null, format: formatPrice },
      { label: 'SMA 200', field: 'technicals.sma200', value: (p) => p.technicals.sma200?.value ?? null, format: formatPrice },
    ],
  },
];

function parseSymbols(raw: string | null) {
  const seen = new Set<string>();
  return (raw ?? '').split(',').map((s) => s.trim().toUpperCase())
    .filter((s) => s && !seen.has(s) && seen.add(s)).slice(0, MAX_SYMBOLS);
}

function errorMessage(error: unknown) {
  if (isAxiosError<CompareError>(error) && error.response?.data?.detail) return error.response.data.detail;
  return 'The comparison could not be loaded.';
}

export default function StockComparisonPage() {
  const [params, setParams] = useSearchParams();
  const symbols = useMemo(() => parseSymbols(params.get('symbols')), [params]);
  const companies = useCompareCompanies();
  const compare = useCompare(symbols);

  const setSymbols = (next: string[]) => {
    const updated = new URLSearchParams(params);
    if (next.length) updated.set('symbols', next.join(','));
    else updated.delete('symbols');
    setParams(updated, { replace: true });
  };

  const profiles = symbols.length >= MIN_SYMBOLS ? compare.data?.results ?? [] : [];
  const slot = (symbol: string) => Math.max(0, symbols.indexOf(symbol));

  return (
    <div className="space-y-4">
      <PageHeader title="Stock Comparison"
        subtitle="Compare 2 to 5 tracked companies side by side, from crawled prices, filings and the floorsheet" />

      <Picker symbols={symbols} onChange={setSymbols} companies={companies.data?.results ?? []}
        loading={companies.isPending} />

      {symbols.length < MIN_SYMBOLS ? (
        <div className="card">
          <EmptyState title="Pick at least two companies"
            description={`Add ${MIN_SYMBOLS} to ${MAX_SYMBOLS} tracked companies above to compare them.`} />
        </div>
      ) : compare.isError ? (
        <div className="card flex items-start gap-3 text-sm text-down">
          <AlertTriangle size={18} className="mt-0.5 shrink-0" />
          <p>{errorMessage(compare.error)}</p>
        </div>
      ) : compare.isPending ? (
        <div className="card flex items-center justify-center gap-2 py-16 text-sm text-text-secondary">
          <Loader2 size={16} className="animate-spin" /> Loading comparison…
        </div>
      ) : (
        <>
          <SummaryCards profiles={profiles} slot={slot} />
          <TrendChart profiles={profiles} slot={slot} />
          <MetricsTable profiles={profiles} slot={slot} />
          <BrokersSection profiles={profiles} slot={slot} />
          <DataNotes profiles={profiles} />
        </>
      )}
    </div>
  );
}

function Picker({ symbols, onChange, companies, loading }: {
  symbols: string[]; onChange: (next: string[]) => void;
  companies: { symbol: string; name: string; sector: string }[]; loading: boolean;
}) {
  const bySector = useMemo(() => {
    const groups = new Map<string, typeof companies>();
    companies.filter((c) => !symbols.includes(c.symbol)).forEach((c) => {
      groups.set(c.sector, [...(groups.get(c.sector) ?? []), c]);
    });
    return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [companies, symbols]);
  const full = symbols.length >= MAX_SYMBOLS;

  return (
    <div className="card flex flex-wrap items-center gap-2">
      {symbols.map((symbol, i) => (
        <span key={symbol}
          className="inline-flex items-center gap-1.5 rounded-full border border-bg-border bg-bg-border py-1 pl-2.5 pr-1 text-xs font-semibold text-text-primary">
          <span className="h-2 w-2 rounded-full" style={{ background: seriesColor(i) }} />
          {symbol}
          <button type="button" aria-label={`Remove ${symbol}`} onClick={() => onChange(symbols.filter((s) => s !== symbol))}
            className="rounded-full p-0.5 text-text-muted hover:bg-bg-card hover:text-text-primary">
            <X size={12} />
          </button>
        </span>
      ))}
      <label className="inline-flex items-center gap-1.5 text-xs text-text-secondary">
        <Plus size={14} />
        <select value="" disabled={full || loading} aria-label="Add a company"
          onChange={(e) => e.target.value && onChange([...symbols, e.target.value])}
          className={`${selectClass} min-w-[170px]`}>
          <option value="">{loading ? 'Loading…' : full ? `Up to ${MAX_SYMBOLS} companies` : 'Add company'}</option>
          {bySector.map(([sector, list]) => (
            <optgroup key={sector} label={sector}>
              {list.map((c) => <option key={c.symbol} value={c.symbol}>{c.symbol} · {c.name}</option>)}
            </optgroup>
          ))}
        </select>
      </label>
      {symbols.length > 0 && (
        <button type="button" onClick={() => onChange([])} className="ml-auto text-xs text-text-muted hover:text-text-primary">
          Clear
        </button>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Small building blocks                                               */
/* ------------------------------------------------------------------ */

type Tone = 'up' | 'down' | 'flat';

/** Neutral pill with a toned label, so it works on any theme without alpha colors. */
function Pill({ tone, children }: { tone: Tone; children: ReactNode }) {
  return (
    <span className={clsx(
      'inline-flex items-center gap-1.5 rounded-full bg-bg-border px-2.5 py-0.5 text-[11px] font-semibold',
      tone === 'up' && 'text-up', tone === 'down' && 'text-down', tone === 'flat' && 'text-text-muted',
    )}>
      <span className="h-1.5 w-1.5 rounded-full bg-current" />
      {children}
    </span>
  );
}

function ChangePill({ value }: { value: Num }) {
  const tone = changeTone(value) as Tone;
  const Icon = tone === 'up' ? ArrowUpRight : tone === 'down' ? ArrowDownRight : Minus;
  return (
    <span className={clsx(
      'inline-flex items-center gap-1 rounded-full bg-bg-border px-2.5 py-0.5 font-mono text-xs font-semibold',
      tone === 'up' && 'text-up', tone === 'down' && 'text-down', tone === 'flat' && 'text-text-muted',
    )}>
      <Icon size={13} />
      {formatPct(value)}
    </span>
  );
}

/** Where today's price sits between the 52-week low and high. */
function RangeBar({ low, high, ltp, color }: { low: Num; high: Num; ltp: Num; color: string }) {
  const l = toNumber(low);
  const h = toNumber(high);
  const v = toNumber(ltp);
  if (l === null || h === null || v === null || Number.isNaN(l + h + v) || h <= l) return null;
  const pos = Math.min(100, Math.max(0, ((v - l) / (h - l)) * 100));
  return (
    <div className="space-y-1.5">
      <p className="text-[10px] font-semibold uppercase tracking-wide text-text-muted">52-week range</p>
      <div className="relative h-1.5 rounded-full bg-bg-border">
        <div className="absolute inset-y-0 left-0 rounded-full opacity-40" style={{ width: `${pos}%`, background: color }} />
        <span className="absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-bg-card"
          style={{ left: `${pos}%`, background: color }} />
      </div>
      <div className="flex justify-between font-mono text-[11px] text-text-secondary">
        <span>{formatPrice(low)}</span>
        <span>{formatPrice(high)}</span>
      </div>
    </div>
  );
}

function SummaryCards({ profiles, slot }: { profiles: CompareProfile[]; slot: (s: string) => number }) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">
      {profiles.map((p) => {
        if (p.error) {
          return (
            <div key={p.symbol} className="card text-sm">
              <p className="font-semibold text-text-primary">{p.symbol}</p>
              <p className="mt-1 text-xs text-down">{p.detail}</p>
            </div>
          );
        }
        const color = seriesColor(slot(p.symbol));
        return (
          <div key={p.symbol} className="card space-y-3">
            <div>
              <div className="flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full" style={{ background: color }} />
                <span className="font-semibold text-text-primary">{p.symbol}</span>
                <span className="ml-auto truncate text-[11px] text-text-muted">{p.sector}</span>
              </div>
              <p className="mt-1 truncate text-xs text-text-secondary" title={p.name}>{p.name}</p>
            </div>

            <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
              <span className="font-mono text-2xl font-semibold leading-none text-text-primary">
                {formatPrice(p.general.ltp)}
              </span>
              <ChangePill value={p.general.change_pct} />
            </div>

            <div className="flex items-center justify-between border-y border-bg-border py-2 text-xs">
              <span className="text-text-secondary">Previous close</span>
              <span className="font-mono font-semibold text-text-primary">{formatPrice(p.general.previous_close)}</span>
            </div>

            <RangeBar low={p.general.week52_low} high={p.general.week52_high} ltp={p.general.ltp} color={color} />

            <p className="text-[11px] text-text-muted">
              Close of {formatTradeDate(p.data_quality.price_as_of)}
              {p.general.ltp_source === 'company_live_feed' && ' · live feed'}
            </p>
          </div>
        );
      })}
    </div>
  );
}

function TrendChart({ profiles, slot }: { profiles: CompareProfile[]; slot: (s: string) => number }) {
  // Each line is % change from that company's first close in the window, so prices of
  // different sizes share one axis.
  const { rows, series } = useMemo(() => {
    const byDate = new Map<string, Record<string, number | string>>();
    const series: string[] = [];
    profiles.forEach((p) => {
      const points = p.error ? null : p.general.price_trend_3m;
      const base = toNumber(points?.[0]?.close);
      if (!points || !base) return;
      series.push(p.symbol);
      points.forEach((point) => {
        const close = toNumber(point.close);
        if (close === null) return;
        const row = byDate.get(point.date) ?? { date: point.date };
        row[p.symbol] = ((close - base) / base) * 100;
        byDate.set(point.date, row);
      });
    });
    return { rows: [...byDate.values()].sort((a, b) => String(a.date).localeCompare(String(b.date))), series };
  }, [profiles]);

  return (
    <div className="card">
      <h2 className="mb-3 text-sm font-semibold text-text-primary">3-month price trend <span className="font-normal text-text-muted">(% from first close)</span></h2>
      {rows.length === 0 ? (
        <p className="py-8 text-center text-xs text-text-muted">No crawled prices in the last 3 months.</p>
      ) : (
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={rows} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid stroke={GRID} vertical={false} />
              <XAxis dataKey="date" tick={{ fill: MUTED, fontSize: 11 }} tickLine={false} axisLine={false} minTickGap={40}
                tickFormatter={(d: string) => formatTradeDate(d).replace(/ \d{4}$/, '')} />
              <YAxis tick={{ fill: MUTED, fontSize: 11 }} tickLine={false} axisLine={false} width={48}
                tickFormatter={(v: number) => `${v.toFixed(0)}%`} />
              <Tooltip content={<TrendTooltip />} />
              {series.map((symbol) => (
                <Line key={symbol} dataKey={symbol} stroke={seriesColor(slot(symbol))} dot={false} strokeWidth={1.75}
                  connectNulls isAnimationActive={false} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}

function TrendTooltip({ active, label, payload }: {
  active?: boolean; label?: string; payload?: { dataKey: string; value: number; color: string }[];
}) {
  if (!active || !payload?.length || !label) return null;
  return (
    <div className="min-w-[150px] rounded-lg border border-bg-border bg-bg-elevated px-3 py-2 text-xs shadow-xl">
      <p className="mb-1.5 font-semibold text-text-muted">{formatTradeDate(label)}</p>
      {[...payload].sort((a, b) => b.value - a.value).map((row) => (
        <p key={row.dataKey} className="flex items-center gap-2 py-0.5 font-mono">
          <span className="h-2 w-2 rounded-full" style={{ background: row.color }} />
          <span className="font-sans text-text-secondary">{row.dataKey}</span>
          <span className="ml-auto pl-4 text-text-primary">{formatPct(row.value)}</span>
        </p>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Metrics table                                                       */
/* ------------------------------------------------------------------ */

function nullReason(p: CompareProfile, field: string) {
  const entry = p.data_quality.null_fields.find((e) => e.field === field);
  return entry ? NULL_REASON_LABELS[entry.reason] ?? entry.reason : null;
}

function bestSymbol(row: MetricRow, profiles: CompareProfile[]) {
  if (!row.best) return null;
  const values = profiles.filter((p) => !p.error)
    .map((p) => ({ symbol: p.symbol, n: toNumber(row.value(p)) }))
    .filter((v): v is { symbol: string; n: number } => v.n !== null && !Number.isNaN(v.n));
  if (values.length < 2) return null;
  values.sort((a, b) => (row.best === 'high' ? b.n - a.n : a.n - b.n));
  return values[0].n === values[1].n ? null : values[0].symbol;
}

/** Bar length (0-100) for one cell, or null when the row has no bar / the value can't be drawn. */
function barPct(row: MetricRow, p: CompareProfile, profiles: CompareProfile[]) {
  if (!row.bar) return null;
  const n = toNumber(row.value(p));
  if (n === null || Number.isNaN(n) || n < 0) return null;
  const max = typeof row.bar === 'number'
    ? row.bar
    : profiles.reduce((m, q) => {
      const v = toNumber(row.value(q));
      return v !== null && !Number.isNaN(v) && v > m ? v : m;
    }, 0);
  return max > 0 ? Math.min(100, (n / max) * 100) : null;
}

const LABEL_W = 176; // px, Metric column
const COL_W = 120;   // px, min per symbol column
const labelCell =
  'sticky left-0 z-10 truncate border-r border-bg-border bg-bg-card px-4 py-2.5 text-left text-text-secondary';
const valueCell = 'px-4 py-2.5 text-right align-middle tabular-nums';
const dash = <span className="font-mono text-text-muted">—</span>;

function SimpleRow({ label, profiles, render }: {
  label: string;
  profiles: CompareProfile[];
  render: (p: CompareProfile) => ReactNode;
}) {
  return (
    <tr className="border-t border-bg-border">
      <td className={labelCell} title={label}>{label}</td>
      {profiles.map((p) => (
        <td key={p.symbol} className={valueCell}>{render(p)}</td>
      ))}
    </tr>
  );
}

function MetricsTable({ profiles, slot }: { profiles: CompareProfile[]; slot: (s: string) => number }) {
  const ok = profiles.filter((p) => !p.error);
  if (ok.length === 0) return null;

  // A metric that is missing for every company moves to the "Not available" card below the
  // table instead of taking a row of dashes.
  const sections = SECTIONS.map((section) => {
    const shown = section.rows.filter((r) => ok.some((p) => toNumber(r.value(p)) !== null));
    return { title: section.title, shown, hidden: section.rows.filter((r) => !shown.includes(r)) };
  });
  const unavailable = sections.flatMap((s) => s.hidden).map((row) => ({
    label: row.label,
    reason: [...new Set(ok.map((p) => nullReason(p, row.field)).filter((r): r is string => !!r))].join(' · '),
  }));

  return (
    <>
      <div className="card overflow-x-auto !p-0">
        <table className="w-full table-fixed text-xs" style={{ minWidth: LABEL_W + ok.length * COL_W }}>
          <colgroup>
            <col style={{ width: LABEL_W }} />
            {ok.map((p) => <col key={p.symbol} />)}
          </colgroup>

          <thead>
            <tr className="bg-bg-card text-text-secondary">
              <th className="sticky left-0 z-20 border-r border-bg-border bg-bg-card px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wide">
                Metric
              </th>
              {ok.map((p) => (
                <th key={p.symbol} className="px-4 py-3 text-right text-sm font-semibold text-text-primary">
                  <span className="inline-flex max-w-full items-center justify-end gap-2">
                    <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: seriesColor(slot(p.symbol)) }} />
                    <span className="truncate" title={p.symbol}>{p.symbol}</span>
                  </span>
                </th>
              ))}
            </tr>
          </thead>

          <tbody>
            {sections.filter((s) => s.shown.length > 0).map((section) => (
              <SectionRows key={section.title} title={section.title} rows={section.shown}
                profiles={ok} slot={slot} span={ok.length + 1} />
            ))}

            <SimpleRow label="MACD trend" profiles={ok} render={(p) => {
              const l = p.technicals.macd_label;
              if (!l) return dash;
              return <Pill tone={l === 'Bullish' ? 'up' : l === 'Bearish' ? 'down' : 'flat'}>{l}</Pill>;
            }} />

            {(['sma50', 'sma200'] as const).map((key) => (
              <SimpleRow key={key} label={`LTP vs ${key === 'sma50' ? 'SMA 50' : 'SMA 200'}`} profiles={ok}
                render={(p) => {
                  const block = p.technicals[key];
                  if (!block) return dash;
                  return <Pill tone={block.above ? 'up' : 'down'}>{block.above ? 'Above' : 'Below'}</Pill>;
                }} />
            ))}

            <SimpleRow label="Volume (10 sessions)" profiles={ok} render={(p) => {
              const volumes = (p.technicals.volume_trend ?? []).map((v) => v.volume);
              if (volumes.length < 2) return dash;
              return (
                <span className="inline-flex flex-col items-end gap-0.5">
                  <Sparkline data={volumes} width={80} height={24}
                    positive={volumes[volumes.length - 1] >= volumes[0]} />
                  <span className="font-mono text-[11px] text-text-muted">{formatCount(volumes[volumes.length - 1])}</span>
                </span>
              );
            }} />
          </tbody>
        </table>
      </div>

      <p className="px-1 text-[11px] text-text-muted">
        Bars compare the companies: a longer bar is the higher number, not necessarily the better one. RSI bars use a
        0 to 100 scale. The highlighted value is the best in the group where "better" is clear (higher EPS, ROE and
        yield; lower P/E and P/B).
      </p>

      {unavailable.length > 0 && (
        <div className="card space-y-3">
          <div>
            <h2 className="text-sm font-semibold text-text-primary">Not available</h2>
            <p className="text-xs text-text-muted">These metrics are missing for every company in this comparison.</p>
          </div>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
            {unavailable.map((u) => (
              <div key={u.label} className="rounded-lg border border-dashed border-bg-border px-3 py-2.5">
                <p className="text-xs font-semibold text-text-primary">{u.label}</p>
                {u.reason && <p className="mt-0.5 text-[11px] leading-tight text-text-muted">{u.reason}</p>}
              </div>
            ))}
          </div>
        </div>
      )}
    </>
  );
}

function SectionRows({ title, rows, profiles, slot, span }: {
  title: string; rows: MetricRow[]; profiles: CompareProfile[]; slot: (s: string) => number; span: number;
}) {
  return (
    <>
      {/* Title lives in the sticky first cell so it stays visible on horizontal scroll */}
      <tr className="border-t border-bg-border bg-bg-border">
        <td className="sticky left-0 z-10 truncate bg-bg-border px-4 py-1.5 text-left text-[11px] font-semibold uppercase tracking-wide text-text-secondary">
          {title}
        </td>
        <td colSpan={span - 1} />
      </tr>
      {rows.map((row) => {
        const best = bestSymbol(row, profiles);
        return (
          <tr key={row.field} className="border-t border-bg-border">
            <td className={labelCell} title={row.hint ?? row.label}>{row.label}</td>
            {profiles.map((p) => {
              const value = row.value(p);
              const missing = toNumber(value) === null;
              const reason = missing ? nullReason(p, row.field) : null;
              const pct = missing ? null : barPct(row, p, profiles);
              return (
                <td key={p.symbol} className={valueCell}>
                  {missing ? (
                    <span className="inline-flex max-w-full flex-col items-end">
                      {dash}
                      {reason && (
                        <span className="text-right text-[10px] leading-tight text-text-muted">{reason}</span>
                      )}
                    </span>
                  ) : (
                    <span className="inline-flex w-full flex-col items-end gap-1">
                      <span className={clsx('font-mono',
                        best === p.symbol ? 'font-semibold text-accent-light' : 'text-text-primary')}>
                        {row.format(value)}
                      </span>
                      {pct !== null && (
                        <span className="h-1 w-full max-w-[88px] overflow-hidden rounded-full bg-bg-border">
                          <span className="block h-full rounded-full"
                            style={{ width: `${pct}%`, background: seriesColor(slot(p.symbol)) }} />
                        </span>
                      )}
                    </span>
                  )}
                </td>
              );
            })}
          </tr>
        );
      })}
    </>
  );
}

/* ------------------------------------------------------------------ */
/* Brokers + data notes (unchanged)                                    */
/* ------------------------------------------------------------------ */

function BrokerList({ title, rows }: { title: string; rows: BrokerRow[] | null }) {
  return (
    <div>
      <p className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-text-muted">{title}</p>
      {!rows?.length ? <p className="text-xs text-text-muted">—</p> : (
        <ol className="space-y-0.5">
          {rows.map((b) => (
            <li key={String(b.broker_no)} className="flex items-baseline gap-2 text-xs">
              <span className="w-7 font-mono text-text-primary">{b.broker_no}</span>
              <span className="min-w-0 flex-1 truncate text-text-secondary" title={b.broker_name ?? undefined}>{b.broker_name ?? 'Unknown broker'}</span>
              <span className="font-mono text-text-muted">{plainPct(b.pct_of_day_volume)}</span>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

function BrokersSection({ profiles, slot }: { profiles: CompareProfile[]; slot: (s: string) => number }) {
  const ok = profiles.filter((p) => !p.error);
  if (ok.length === 0) return null;
  return (
    <div className="card">
      <h2 className="mb-3 text-sm font-semibold text-text-primary">Top brokers <span className="font-normal text-text-muted">(share of the day's volume)</span></h2>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
        {ok.map((p) => (
          <div key={p.symbol} className="space-y-3 rounded-lg border border-bg-border p-3">
            <p className="flex items-center gap-2 text-xs font-semibold text-text-primary">
              <span className="h-2 w-2 rounded-full" style={{ background: seriesColor(slot(p.symbol)) }} />
              {p.symbol}
              <span className="ml-auto font-normal text-text-muted">{formatTradeDate(p.general.brokers_date)}</span>
            </p>
            <BrokerList title="Buyers" rows={p.general.top_buy_brokers} />
            <BrokerList title="Sellers" rows={p.general.top_sell_brokers} />
          </div>
        ))}
      </div>
    </div>
  );
}

function DataNotes({ profiles }: { profiles: CompareProfile[] }) {
  const ok = profiles.filter((p) => !p.error);
  const sectorNote = ok.flatMap((p) => p.data_quality.null_fields).find((e) => e.note)?.note;
  const anyWarnings = ok.some((p) => p.data_quality.warnings.length > 0);
  if (!anyWarnings && !sectorNote) return null;
  return (
    <div className="card space-y-3 text-xs">
      <h2 className="flex items-center gap-2 text-sm font-semibold text-text-primary"><Info size={15} /> Data notes</h2>
      {sectorNote && <p className="text-text-secondary">{sectorNote}</p>}
      {ok.map((p) => p.data_quality.warnings.length > 0 && (
        <div key={p.symbol}>
          <p className="font-semibold text-text-primary">{p.symbol}</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-5 text-text-secondary">
            {p.data_quality.warnings.map((w) => (
              <li key={w.code}>
                {w.detail}
                {w.sessions && ` (${w.sessions.map((s) => formatTradeDate(s.date)).join(', ')})`}
              </li>
            ))}
          </ul>
        </div>
      ))}
      <p className="text-text-muted">Tracked companies only. Prices are crawled closes, not adjusted for bonus or right shares.</p>
    </div>
  );
}