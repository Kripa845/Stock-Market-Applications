// Building blocks of the Technical Charts terminal: the right-hand tool rail and the
// panels it opens (watchlist, movers, symbol details, sectors, broker activity).
import { useEffect, useMemo, useRef, useState } from 'react';
import {
  ChevronDown, ChevronUp, ExternalLink, Info,
  Landmark, LayoutGrid, List, Loader2, Newspaper, Rocket, Search, X,
  type LucideIcon,
} from 'lucide-react';
import clsx from 'clsx';
import { formatDistanceToNow } from 'date-fns';

import CompanyLogo from '../companies/CompanyLogo';
import type { Company } from '../../types/company';
import type { IndexRow } from '../../api/marketIndices';
import { marketApi, type BrokerRow, type BrokerWindow } from '../../api/market';
import { analysisApi } from '../../api/analysis';
import { newsApi } from '../../api/news';

// ─── Formatting ──────────────────────────────────────────────────────────────

// Values arrive as numbers or decimal strings; a missing value is shown as "—", never 0.
export function fmt(value: string | number | null | undefined, signed = false, digits = 2) {
  if (value == null || value === '') return '—';
  const n = Number(value);
  if (!Number.isFinite(n)) return '—';
  const text = n.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits });
  return signed && n > 0 ? `+${text}` : text;
}

const compact = new Intl.NumberFormat('en-IN', { notation: 'compact', maximumFractionDigits: 2 });
export const fmtCompact = (value: number | null | undefined) =>
  value == null || !Number.isFinite(value) ? '—' : compact.format(value);

export const toneText = (value: number | null) =>
  value === null || value === 0 ? 'text-text-secondary' : value > 0 ? 'text-up' : 'text-down';

const tonePill = (value: number | null) =>
  value === null || value === 0 ? 'bg-bg-elevated text-text-secondary' : value > 0 ? 'bg-up/10 text-up' : 'bg-down/10 text-down';

function ChangePill({ value }: { value: number | null }) {
  return (
    <span className={clsx('inline-block min-w-[58px] rounded px-1.5 py-0.5 text-center font-mono text-[11px] tabular-nums', tonePill(value))}>
      {value === null ? '—' : `${fmt(value, true)}%`}
    </span>
  );
}

// ─── Symbol rows ─────────────────────────────────────────────────────────────

/** One symbol in the terminal: an index or a company. */
export interface ListRow {
  key: string;            // "index:NEPSE" / "company:NABIL"
  kind: 'index' | 'company';
  code: string;           // index code or company symbol
  name: string;
  group: string;          // "Indices" or the company's sector
  ltp: number | null;
  ch: number | null;
  chPct: number | null;
  company?: Company;
  isSubIndex?: boolean;
  date?: string | null;   // session date (indices)
  spark?: number[];       // recent closes, oldest first (indices)
}

export function companyRow(company: Company): ListRow {
  // The serializer's change is the movers-ranked one; fall back to the last two closes.
  const spark = company.sparkline ?? [];
  const prev = spark.length > 1 ? spark[spark.length - 2] : null;
  const ch = company.price_change ?? (company.latest_price !== null && prev !== null ? company.latest_price - prev : null);
  const chPct = company.price_change_percent ?? (ch !== null && prev ? (ch / prev) * 100 : null);
  return {
    key: `company:${company.symbol}`, kind: 'company', code: company.symbol, name: company.name,
    group: company.sector || 'Other', ltp: company.latest_price, ch, chPct, company,
  };
}

export function indexRow(row: IndexRow, isSubIndex: boolean): ListRow {
  return {
    key: `index:${row.code}`, kind: 'index', code: row.code, name: row.name, group: 'Indices',
    ltp: row.close, ch: row.ch, chPct: row.ch_pct, isSubIndex, date: row.date,
    spark: (row.sparkline ?? []).map(Number),
  };
}

// Indices have no logos, so each gets a two-letter monogram: "HydroPower" -> "HY",
// "Development Bank" -> "DB", "Hotels And Tourism" -> "HT".
const MONOGRAM_STOPWORDS = new Set(['and', 'of', 'the', 'index', 'subindex', 'sub-index']);

export function monogram(row: Pick<ListRow, 'name' | 'code'>) {
  const words = row.name.split(/[\s&/-]+/).filter((word) => word && !MONOGRAM_STOPWORDS.has(word.toLowerCase()));
  const text = words.length > 1 ? words[0][0] + words[1][0] : (words[0] ?? row.code).slice(0, 2);
  return text.toUpperCase();
}

export function RowIcon({ row, size = 'md' }: { row: ListRow; size?: 'md' | 'lg' }) {
  if (row.company) {
    return <CompanyLogo symbol={row.code} name={row.name} logoUrl={row.company.logo_url} size={size === 'lg' ? 'md' : 'sm'} />;
  }
  return (
    <span className={clsx(
      'flex shrink-0 items-center justify-center rounded-lg bg-bg-elevated font-sans font-semibold tracking-wide text-text-secondary',
      size === 'lg' ? 'h-10 w-10 text-xs' : 'h-8 w-8 text-[11px]',
    )}>
      {monogram(row)}
    </span>
  );
}

// ─── Panel frame ─────────────────────────────────────────────────────────────

export type PanelId = 'watchlist' | 'movers' | 'details' | 'sectors' | 'brokers' | 'news';

