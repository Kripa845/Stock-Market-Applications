import { useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { AlertTriangle, ChevronDown, ChevronsUpDown, ChevronUp, Info } from 'lucide-react';
import clsx from 'clsx';
import PageHeader from '../components/common/PageHeader';
import CompanyLogo from '../components/companies/CompanyLogo';
import { formatPrice, formatTradeDate } from '../components/market/format';
import { Filter, ResetButton, formatTradeTime, selectClass } from '../components/market/TopListControls';
import { marketApi, type DividendFlag, type DividendRow, type DividendStatus, type DividendsResponse } from '../api/market';

// Market -> Proposed Dividend (/market/dividends) for the tracked companies, crawled from ShareSansar.
// Every figure (cash per share, yield, payout, ex-bonus price) is calculated by the backend
// (services/dividends.py); this page only filters, sorts and formats.

type SortKey =
  | 'symbol' | 'fiscal_year' | 'bonus_pct' | 'cash_pct' | 'total_pct' | 'cash_dps' | 'price'
  | 'dividend_yield_pct' | 'eps' | 'payout_pct' | 'ex_bonus_price' | 'announcement_date'
  | 'book_closure_date' | 'status';

const COLUMNS: { key: SortKey; label: string; align?: 'left' | 'center'; title?: string }[] = [
  { key: 'symbol', label: 'Symbol', align: 'left' },
  { key: 'fiscal_year', label: 'Fiscal Year', align: 'center' },
  { key: 'bonus_pct', label: 'Bonus %' },
  { key: 'cash_pct', label: 'Cash %' },
  { key: 'total_pct', label: 'Total %' },
  { key: 'cash_dps', label: 'Cash / Share', title: 'Cash % × face value (NPR)' },
  { key: 'price', label: 'Price', title: 'Latest crawled close' },
  { key: 'dividend_yield_pct', label: 'Yield %', title: 'Cash per share ÷ price' },
  { key: 'eps', label: 'EPS', title: 'Full-year EPS of the same fiscal year' },
  { key: 'payout_pct', label: 'Payout %', title: '(Cash + bonus) per share ÷ EPS; hover a value for the cash-only ratio' },
  { key: 'ex_bonus_price', label: 'Ex-Bonus Price', title: 'Price ÷ (1 + bonus %), while the price is still cum-bonus' },
  { key: 'announcement_date', label: 'Announced', align: 'center' },
  { key: 'book_closure_date', label: 'Book Closure', align: 'center' },
  { key: 'status', label: 'Status', align: 'center' },
];
const ALIGN = { left: 'text-left', center: 'text-center', right: 'text-right' } as const;
const TEXT_KEYS = new Set<SortKey>(['symbol', 'fiscal_year', 'announcement_date', 'book_closure_date']);

const STATUS_ORDER: Record<DividendStatus, number> = { proposed: 0, agm_approved: 1, sebon_approved: 2, distributed: 3 };
const STATUS_CHIP: Record<DividendStatus, string> = {
  proposed: 'bg-yellow-400/10 text-yellow-400',
  agm_approved: 'bg-blue-500/10 text-blue-400',
  sebon_approved: 'bg-violet-500/10 text-violet-400',
  distributed: 'bg-up/10 text-up',
};

const MISSING_LABEL: Partial<Record<DividendFlag, string>> = {
  missing_symbol: 'No symbol',
  missing_fiscal_year: 'No fiscal year',
};
const NO_VALUE_REASON: Partial<Record<DividendFlag, string>> = {
  no_price: 'No crawled price for this symbol',
  no_face_value: 'Face value not crawled yet',
  no_eps: 'No full-year EPS crawled for this fiscal year',
};

const toNumber = (value: number | string | null) => (value === null || value === '' ? null : Number(value));

function pct(value: number | string | null, digits = 2) {
  const n = toNumber(value);
  return n === null || Number.isNaN(n) ? '—' : `${n.toFixed(digits)}%`;
}

function sortValue(row: DividendRow, key: SortKey): number | string | null {
  if (key === 'status') return STATUS_ORDER[row.status];
  const value = row[key];
  if (value === null || value === '') return null;
  return TEXT_KEYS.has(key) ? String(value) : Number(value);
}

/** "—" with the reason as a tooltip when the backend could not calculate the value. */
function Missing({ row, needs }: { row: DividendRow; needs: DividendFlag[] }) {
  const reasons = needs.filter((flag) => row.flags.includes(flag)).map((flag) => NO_VALUE_REASON[flag]);
  return <span title={reasons.join(' · ') || undefined} className="text-text-muted">—</span>;
}

function DividendTableRow({ row, statusLabel }: { row: DividendRow; statusLabel: string }) {
  const missing = row.flags.filter((flag) => MISSING_LABEL[flag]);
  const money = (value: number | null, needs: DividendFlag[]) =>
    value === null ? <Missing row={row} needs={needs} /> : formatPrice(value);
  const ratio = (value: number | null, needs: DividendFlag[]) =>
    value === null ? <Missing row={row} needs={needs} /> : pct(value);

  return (
    <tr className={clsx('border-b border-bg-border last:border-0 hover:bg-blue-500/10', missing.length > 0 && 'bg-yellow-400/5')}>
      <td className="py-2.5 pl-4 pr-2">
        <span className="flex min-w-0 items-center gap-2.5">
          <CompanyLogo symbol={row.symbol || '?'} name={row.name} logoUrl={row.logo_url} size="sm" />
          <span className="min-w-0">
            <span className="block font-semibold text-text-primary">{row.symbol || '—'}</span>
            <span className="block max-w-[220px] truncate text-[11px] text-text-muted" title={row.name}>{row.name}</span>
            {missing.length > 0 && (
              <span className="mt-0.5 flex flex-wrap gap-1">
                {missing.map((flag) => (
                  <span key={flag} title="Missing from the scraped data"
                    className="inline-flex items-center gap-0.5 rounded bg-yellow-400/15 px-1.5 py-px text-[10px] font-semibold text-yellow-400">
                    <AlertTriangle size={9} /> {MISSING_LABEL[flag]}
                  </span>
                ))}
              </span>
            )}
          </span>
        </span>
      </td>
      <td className="px-2 text-center font-mono text-text-secondary">{row.fiscal_year || '—'}</td>
      <td className="px-2 text-right font-mono">{pct(row.bonus_pct)}</td>
      <td className="px-2 text-right font-mono">{pct(row.cash_pct)}</td>
      <td className="px-2 text-right font-mono font-semibold text-text-primary">{pct(row.total_pct)}</td>
      <td className="px-2 text-right font-mono">{money(row.cash_dps, ['no_face_value'])}</td>
      <td className="px-2 text-right font-mono" title={row.price_date ? `Close of ${formatTradeDate(row.price_date)}` : undefined}>
        {money(row.price, ['no_price'])}
      </td>
      <td className="px-2 text-right font-mono">{ratio(row.dividend_yield_pct, ['no_face_value', 'no_price'])}</td>
      <td className="px-2 text-right font-mono">{money(row.eps, ['no_eps'])}</td>
      <td className="px-2 text-right font-mono" title={row.cash_payout_pct !== null ? `Cash only: ${pct(row.cash_payout_pct)}` : undefined}>
        {ratio(row.payout_pct, ['no_face_value', 'no_eps'])}
      </td>
      <td className="px-2 text-right font-mono">{money(row.ex_bonus_price, ['no_price'])}</td>
      <td className="whitespace-nowrap px-2 text-center font-mono text-text-secondary">{formatTradeDate(row.announcement_date)}</td>
      <td className="whitespace-nowrap px-2 text-center font-mono text-text-secondary">{formatTradeDate(row.book_closure_date)}</td>
      <td className="py-2.5 pl-2 pr-4 text-center">
        <span className={`inline-block whitespace-nowrap rounded-md px-2 py-0.5 text-[11px] font-semibold ${STATUS_CHIP[row.status]}`}>
          {statusLabel}
        </span>
      </td>
    </tr>
  );
}

export default function DividendsPage() {
  const [params, setParams] = useSearchParams();
  const fiscalYear = params.get('fiscal_year') ?? '';
  const status = params.get('status') ?? '';

  const [data, setData] = useState<DividendsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [tick, setTick] = useState(0);          // bumped by Retry
  const [sort, setSort] = useState<{ key: SortKey; desc: boolean } | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(false);
    marketApi.dividends({ fiscal_year: fiscalYear, status })
      .then((response) => { if (!cancelled) setData(response); })
      .catch(() => { if (!cancelled) setError(true); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [fiscalYear, status, tick]);

  const update = (changes: Record<string, string | null>) => {
    const next = new URLSearchParams(params);
    Object.entries(changes).forEach(([key, value]) => (value ? next.set(key, value) : next.delete(key)));
    setParams(next, { replace: true });
  };

  const rows = data?.rows ?? [];
  const sorted = useMemo(() => {
    if (!sort) return rows;
    const factor = sort.desc ? -1 : 1;
    return [...rows].sort((a, b) => {
      const left = sortValue(a, sort.key);
      const right = sortValue(b, sort.key);
      if (left === null) return 1;
      if (right === null) return -1;
      return (typeof left === 'string' ? left.localeCompare(String(right)) : left - Number(right)) * factor;
    });
  }, [rows, sort]);

  // Text columns start ascending, numbers descending; a third click restores the server order.
  const toggle = (key: SortKey) => {
    const firstDesc = !TEXT_KEYS.has(key) || key.endsWith('_date');
    setSort((current) => (current?.key !== key ? { key, desc: firstDesc } : current.desc === firstDesc ? { key, desc: !current.desc } : null));
  };

  const statusLabels = Object.fromEntries((data?.statuses ?? []).map((s) => [s.value, s.label])) as Record<string, string>;
  const incomplete = rows.filter((row) => row.flags.some((flag) => MISSING_LABEL[flag])).length;
  const lastCrawl = data?.last_crawl;

  return (
    <div className="space-y-4">
      <PageHeader title="Proposed Dividend" subtitle="Bonus and cash dividends announced by your tracked companies" />

      <div className="card space-y-3 !p-0">
        <div className="flex flex-wrap items-center justify-between gap-3 px-4 pt-4">
          <p className="text-[11px] text-text-muted">
            Last updated{' '}
            <span className="font-mono font-semibold text-text-secondary">{formatTradeTime(data?.last_scraped_at ?? null) ?? '—'}</span>
            {lastCrawl && lastCrawl.status !== 'success' && lastCrawl.status !== 'running' && (
              <span className="ml-2 text-down">· last crawl {lastCrawl.status}</span>
            )}
            <span> · source ShareSansar (face value), Merolagani (EPS)</span>
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <Filter label="Fiscal Year">
              <select value={fiscalYear || data?.fiscal_year || ''} onChange={(e) => update({ fiscal_year: e.target.value })}
                className={`${selectClass} min-w-[120px]`}>
                {(data?.fiscal_years ?? []).map((year) => <option key={year} value={year}>{year}</option>)}
                <option value="all">All years</option>
              </select>
            </Filter>
            <Filter label="Status">
              <select value={status} onChange={(e) => update({ status: e.target.value })} className={`${selectClass} min-w-[140px]`}>
                <option value="">All statuses</option>
                {(data?.statuses ?? []).map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
              </select>
            </Filter>
            <ResetButton disabled={!params.toString() && !sort} onClick={() => { setParams({}, { replace: true }); setSort(null); }} />
          </div>
        </div>

        {data?.status_note && (
          <p className="mx-4 flex items-start gap-1.5 text-[11px] text-text-muted">
            <Info size={12} className="mt-px shrink-0" /> {data.status_note}
          </p>
        )}
        {incomplete > 0 && (
          <p className="mx-4 flex items-center gap-1.5 rounded-md border border-yellow-400/30 bg-yellow-400/10 px-3 py-2 text-xs text-yellow-400">
            <AlertTriangle size={13} /> {incomplete} row{incomplete > 1 ? 's are' : ' is'} missing a symbol or fiscal year in the scraped data (highlighted).
          </p>
        )}

        {error ? (
          <div className="flex items-center justify-center gap-2 py-12 text-sm text-down">
            <AlertTriangle size={14} /> Could not load the proposed dividends.
            <button onClick={() => setTick((t) => t + 1)} className="underline">Retry</button>
          </div>
        ) : !data && loading ? (
          <p className="py-12 text-center text-sm text-text-muted">Loading proposed dividends…</p>
        ) : (
          <div className={clsx('overflow-x-auto transition-opacity', loading && 'opacity-60')}>
            <table className="w-full min-w-[1280px] text-xs">
              <thead>
                <tr className="border-y border-bg-border text-[11px] uppercase text-text-secondary">
                  {COLUMNS.map((column) => {
                    const active = sort?.key === column.key;
                    const Icon = !active ? ChevronsUpDown : sort?.desc ? ChevronDown : ChevronUp;
                    return (
                      <th key={column.key} title={column.title}
                        className={`whitespace-nowrap px-2 py-2.5 font-semibold first:pl-4 last:pr-4 ${ALIGN[column.align ?? 'right']}`}>
                        <button type="button" onClick={() => toggle(column.key)}
                          className={`inline-flex items-center gap-0.5 uppercase hover:text-text-primary ${active ? 'text-text-primary' : ''}`}>
                          {column.label}<Icon size={11} className={active ? '' : 'opacity-50'} />
                        </button>
                      </th>
                    );
                  })}
                </tr>
              </thead>
              <tbody>
                {sorted.map((row) => <DividendTableRow key={row.id} row={row} statusLabel={statusLabels[row.status] ?? row.status} />)}
                {!loading && rows.length === 0 && (
                  <tr>
                    <td colSpan={COLUMNS.length} className="px-4 py-12 text-center text-sm text-text-muted">
                      {data?.last_scraped_at ? 'No dividends match these filters.' : 'No dividends crawled yet: run `scrapy crawl dividends`.'}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
        <p className="px-4 pb-4 text-[11px] text-text-muted">{rows.length} rows</p>
      </div>
    </div>
  );
}
