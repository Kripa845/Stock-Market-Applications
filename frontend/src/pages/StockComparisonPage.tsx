import { useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { isAxiosError } from 'axios';
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { AlertTriangle, Info, Loader2, Plus, X } from 'lucide-react';
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
      { label: 'EPS (TTM)', field: 'general.eps_ttm', value: (p) => p.general.eps_ttm, format: formatPrice, best: 'high' },
      { label: 'EPS (as filed)', field: 'general.eps_reported', value: (p) => p.general.eps_reported, format: formatPrice },
      { label: 'P/E', field: 'fundamentals.pe', value: (p) => p.fundamentals.pe, format: ratio, best: 'low' },
      { label: 'P/B', field: 'fundamentals.pb', value: (p) => p.fundamentals.pb, format: ratio, best: 'low' },
      { label: 'ROE', field: 'fundamentals.roe', value: (p) => p.fundamentals.roe, format: plainPct, best: 'high' },
      { label: 'Dividend (total)', field: 'fundamentals.dividend', value: (p) => p.fundamentals.dividend?.total_pct ?? null, format: plainPct },
      { label: 'Dividend yield', field: 'fundamentals.dividend_yield', value: (p) => p.fundamentals.dividend_yield, format: plainPct, best: 'high',
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
      { label: 'RSI (14)', field: 'technicals.rsi', value: (p) => p.technicals.rsi, format: ratio },
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
          className="inline-flex items-center gap-1.5 rounded-full border border-bg-border bg-bg-elevated py-1 pl-2.5 pr-1 text-xs font-semibold text-text-primary">
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
        const tone = changeTone(p.general.change_pct);
        return (
          <div key={p.symbol} className="card space-y-1">
            <div className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full" style={{ background: seriesColor(slot(p.symbol)) }} />
              <span className="font-semibold text-text-primary">{p.symbol}</span>
              <span className="ml-auto truncate text-[11px] text-text-muted">{p.sector}</span>
            </div>
            <p className="truncate text-xs text-text-secondary" title={p.name}>{p.name}</p>
            <p className="font-mono text-lg font-semibold text-text-primary">
              {formatPrice(p.general.ltp)}
              <span className={clsx('ml-2 text-sm', tone === 'up' && 'text-up', tone === 'down' && 'text-down',
                tone === 'flat' && 'text-text-muted')}>
                {formatPct(p.general.change_pct)}
              </span>
            </p>
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

function MetricsTable({ profiles, slot }: { profiles: CompareProfile[]; slot: (s: string) => number }) {
  const ok = profiles.filter((p) => !p.error);
  if (ok.length === 0) return null;
  const cell = 'px-3 py-2 text-right';
  return (
    <div className="card overflow-x-auto !p-0">
      <table className="w-full min-w-[640px] text-xs">
        <thead>
          <tr className="border-b border-bg-border text-text-secondary">
            <th className="sticky left-0 bg-bg-card px-3 py-2.5 text-left font-semibold">Metric</th>
            {ok.map((p) => (
              <th key={p.symbol} className={clsx(cell, 'font-semibold text-text-primary')}>
                <span className="inline-flex items-center gap-1.5">
                  <span className="h-2 w-2 rounded-full" style={{ background: seriesColor(slot(p.symbol)) }} />
                  {p.symbol}
                </span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {SECTIONS.map((section) => (
            <SectionRows key={section.title} title={section.title} rows={section.rows} profiles={ok} span={ok.length + 1} />
          ))}
          <tr className="border-t border-bg-border/60">
            <td className="sticky left-0 bg-bg-card px-3 py-2 text-text-secondary">MACD trend</td>
            {ok.map((p) => (
              <td key={p.symbol} className={clsx(cell, 'font-semibold',
                p.technicals.macd_label === 'Bullish' ? 'text-up' : p.technicals.macd_label === 'Bearish' ? 'text-down' : 'text-text-muted')}>
                {p.technicals.macd_label ?? '—'}
              </td>
            ))}
          </tr>
          {(['sma50', 'sma200'] as const).map((key) => (
            <tr key={key} className="border-t border-bg-border/60">
              <td className="sticky left-0 bg-bg-card px-3 py-2 text-text-secondary">LTP vs {key === 'sma50' ? 'SMA 50' : 'SMA 200'}</td>
              {ok.map((p) => {
                const block = p.technicals[key];
                return (
                  <td key={p.symbol} className={clsx(cell, block ? (block.above ? 'text-up' : 'text-down') : 'text-text-muted')}>
                    {block ? (block.above ? 'Above' : 'Below') : '—'}
                  </td>
                );
              })}
            </tr>
          ))}
          <tr className="border-t border-bg-border/60">
            <td className="sticky left-0 bg-bg-card px-3 py-2 text-text-secondary">Volume, last 10 sessions</td>
            {ok.map((p) => {
              const volumes = (p.technicals.volume_trend ?? []).map((v) => v.volume);
              return (
                <td key={p.symbol} className={cell}>
                  {volumes.length >= 2 ? (
                    <span className="inline-flex flex-col items-end gap-0.5">
                      <Sparkline data={volumes} width={88} height={24} positive={volumes[volumes.length - 1] >= volumes[0]} />
                      <span className="font-mono text-[11px] text-text-muted">{formatCount(volumes[volumes.length - 1])}</span>
                    </span>
                  ) : '—'}
                </td>
              );
            })}
          </tr>
        </tbody>
      </table>
    </div>
  );
}

function SectionRows({ title, rows, profiles, span }: { title: string; rows: MetricRow[]; profiles: CompareProfile[]; span: number }) {
  return (
    <>
      <tr className="bg-bg-elevated/60">
        <td colSpan={span} className="px-3 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-text-muted">{title}</td>
      </tr>
      {rows.map((row) => {
        const best = bestSymbol(row, profiles);
        return (
          <tr key={row.field} className="border-t border-bg-border/60">
            <td className="sticky left-0 bg-bg-card px-3 py-2 text-text-secondary" title={row.hint}>{row.label}</td>
            {profiles.map((p) => {
              const value = row.value(p);
              const reason = toNumber(value) === null ? nullReason(p, row.field) : null;
              return (
                <td key={p.symbol} className="px-3 py-2 text-right">
                  {reason !== null || toNumber(value) === null ? (
                    <span className="inline-flex flex-col items-end">
                      <span className="font-mono text-text-muted">—</span>
                      {reason && <span className="text-[10px] text-text-muted">{reason}</span>}
                    </span>
                  ) : (
                    <span className={clsx('font-mono', best === p.symbol ? 'font-semibold text-accent-light' : 'text-text-primary')}>
                      {row.format(value)}
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