export const PANELS: { id: PanelId; label: string; short: string; icon: LucideIcon }[] = [
  { id: 'watchlist', label: 'Watchlist', short: 'Watchlist', icon: List },
  { id: 'movers', label: 'Top Movers', short: 'Movers', icon: Rocket },
  { id: 'details', label: 'Symbol Details', short: 'Details', icon: Info },
  { id: 'sectors', label: 'Sectors', short: 'Sectors', icon: LayoutGrid },
  { id: 'brokers', label: 'Broker Activity', short: 'Brokers', icon: Landmark },
  { id: 'news', label: 'News', short: 'News', icon: Newspaper },
];

export function PanelFrame({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="border-b border-bg-border px-3 py-2.5">
        <h2 className="text-sm font-semibold text-text-primary">{title}</h2>
        {subtitle && <p className="mt-0.5 truncate text-[11px] text-text-muted">{subtitle}</p>}
      </div>
      {children}
    </div>
  );
}

const Empty = ({ children }: { children: React.ReactNode }) => (
  <p className="px-3 py-8 text-center text-xs text-text-muted">{children}</p>
);

// ─── Tool rail ───────────────────────────────────────────────────────────────

export function ToolRail({ active, onSelect }: {
  active: PanelId | null;
  onSelect: (id: PanelId) => void;
}) {
  return (
    <nav aria-label="Chart tools" className="flex w-[68px] shrink-0 flex-col items-center gap-1 border-l border-bg-border bg-bg-secondary px-1.5 py-2">
      {PANELS.map(({ id, label, short, icon: Icon }) => {
        const on = active === id;
        return (
          <button
            key={id}
            type="button"
            onClick={() => onSelect(id)}
            aria-label={label}
            aria-pressed={on}
            title={label}
            className={clsx(
              'flex w-full flex-col items-center gap-1 rounded-lg px-1 py-2 text-[10px] font-medium transition-colors',
              on ? 'bg-accent/15 text-accent-light' : 'text-text-muted hover:bg-white/[0.04] hover:text-text-primary',
            )}
          >
            <Icon size={18} strokeWidth={1.75} />
            <span className="leading-none">{short}</span>
          </button>
        );
      })}
    </nav>
  );
}

// ─── Watchlist ───────────────────────────────────────────────────────────────

// "Banking SubIndex" -> "Banking", "NEPSE Index" -> "NEPSE": index codes are long and truncate badly.
export const indexLabel = (row: ListRow) => row.name.replace(/ ?Sub-?Index$/i, '').replace(/ Index$/i, '') || row.code;

type ListFilter = 'all' | 'indices' | 'companies';
type SortKey = 'default' | 'name' | 'ltp' | 'chPct';

const direction = (row: ListRow) => Math.sign(row.chPct ?? row.ch ?? 0);
const sparkOf = (row: ListRow) => row.spark ?? row.company?.sparkline ?? [];

/** ▲ 0.21% pill (or ▲ +4.67 (+0.17%) with the points change). */
export function ChangeBadge({ ch, chPct, withPoints = false, className }: {
  ch: number | null; chPct: number | null; withPoints?: boolean; className?: string;
}) {
  const tone = chPct ?? ch;
  const up = tone !== null && tone > 0;
  const down = tone !== null && tone < 0;
  return (
    <span className={clsx(
      'inline-flex items-center gap-1 whitespace-nowrap rounded-md px-1.5 py-0.5 font-mono tabular-nums',
      up ? 'bg-up/10 text-up' : down ? 'bg-down/10 text-down' : 'bg-bg-elevated text-text-secondary',
      className,
    )}>
      <span className="text-[8px] leading-none">{up ? '▲' : down ? '▼' : '■'}</span>
      {withPoints
        ? <>{fmt(ch, true)} ({chPct === null ? '—' : `${fmt(chPct, true)}%`})</>
        : chPct === null ? '—' : `${fmt(Math.abs(chPct))}%`}
    </span>
  );
}

