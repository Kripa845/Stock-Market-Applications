import { ArrowDownRight, ArrowUpRight, BarChart3, ChevronLeft, ChevronRight, Coins, Layers, RotateCcw, type LucideIcon } from 'lucide-react';
import { NavLink, useSearchParams } from 'react-router-dom';
import clsx from 'clsx';
import type { TopMoversPeriod } from '../../api/market';

/** The Market Overview sub-pages, in sidebar order (also used by the sidebar dropdown). */
export const TOP_LIST_PAGES: { label: string; to: string; icon: LucideIcon }[] = [
  { label: 'Top Gainers', to: '/market/gainers', icon: ArrowUpRight },
  { label: 'Top Losers', to: '/market/losers', icon: ArrowDownRight },
  { label: 'Top Turnover', to: '/market/turnover', icon: Coins },
  { label: 'Top Volume', to: '/market/volume', icon: Layers },
  { label: 'Top Transactions', to: '/market/transactions', icon: BarChart3 },
];

/** Tabs across the five pages; period / sector / page size carry over. */
export function TopListTabs() {
  const [params] = useSearchParams();
  const keep = new URLSearchParams();
  ['period', 'sector', 'page_size'].forEach((key) => { const v = params.get(key); if (v) keep.set(key, v); });
  const search = keep.toString() ? `?${keep.toString()}` : '';
  return (
    <nav className="flex flex-wrap gap-1 rounded-lg bg-bg-elevated p-0.5 text-sm font-semibold sm:inline-flex">
      {TOP_LIST_PAGES.map(({ label, to }) => (
        <NavLink key={to} to={`${to}${search}`}
          className={({ isActive }) => clsx('rounded-md px-3 py-1.5', isActive
            ? 'bg-bg-card text-accent-light'
            : 'text-text-secondary hover:text-text-primary')}>
          {label.replace('Top ', '')}
        </NavLink>
      ))}
    </nav>
  );
}

// Shared pieces of the Market Overview sub-pages (Top Gainers / Losers / Turnover / Volume /
// Transactions): period chips, filters, pager.  Filters live in the URL so a view can be
// bookmarked or shared, and defaults are left out of it.

export const PERIODS: { id: TopMoversPeriod; label: string }[] = [
  { id: 'today', label: 'Today' }, { id: '2d', label: '2 Days' }, { id: '3d', label: '3 Days' },
  { id: '5d', label: '5 Days' }, { id: '7d', label: '7 Days' }, { id: '1w', label: '1 Week' },
  { id: '1m', label: '1 Month' }, { id: '3m', label: '3 Months' }, { id: '4m', label: '4 Months' },
  { id: '6m', label: '6 Months' }, { id: '1y', label: '1 Year' },
];
export const PAGE_SIZES = [10, 20, 50, 100];
const DEFAULT_PAGE_SIZE = 20;
export const POLL_MS = 60_000;

export const selectClass =
  'rounded-lg border border-bg-border bg-bg-elevated px-2.5 py-1.5 text-xs text-text-primary outline-none focus:border-accent [color-scheme:dark]';

/** Filters read from / written to the URL; any change other than the page goes back to page 1. */
export function useTopListParams() {
  const [params, setParams] = useSearchParams();
  const period = (PERIODS.find((p) => p.id === params.get('period'))?.id ?? 'today') as TopMoversPeriod;
  const pageSize = PAGE_SIZES.includes(Number(params.get('page_size'))) ? Number(params.get('page_size')) : DEFAULT_PAGE_SIZE;

  const update = (patch: Record<string, string | number | null>) => {
    const next = new URLSearchParams(params);
    Object.entries({ page: null, ...patch }).forEach(([key, value]) => {
      if (value === null || value === '') next.delete(key);
      else next.set(key, String(value));
    });
    setParams(next);
  };

  return {
    params,
    period,
    sector: params.get('sector') ?? '',
    pageSize,
    page: Math.max(1, Number(params.get('page')) || 1),
    update,
    setPeriod: (id: TopMoversPeriod) => update({ period: id === 'today' ? null : id }),
    setPageSize: (n: number) => update({ page_size: n === DEFAULT_PAGE_SIZE ? null : n }),
    reset: () => setParams(new URLSearchParams()),
  };
}

// "2026-10-13, 12:50:19 PM" in Nepal time.
export function formatTradeTime(iso: string | null): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  const tz = 'Asia/Kathmandu';
  return `${d.toLocaleDateString('en-CA', { timeZone: tz })}, ${d.toLocaleTimeString('en-US', { timeZone: tz })}`;
}

export function Filter({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex items-center gap-2 text-xs font-semibold text-text-secondary">
      {label}
      {children}
    </label>
  );
}

export function SectorSelect({ value, sectors, onChange }: { value: string; sectors: string[]; onChange: (v: string) => void }) {
  return (
    <Filter label="Sector">
      <select value={value} onChange={(e) => onChange(e.target.value)} className={`${selectClass} min-w-[150px]`}>
        <option value="">All Sectors</option>
        {sectors.map((s) => <option key={s} value={s}>{s}</option>)}
      </select>
    </Filter>
  );
}

export function PageSizeSelect({ value, onChange }: { value: number; onChange: (n: number) => void }) {
  return (
    <Filter label="Items Per Page">
      <select value={value} onChange={(e) => onChange(Number(e.target.value))} className={selectClass}>
        {PAGE_SIZES.map((n) => <option key={n} value={n}>{n}</option>)}
      </select>
    </Filter>
  );
}

export function ResetButton({ disabled, onClick }: { disabled: boolean; onClick: () => void }) {
  return (
    <button onClick={onClick} disabled={disabled}
      className="btn-ghost flex items-center gap-1.5 px-2.5 py-1.5 text-xs disabled:opacity-40">
      <RotateCcw size={13} /> Reset
    </button>
  );
}

export function PeriodChips({ value, onChange }: { value: TopMoversPeriod; onChange: (id: TopMoversPeriod) => void }) {
  return (
    <div className="flex flex-wrap gap-1.5 px-4">
      {PERIODS.map((p) => (
        <button key={p.id} onClick={() => onChange(p.id)}
          className={clsx('rounded-full px-3 py-1 text-xs font-medium transition-colors', value === p.id
            ? 'bg-accent/20 text-accent-light'
            : 'bg-bg-elevated text-text-secondary hover:text-text-primary')}>
          {p.label}
        </button>
      ))}
    </div>
  );
}

export function Pager({ page, pages, pageSize, total, onPage }: {
  page: number; pages: number; pageSize: number; total: number; onPage: (page: number) => void;
}) {
  const first = total ? (page - 1) * pageSize + 1 : 0;
  const last = Math.min(page * pageSize, total);
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 border-t border-bg-border px-4 py-3 text-xs text-text-muted">
      <span>{total ? `Showing ${first}–${last} of ${total} companies` : 'No companies'}</span>
      <div className="flex items-center gap-2">
        <button onClick={() => onPage(page - 1)} disabled={page <= 1}
          className="btn-ghost flex items-center gap-1 px-2 py-1 disabled:opacity-40">
          <ChevronLeft size={13} /> Prev
        </button>
        <span>Page {page} of {pages}</span>
        <button onClick={() => onPage(page + 1)} disabled={page >= pages}
          className="btn-ghost flex items-center gap-1 px-2 py-1 disabled:opacity-40">
          Next <ChevronRight size={13} />
        </button>
      </div>
    </div>
  );
}