function Sparkline({ data, up, width = 72, height = 24, area = false }: {
  data: number[]; up: boolean; width?: number; height?: number; area?: boolean;
}) {
  if (data.length < 2) return <span style={{ width, height }} className="shrink-0" aria-hidden />;
  const min = Math.min(...data);
  const range = Math.max(...data) - min || 1;
  const points = data.map((value, i) => `${((i / (data.length - 1)) * width).toFixed(1)},${(height - 2 - ((Number(value) - min) / range) * (height - 4)).toFixed(1)}`);
  const color = up ? '#26a69a' : '#ef5350';
  return (
    <svg viewBox={`0 0 ${width} ${height}`} style={{ width, height }} className="shrink-0 overflow-visible" aria-hidden>
      {area && <polygon points={`0,${height} ${points.join(' ')} ${width},${height}`} fill={color} fillOpacity={0.12} />}
      <polyline points={points.join(' ')} fill="none" stroke={color} strokeWidth={1.5} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

/** Advancing / unchanged / declining stocks. */
function MarketBreadth({ rows }: { rows: ListRow[] }) {
  const stocks = rows.filter((row) => row.kind === 'company' && (row.chPct !== null || row.ch !== null));
  if (stocks.length === 0) return null;
  const up = stocks.filter((row) => direction(row) > 0).length;
  const down = stocks.filter((row) => direction(row) < 0).length;
  const flat = stocks.length - up - down;
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-xs">
        <span className="text-text-secondary">Market breadth</span>
        <span className="flex items-center gap-3 font-mono tabular-nums">
          <span className="text-up" title="Advancing">▲ {up}</span>
          <span className="text-text-secondary" title="Unchanged">■ {flat}</span>
          <span className="text-down" title="Declining">▼ {down}</span>
        </span>
      </div>
      <div className="flex h-1.5 gap-1" role="img" aria-label={`${up} advancing, ${flat} unchanged, ${down} declining`}>
        {up > 0 && <span className="rounded-full bg-up" style={{ flexGrow: up }} />}
        {flat > 0 && <span className="rounded-full bg-text-muted/40" style={{ flexGrow: flat }} />}
        {down > 0 && <span className="rounded-full bg-down" style={{ flexGrow: down }} />}
      </div>
    </div>
  );
}

function NepseCard({ row, active, onSelect }: { row: ListRow; active: boolean; onSelect: (row: ListRow) => void }) {
  return (
    <button
      type="button"
      onClick={() => onSelect(row)}
      aria-current={active ? 'true' : undefined}
      className={clsx(
        'flex w-full items-center justify-between gap-3 rounded-xl border bg-bg-card px-4 py-3.5 text-left transition-colors',
        active ? 'border-accent ring-1 ring-accent/40' : 'border-bg-border hover:border-accent/40',
      )}
    >
      <span className="min-w-0">
        <span className="block text-[10px] font-semibold uppercase tracking-[0.14em] text-text-muted">NEPSE Index</span>
        <span className="mt-1.5 block font-mono text-2xl font-semibold leading-none tabular-nums text-text-primary">{fmt(row.ltp)}</span>
        <ChangeBadge ch={row.ch} chPct={row.chPct} withPoints className="mt-2.5 text-[11px]" />
      </span>
      <Sparkline data={sparkOf(row)} up={direction(row) >= 0} width={120} height={48} area />
    </button>
  );
}

function SymbolRow({ row, active, onSelect }: { row: ListRow; active: boolean; onSelect: (row: ListRow) => void }) {
  const isIndex = row.kind === 'index';
  return (
    <button
      type="button"
      onClick={() => onSelect(row)}
      aria-current={active ? 'true' : undefined}
      title={`${row.code} · ${row.name}`}
      className={clsx(
        'flex w-full items-center gap-3 rounded-xl border px-2.5 py-2 text-left transition-colors',
        active ? 'border-accent bg-accent/[0.07]' : 'border-transparent hover:bg-white/[0.035]',
      )}
    >
      <RowIcon row={row} />
      <span className="min-w-0 flex-1 leading-tight">
        <span className={clsx('block truncate text-[13px] font-semibold text-text-primary', !isIndex && 'font-mono')}>
          {isIndex ? indexLabel(row) : row.code}
        </span>
        <span className="mt-0.5 block truncate text-[11px] text-text-muted">
          {isIndex ? (row.isSubIndex ? 'Sub-index' : 'Index') : row.name}
        </span>
      </span>
      <Sparkline data={sparkOf(row)} up={direction(row) >= 0} />
      <span className="flex w-[84px] shrink-0 flex-col items-end gap-1">
        <span className="font-mono text-[13px] font-semibold tabular-nums text-text-primary">{fmt(row.ltp)}</span>
        <ChangeBadge ch={row.ch} chPct={row.chPct} className="text-[10.5px]" />
      </span>
    </button>
  );
}

function SortHeader({ label, sortKey, sort, onSort, className }: {
  label: string; sortKey: SortKey; sort: { key: SortKey; desc: boolean }; onSort: (key: SortKey) => void; className?: string;
}) {
  const on = sort.key === sortKey;
  return (
    <button
      type="button"
      onClick={() => onSort(sortKey)}
      title={`Sort by ${label.toLowerCase()}`}
      className={clsx('inline-flex items-center gap-0.5 uppercase hover:text-text-primary', on && 'text-accent-light', className)}
    >
      {label}
      {on && (sort.desc ? <ChevronDown size={11} /> : <ChevronUp size={11} />)}
    </button>
  );
}

export function WatchlistPanel({ rows, sectors, selectedKey, loading, onSelect }: {
  rows: ListRow[];
  sectors: string[];
  selectedKey: string | undefined;
  loading: boolean;
  onSelect: (row: ListRow) => void;
}) {
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<ListFilter>('all');
  const [sector, setSector] = useState('');
  const [sort, setSort] = useState<{ key: SortKey; desc: boolean }>({ key: 'default', desc: false });
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const searchRef = useRef<HTMLInputElement>(null);

  // "/" focuses the filter, as the hint in the box says.
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      if (event.key !== '/' || target?.closest('input, textarea, select, [contenteditable="true"]')) return;
      event.preventDefault();
      searchRef.current?.focus();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const nepse = rows.find((row) => row.key === 'index:NEPSE');
  const counts = {
    all: rows.length,
    indices: rows.filter((row) => row.kind === 'index').length,
    companies: rows.filter((row) => row.kind === 'company').length,
  };

  const groups = useMemo(() => {
    const q = search.trim().toLowerCase();
    const matches = (row: ListRow) =>
      (filter === 'all' || (filter === 'indices') === (row.kind === 'index'))
      && (!sector || (row.kind === 'company' && row.group === sector))
      && (!q || row.code.toLowerCase().includes(q) || row.name.toLowerCase().includes(q)
        || row.group.toLowerCase().includes(q) || (row.kind === 'index' && indexLabel(row).toLowerCase().includes(q)));
    const sorted = (list: ListRow[]) => {
      if (sort.key === 'default') return list;
      const factor = sort.desc ? -1 : 1;
      return [...list].sort((a, b) => {
        if (sort.key === 'name') return (a.kind === 'index' ? indexLabel(a) : a.code).localeCompare(b.kind === 'index' ? indexLabel(b) : b.code) * factor;
        const left = sort.key === 'ltp' ? a.ltp : a.chPct;
        const right = sort.key === 'ltp' ? b.ltp : b.chPct;
        if (left === null) return 1;
        if (right === null) return -1;
        return (left - right) * factor;
      });
    };
    // NEPSE has its own card above the list unless the user is searching.
    const list = rows.filter((row) => matches(row) && !(row === nepse && !q));
    return [
      { id: 'indices', label: 'Indices', rows: sorted(list.filter((row) => row.kind === 'index')) },
      { id: 'companies', label: sector || 'Stocks', rows: sorted(list.filter((row) => row.kind === 'company')) },
    ].filter((group) => group.rows.length > 0);
  }, [rows, search, filter, sector, sort, nepse]);

  const showCard = Boolean(nepse) && !search.trim() && filter !== 'companies' && !sector;
  const shown = groups.reduce((total, group) => total + group.rows.length, 0) + (showCard ? 1 : 0);
  const filtered = Boolean(search.trim()) || filter !== 'all' || Boolean(sector);
  const reset = () => { setSearch(''); setFilter('all'); setSector(''); };
  const onSort = (key: SortKey) =>
    setSort((current) => (current.key !== key ? { key, desc: key !== 'name' }
      : current.desc === (key !== 'name') ? { key, desc: !current.desc } : { key: 'default', desc: false }));

  const tabs: { id: ListFilter; label: string; count: number }[] = [
    { id: 'all', label: 'All', count: counts.all },
    { id: 'indices', label: 'Indices', count: counts.indices },
    { id: 'companies', label: 'Stocks', count: counts.companies },
  ];

  return (
    <div className="flex h-full min-h-0 flex-col">
      {/* Header, breadth, filter, tabs */}
      <div className="space-y-4 border-b border-bg-border px-5 pb-4 pt-4">
        <div className="flex items-center gap-2">
          <h2 className="flex-1 text-base font-semibold text-text-primary">Watchlist</h2>
          <span className="rounded-full bg-bg-elevated px-2.5 py-0.5 font-mono text-xs tabular-nums text-text-secondary">{rows.length}</span>
        </div>

        <MarketBreadth rows={rows} />

        <div className="relative">
          <Search size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
          <input
            ref={searchRef}
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            onKeyDown={(event) => { if (event.key === 'Escape') { setSearch(''); event.currentTarget.blur(); } }}
            placeholder="Filter watchlist"
            aria-label="Filter watchlist"
            className="h-10 w-full rounded-xl border border-bg-border bg-bg-card pl-9 pr-10 text-[13px] text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-accent/70 focus:ring-2 focus:ring-accent/20"
          />
          {search ? (
            <button type="button" onClick={() => setSearch('')} aria-label="Clear filter" className="absolute right-2.5 top-1/2 -translate-y-1/2 rounded p-0.5 text-text-muted hover:text-text-primary">
              <X size={14} />
            </button>
          ) : (
            <kbd className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 rounded border border-bg-border px-1.5 font-mono text-[10px] text-text-muted">/</kbd>
          )}
        </div>

        <div role="tablist" aria-label="Symbol type" className="flex rounded-xl bg-bg-elevated p-1">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={filter === tab.id}
              onClick={() => { setFilter(tab.id); if (tab.id !== 'companies') setSector(''); }}
              className={clsx(
                'flex flex-1 items-center justify-center gap-2 rounded-lg px-2 py-1.5 text-[13px] font-medium transition-colors',
                filter === tab.id ? 'bg-bg-card text-accent-light shadow-sm' : 'text-text-secondary hover:text-text-primary',
              )}
            >
              {tab.label}
              <span className="font-mono text-[11px] tabular-nums text-text-muted">{tab.count}</span>
            </button>
          ))}
        </div>

        {filter === 'companies' && sectors.length > 0 && (
          <select
            value={sector}
            onChange={(event) => setSector(event.target.value)}
            aria-label="Filter by sector"
            className="h-9 w-full rounded-xl border border-bg-border bg-bg-card px-3 text-xs text-text-primary outline-none focus:border-accent/70"
          >
            <option value="">All sectors</option>
            {sectors.map((name) => <option key={name} value={name}>{name}</option>)}
          </select>
        )}
      </div>

      {/* List */}
      <div className="min-h-0 flex-1 overflow-y-auto">
        {showCard && nepse && (
          <div className="px-5 pt-4">
            <NepseCard row={nepse} active={nepse.key === selectedKey} onSelect={onSelect} />
          </div>
        )}

        <div className="sticky top-0 z-10 mt-3 flex items-center gap-3 border-b border-bg-border bg-bg-secondary px-7 py-2.5 text-[11px] font-semibold uppercase tracking-wider text-text-muted">
          <SortHeader label="Symbol" sortKey="name" sort={sort} onSort={onSort} className="flex-1" />
          <span className="w-[72px] text-center">Trend</span>
          <span className="flex w-[84px] justify-end gap-1">
            <SortHeader label="LTP" sortKey="ltp" sort={sort} onSort={onSort} />
            <span>·</span>
            <SortHeader label="Chg" sortKey="chPct" sort={sort} onSort={onSort} />
          </span>
        </div>

        {loading && rows.length === 0 ? (
          <div className="space-y-1 px-3 pt-2">
            {Array.from({ length: 9 }, (_, i) => (
              <div key={i} className="flex items-center gap-3 px-2.5 py-2.5">
                <span className="skeleton h-8 w-8 shrink-0 rounded-lg" />
                <span className="flex-1 space-y-1.5"><span className="skeleton block h-3 w-20" /><span className="skeleton block h-2 w-14" /></span>
                <span className="skeleton h-4 w-[72px]" />
                <span className="w-[84px] space-y-1.5"><span className="skeleton ml-auto block h-3 w-16" /><span className="skeleton ml-auto block h-3.5 w-12" /></span>
              </div>
            ))}
          </div>
        ) : shown === 0 ? (
          <div className="flex flex-col items-center gap-2 px-6 py-14 text-center">
            <span className="flex h-11 w-11 items-center justify-center rounded-full bg-bg-elevated text-text-muted"><Search size={17} /></span>
            <p className="text-sm font-medium text-text-primary">No symbols match</p>
            <p className="text-xs text-text-muted">Try another name or sector.</p>
            <button type="button" onClick={reset} className="mt-1 rounded-lg border border-accent/40 px-3 py-1 text-xs font-medium text-accent-light hover:bg-accent/10">
              Reset filters
            </button>
          </div>
        ) : (
          <div className="pb-3">
            {groups.map((group) => {
              const isCollapsed = collapsed[group.id];
              return (
                <section key={group.id} className="px-3">
                  <button
                    type="button"
                    onClick={() => setCollapsed((current) => ({ ...current, [group.id]: !current[group.id] }))}
                    aria-expanded={!isCollapsed}
                    className="flex w-full items-center gap-2 px-3 pb-2 pt-4 text-[11px] font-semibold uppercase tracking-wider text-text-secondary hover:text-text-primary"
                  >
                    <ChevronDown size={13} className={clsx('transition-transform', isCollapsed && '-rotate-90')} />
                    {group.label}
                    <span className="rounded-md bg-bg-elevated px-1.5 py-px font-mono text-[10px] font-normal tabular-nums">{group.rows.length}</span>
                  </button>
                  {!isCollapsed && (
                    <div className="space-y-0.5">
                      {group.rows.map((row) => (
                        <SymbolRow key={row.key} row={row} active={row.key === selectedKey} onSelect={onSelect} />
                      ))}
                    </div>
                  )}
                </section>
              );
            })}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="flex items-center justify-between gap-2 border-t border-bg-border px-5 py-2.5 text-xs text-text-muted">
        <span>Showing <span className="font-semibold text-text-primary">{shown}</span> of {rows.length}</span>
        {filtered ? (
          <button type="button" onClick={reset} className="font-medium text-accent-light hover:underline">Clear filters</button>
        ) : (
          <span className="flex items-center gap-1.5"><span className="h-1.5 w-1.5 rounded-full bg-text-muted" />End-of-session prices</span>
        )}
      </div>
    </div>
  );
}

// ─── Top movers ──────────────────────────────────────────────────────────────

export function MoversPanel({ rows, selectedKey, onSelect }: {
  rows: ListRow[];
  selectedKey: string | undefined;
  onSelect: (row: ListRow) => void;
}) {
  const [side, setSide] = useState<'gainers' | 'losers'>('gainers');
  const ranked = useMemo(() => {
    const priced = rows.filter((r) => r.kind === 'company' && r.chPct !== null);
    const sorted = [...priced].sort((a, b) => (b.chPct! - a.chPct!));
    return side === 'gainers'
      ? sorted.filter((r) => r.chPct! > 0)
      : sorted.reverse().filter((r) => r.chPct! < 0);
  }, [rows, side]);

  return (
    <PanelFrame title="Top Movers" subtitle="Tracked companies, latest session">
      <div className="flex gap-1 border-b border-bg-border p-2">
        {(['gainers', 'losers'] as const).map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => setSide(s)}
            aria-pressed={side === s}
            className={clsx(
              'flex-1 rounded px-2 py-1 text-xs font-medium capitalize transition-colors',
              side === s
                ? s === 'gainers' ? 'bg-up/15 text-up' : 'bg-down/15 text-down'
                : 'text-text-secondary hover:bg-blue-500/10 hover:text-text-primary',
            )}
          >
            {s}
          </button>
        ))}
      </div>
      <ol className="min-h-0 flex-1 overflow-y-auto">
        {ranked.length === 0 ? (
          <li><Empty>No {side} in the latest session.</Empty></li>
        ) : ranked.map((row, i) => (
          <li key={row.key}>
            <button
              type="button"
              onClick={() => onSelect(row)}
              title={row.name}
              className={clsx(
                'flex w-full items-center gap-2 border-b border-bg-border/60 px-3 py-2 text-left text-xs transition-colors',
                row.key === selectedKey ? 'bg-accent/10' : 'hover:bg-blue-500/10',
              )}
            >
              <span className="w-4 text-right font-mono text-[10px] text-text-muted">{i + 1}</span>
              <RowIcon row={row} />
              <span className="min-w-0 flex-1">
                <span className="block font-mono font-semibold text-accent-light">{row.code}</span>
                <span className="block truncate text-[10px] text-text-muted">{row.name}</span>
              </span>
              <span className="text-right">
                <span className="block font-mono text-text-primary">{fmt(row.ltp, false, 1)}</span>
                <ChangePill value={row.chPct} />
              </span>
            </button>
          </li>
        ))}
      </ol>
    </PanelFrame>
  );
}

// ─── Symbol details ──────────────────────────────────────────────────────────

/** A daily bar with numbers (index bars can have missing OHLC/volume). */
export interface DailyBar {
  date: string;
  open: number | null; high: number | null; low: number | null; close: number;
  volume: number | null; turnover: number | null;
}

export interface Week52 { high: number | null; highDate: string | null; low: number | null; lowDate: string | null }

function RangeMeter({ label, low, high, value, lowNote, highNote }: {
  label: string; low: number | null; high: number | null; value: number | null; lowNote?: string | null; highNote?: string | null;
}) {
  const ok = low !== null && high !== null && value !== null && high > low;
  const pos = ok ? Math.min(100, Math.max(0, ((value! - low!) / (high! - low!)) * 100)) : null;
  return (
    <div className="space-y-1.5">
      <p className="text-[10px] uppercase tracking-wide text-text-muted">{label}</p>
      <div className="relative h-1.5 rounded-full bg-gradient-to-r from-down/40 via-bg-border to-up/40">
        {pos !== null && (
          <span className="absolute top-1/2 h-3 w-1 -translate-x-1/2 -translate-y-1/2 rounded bg-text-primary" style={{ left: `${pos}%` }} />
        )}
      </div>
      <div className="flex justify-between font-mono text-[11px]">
        <span className="text-down">{fmt(low)}{lowNote && <span className="ml-1 font-sans text-[10px] text-text-muted">{lowNote}</span>}</span>
        <span className="text-up">{highNote && <span className="mr-1 font-sans text-[10px] text-text-muted">{highNote}</span>}{fmt(high)}</span>
      </div>
    </div>
  );
}

export function DetailsPanel({ row, bars, week52, loading }: {
  row: ListRow | null;
  bars: DailyBar[];
  week52: Week52 | null;
  loading: boolean;
}) {
  if (!row) return <PanelFrame title="Symbol Details"><Empty>Pick a symbol.</Empty></PanelFrame>;
  const last = bars[bars.length - 1];
  const prev = bars[bars.length - 2];
  const ch = last && prev ? last.close - prev.close : null;
  const chPct = ch !== null && prev?.close ? (ch / prev.close) * 100 : null;
  const recent = bars.slice(-20).map((b) => b.volume).filter((v): v is number => v !== null);
  const avgVolume = recent.length ? recent.reduce((s, v) => s + v, 0) / recent.length : null;

  const stats: [string, React.ReactNode][] = last ? [
    ['Open', fmt(last.open)],
    ['High', fmt(last.high)],
    ['Low', fmt(last.low)],
    ['Prev close', fmt(prev?.close)],
    ['Volume', fmtCompact(last.volume)],
    ['Avg vol (20)', fmtCompact(avgVolume)],
    ['Turnover', last.turnover !== null ? `Rs ${fmtCompact(last.turnover)}` : '—'],
    ['Sessions', bars.length.toLocaleString()],
  ] : [];

  return (
    <PanelFrame title="Symbol Details" subtitle={last ? `As of ${last.date}` : undefined}>
      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-3">
        <div className="flex items-center gap-3">
          <RowIcon row={row} />
          <div className="min-w-0">
            <p className="font-mono text-sm font-semibold text-text-primary">{row.code}</p>
            <p className="truncate text-[11px] text-text-muted" title={row.name}>{row.name}</p>
          </div>
        </div>
        {row.kind === 'company' && row.group && (
          <span className="badge border border-bg-border bg-bg-elevated text-text-secondary">{row.group}</span>
        )}

        {!last ? (
          loading ? <div className="flex justify-center py-6"><Loader2 size={18} className="animate-spin text-accent" /></div>
            : <Empty>No stored price data yet.</Empty>
        ) : (
          <>
            <div>
              <p className="font-mono text-2xl font-semibold text-text-primary">{fmt(last.close)}</p>
              <p className={clsx('font-mono text-xs', toneText(ch))}>
                {fmt(ch, true)} ({fmt(chPct, true)}%)
                {prev && <span className="ml-1 font-sans text-text-muted">vs {prev.date}</span>}
              </p>
            </div>

            <RangeMeter label="Day range" low={last.low} high={last.high} value={last.close} />
            {week52 && (
              <RangeMeter
                label="52-week range" low={week52.low} high={week52.high} value={last.close}
                lowNote={week52.lowDate} highNote={week52.highDate}
              />
            )}

            <dl className="grid grid-cols-2 gap-x-3 gap-y-2">
              {stats.map(([label, value]) => (
                <div key={label} className="rounded border border-bg-border bg-bg-elevated px-2 py-1.5">
                  <dt className="text-[10px] uppercase tracking-wide text-text-muted">{label}</dt>
                  <dd className="font-mono text-xs text-text-primary">{value}</dd>
                </div>
              ))}
            </dl>
          </>
        )}
      </div>
    </PanelFrame>
  );
}

// ─── Sectors ─────────────────────────────────────────────────────────────────

export function SectorsPanel({ rows, selectedKey, onSelect }: {
  rows: ListRow[];
  selectedKey: string | undefined;
  onSelect: (row: ListRow) => void;
}) {
  const sectors = useMemo(
    () => rows.filter((r) => r.isSubIndex).sort((a, b) => (b.chPct ?? -Infinity) - (a.chPct ?? -Infinity)),
    [rows],
  );
  const maxAbs = Math.max(0.01, ...sectors.map((r) => Math.abs(r.chPct ?? 0)));

  return (
    <PanelFrame title="Sectors" subtitle="NEPSE sub-indices by % change · click to chart">
      <ul className="min-h-0 flex-1 overflow-y-auto">
        {sectors.length === 0 ? (
          <li><Empty>No sub-index data yet.</Empty></li>
        ) : sectors.map((row) => {
          const width = row.chPct === null ? 0 : (Math.abs(row.chPct) / maxAbs) * 50;
          const up = (row.chPct ?? 0) >= 0;
          return (
            <li key={row.key}>
              <button
                type="button"
                onClick={() => onSelect(row)}
                title={row.name}
                className={clsx(
                  'w-full space-y-1 border-b border-bg-border/60 px-3 py-2 text-left text-xs transition-colors',
                  row.key === selectedKey ? 'bg-accent/10' : 'hover:bg-blue-500/10',
                )}
              >
                <span className="flex items-center justify-between gap-2">
                  <span className="truncate text-text-primary">{row.name.replace(/ ?Sub-?Index$/i, '')}</span>
                  <span className={clsx('font-mono', toneText(row.chPct))}>{row.chPct === null ? '—' : `${fmt(row.chPct, true)}%`}</span>
                </span>
                {/* Diverging bar: centre line = 0% */}
                <span className="relative block h-1 rounded-full bg-bg-elevated">
                  <span className="absolute inset-y-0 left-1/2 w-px bg-bg-border" />
                  <span
                    className={clsx('absolute inset-y-0 rounded-full', up ? 'left-1/2 bg-up' : 'right-1/2 bg-down')}
                    style={{ width: `${width}%` }}
                  />
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </PanelFrame>
  );
}

// ─── Broker activity ─────────────────────────────────────────────────────────

// The API ranks top_buyers / top_sellers by gross bought / sold quantity, so that is what is shown.
function BrokerList({ title, rows, tone }: { title: string; rows: BrokerRow[]; tone: 'up' | 'down' }) {
  const quantity = (b: BrokerRow) => (tone === 'up' ? b.buy_quantity : b.sell_quantity);
  const amount = (b: BrokerRow) => (tone === 'up' ? b.buy_amount : b.sell_amount);
  return (
    <div>
      <p className={clsx('px-3 pb-1 pt-3 text-[10px] font-semibold uppercase tracking-wide', tone === 'up' ? 'text-up' : 'text-down')}>{title}</p>
      {rows.length === 0 ? <Empty>None in this window.</Empty> : (
        <ul>
          {rows.map((b) => (
            <li key={b.broker} className="flex items-center gap-2 border-b border-bg-border/60 px-3 py-1.5 text-xs" title={b.broker_name}>
              <span className="w-7 shrink-0 rounded bg-bg-elevated py-0.5 text-center font-mono text-[10px] text-text-secondary">{b.broker}</span>
              <span className="min-w-0 flex-1 truncate text-text-primary">{b.broker_name || `Broker ${b.broker}`}</span>
              <span className="text-right">
                <span className={clsx('block font-mono', tone === 'up' ? 'text-up' : 'text-down')}>
                  {fmtCompact(quantity(b))}
                </span>
                <span className="block font-mono text-[10px] text-text-muted">Rs {fmtCompact(amount(b))}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function BrokersPanel({ row }: { row: ListRow | null }) {
  const symbol = row?.kind === 'company' ? row.code : null;
  const [windows, setWindows] = useState<BrokerWindow[] | null>(null);
  const [sessions, setSessions] = useState<number | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!symbol) return;
    let cancelled = false;
    setWindows(null);
    setError('');
    marketApi.brokers(symbol)
      .then((data) => { if (!cancelled) setWindows(data.windows); })
      .catch(() => { if (!cancelled) setError('Unable to load broker activity.'); });
    return () => { cancelled = true; };
  }, [symbol]);

  if (!symbol) {
    return <PanelFrame title="Broker Activity"><Empty>Broker activity is available for companies, not indices.</Empty></PanelFrame>;
  }

  const current = windows?.find((w) => w.sessions === sessions) ?? windows?.[0] ?? null;

  return (
    <PanelFrame
      title="Broker Activity"
      subtitle={current?.start_date ? `${symbol} · ${current.start_date} → ${current.end_date}` : symbol}
    >
      {windows && windows.length > 1 && (
        <div className="flex gap-1 border-b border-bg-border p-2">
          {windows.map((w) => (
            <button
              key={w.sessions}
              type="button"
              onClick={() => setSessions(w.sessions)}
              aria-pressed={w === current}
              className={clsx(
                'flex-1 rounded px-2 py-1 text-xs font-medium transition-colors',
                w === current ? 'bg-accent/20 text-accent-light' : 'text-text-secondary hover:bg-blue-500/10 hover:text-text-primary',
              )}
            >
              {w.sessions} sessions
            </button>
          ))}
        </div>
      )}
      <div className="min-h-0 flex-1 overflow-y-auto">
        {error ? <Empty>{error}</Empty>
          : !windows ? <div className="flex justify-center py-8"><Loader2 size={18} className="animate-spin text-accent" /></div>
          : !current || current.total_trades === 0 ? <Empty>No floorsheet trades stored for {symbol} in this window.</Empty>
          : (
            <>
              <div className="grid grid-cols-3 gap-2 border-b border-bg-border p-3 text-center">
                {[
                  ['Turnover', current.total_amount !== null ? `Rs ${fmtCompact(current.total_amount)}` : '—'],
                  ['Volume', fmtCompact(current.total_quantity)],
                  ['Trades', fmtCompact(current.total_trades)],
                ].map(([label, value]) => (
                  <div key={label}>
                    <p className="text-[10px] uppercase tracking-wide text-text-muted">{label}</p>
                    <p className="font-mono text-xs text-text-primary">{value}</p>
                  </div>
                ))}
              </div>
              {current.sessions_available < current.sessions && (
                <p className="px-3 pt-2 text-[10px] text-text-muted">
                  Only {current.sessions_available} of {current.sessions} sessions stored.
                </p>
              )}
              <BrokerList title="Top buyers (shares bought)" rows={current.top_buyers} tone="up" />
              <BrokerList title="Top sellers (shares sold)" rows={current.top_sellers} tone="down" />
            </>
          )}
      </div>
    </PanelFrame>
  );
}

// ─── News ────────────────────────────────────────────────────────────────────

interface NewsItem {
  id: number;
  headline: string;
  source: string;
  url: string;
  publishedAt: string | null;
  sentimentLabel: string | null;     // null or "pending" until sentiment has been scored
  match?: number;           // company-match confidence (0-1), company tab only
}

const SENTIMENT_TONE: Record<string, string> = {
  positive: 'bg-up/10 text-up',
  negative: 'bg-down/10 text-down',
  neutral: 'bg-bg-elevated text-text-secondary',
};

function timeAgo(iso: string | null) {
  if (!iso) return '';
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? '' : formatDistanceToNow(date, { addSuffix: true });
}

export function NewsPanel({ row }: { row: ListRow | null }) {
  const company = row?.kind === 'company' ? row.company ?? null : null;
  const [tab, setTab] = useState<'company' | 'market'>(company ? 'company' : 'market');
  const [items, setItems] = useState<NewsItem[] | null>(null);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState('');

  // Follow the chart: a company opens its own news, an index the market feed.
  useEffect(() => { setTab(company ? 'company' : 'market'); }, [company?.id]);

  const companyId = tab === 'company' ? company?.id ?? null : null;

  const fetchPage = (pageNo: number) => (companyId
    ? analysisApi.getCategorizedCompanyNews(companyId, pageNo).then((data) => ({
      more: data.next !== null,
      items: data.results.map((a): NewsItem => ({
        id: a.id, headline: a.headline, source: a.source, url: a.url,
        publishedAt: a.published_at, sentimentLabel: a.sentiment_label, match: a.confidence,
      })),
    }))
    : newsApi.getNews({ page: pageNo }).then((data) => ({
      more: Boolean(data.next),
      items: data.results.map((a): NewsItem => ({
        id: a.id, headline: a.headline, source: a.source, url: a.url,
        publishedAt: a.published_at, sentimentLabel: a.sentiment_label,
      })),
    })));

  useEffect(() => {
    if (tab === 'company' && !companyId) return;
    let cancelled = false;
    setItems(null);
    setError('');
    setPage(1);
    fetchPage(1)
      .then((result) => { if (!cancelled) { setItems(result.items); setHasMore(result.more); } })
      .catch(() => { if (!cancelled) setError('Unable to load news. Check your permissions.'); });
    return () => { cancelled = true; };
    // fetchPage reads tab/companyId, both listed.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, companyId]);

  const loadMore = () => {
    setLoadingMore(true);
    fetchPage(page + 1)
      .then((result) => {
        setItems((current) => {
          const seen = new Set((current ?? []).map((item) => item.id));
          return [...(current ?? []), ...result.items.filter((item) => !seen.has(item.id))];
        });
        setHasMore(result.more);
        setPage((p) => p + 1);
      })
      .catch(() => setError('Unable to load more news.'))
      .finally(() => setLoadingMore(false));
  };

  return (
    <PanelFrame title="News" subtitle={tab === 'company' && company ? `Articles tagged to ${company.symbol}` : 'Latest market news'}>
      <div className="flex gap-1 border-b border-bg-border p-2">
        {([
          ['company', company ? company.symbol : 'Company'],
          ['market', 'Market'],
        ] as const).map(([id, label]) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            disabled={id === 'company' && !company}
            title={id === 'company' && !company ? 'Pick a company to see its news' : undefined}
            aria-pressed={tab === id}
            className={clsx(
              'flex-1 rounded px-2 py-1 text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40',
              tab === id ? 'bg-accent/20 text-accent-light' : 'text-text-secondary enabled:hover:bg-blue-500/10 enabled:hover:text-text-primary',
            )}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {error && !items ? <Empty>{error}</Empty>
          : !items ? <div className="flex justify-center py-8"><Loader2 size={18} className="animate-spin text-accent" /></div>
          : items.length === 0 ? (
            <Empty>{tab === 'company' ? `No news is tagged to ${company?.symbol ?? 'this company'} yet.` : 'No news yet.'}</Empty>
          ) : (
            <>
              <ul>
                {items.map((item) => {
                  const tone = item.sentimentLabel ? SENTIMENT_TONE[item.sentimentLabel] : undefined;
                  return (
                    <li key={item.id} className="border-b border-bg-border/60">
                      <a
                        href={item.url}
                        target="_blank"
                        rel="noreferrer"
                        className="group block px-3 py-2.5 transition-colors hover:bg-blue-500/10"
                      >
                        <p className="text-xs font-medium leading-snug text-text-primary group-hover:text-accent-light">
                          {item.headline}
                          <ExternalLink size={10} className="ml-1 inline align-baseline text-text-muted opacity-0 group-hover:opacity-100" />
                        </p>
                        <p className="mt-1 flex flex-wrap items-center gap-x-1.5 gap-y-1 text-[10px] text-text-muted">
                          <span>{item.source}</span>
                          {item.publishedAt && (
                            <>
                              <span aria-hidden="true">·</span>
                              <span title={new Date(item.publishedAt).toLocaleString()}>{timeAgo(item.publishedAt)}</span>
                            </>
                          )}
                          {tone && <span className={clsx('rounded px-1.5 py-px capitalize', tone)}>{item.sentimentLabel}</span>}
                          {item.match !== undefined && (
                            <span title="How sure the tagger is that this article is about the company">{Math.round(item.match * 100)}% match</span>
                          )}
                        </p>
                      </a>
                    </li>
                  );
                })}
              </ul>
              {hasMore && (
                <div className="p-3">
                  <button
                    type="button"
                    onClick={loadMore}
                    disabled={loadingMore}
                    className="w-full rounded border border-bg-border py-1.5 text-xs text-text-secondary hover:bg-blue-500/10 hover:text-text-primary disabled:opacity-50"
                  >
                    {loadingMore ? 'Loading…' : 'Load more'}
                  </button>
                </div>
              )}
              {error && <p className="px-3 pb-3 text-center text-[11px] text-down">{error}</p>}
            </>
          )}
      </div>
    </PanelFrame>
  );
}
