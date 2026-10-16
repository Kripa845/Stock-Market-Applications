// Floorsheet: every stored trade (contract) for the tracked companies, one day at a time,
// with totals and top brokers for whatever the filters select.
import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertTriangle, ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight, Download, RefreshCw, Search, X,
} from 'lucide-react';

import PageHeader from '../components/common/PageHeader';
import BrokerBadge from '../components/brokers/BrokerBadge';
import CompanyLogo from '../components/companies/CompanyLogo';
import { formatCount, formatNprCompact, formatTradeDate } from '../components/market/format';
import { apiClient } from '../api/client';
import { getCompanies } from '../api/companies';
import type { Company } from '../types/company';
import type { FloorsheetTransaction } from '../types';

const PAGE_SIZE = 50;

interface FloorsheetRow extends FloorsheetTransaction {
  symbol: string;
  trade_time: string | null;
}

interface BrokerTotal {
  broker_code: string;
  name: string;
  short_name: string;
  logo_url: string | null;
  quantity: number;
  amount: string | number;
  trades: number;
}

interface FloorsheetSummary {
  date: string | null;
  trades: number;
  quantity: number | null;
  amount: string | number | null;
  companies: number;
  first_trade: string | null;
  last_trade: string | null;
  top_buyers: BrokerTotal[];
  top_sellers: BrokerTotal[];
  latest_date: string | null;
  dates: string[];
}

type SortKey = 'trade_time' | 'quantity' | 'rate' | 'amount';

interface Filters {
  date: string;          // '' until the latest date is known
  symbol: string;
  buyer: string;
  seller: string;
  search: string;
}

const EMPTY_FILTERS: Omit<Filters, 'date'> = { symbol: '', buyer: '', seller: '', search: '' };

// Trade times are stored in UTC; NEPSE runs on Nepal time.
const timeFormat = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'Asia/Kathmandu', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
});
const tradeTime = (iso: string | null) => (iso ? timeFormat.format(new Date(iso)) : '—');

const rs = (value: string | number | null | undefined) =>
  value == null ? '—' : `Rs ${Number(value).toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;

// The companies API pages by 20; the symbol filter needs all of them.
async function allActiveCompanies(): Promise<Company[]> {
  const all: Company[] = [];
  for (let page = 1; ; page += 1) {
    const data = await getCompanies({ status: 'active', page });
    all.push(...data.results);
    if (!data.next) return all;
  }
}

function toParams(filters: Filters) {
  return {
    date: filters.date || undefined,
    symbol: filters.symbol || undefined,
    buyer_broker: filters.buyer.trim() || undefined,
    seller_broker: filters.seller.trim() || undefined,
    search: filters.search.trim() || undefined,
  };
}

// ─── Pieces ──────────────────────────────────────────────────────────────────

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="card">
      <p className="text-xs text-text-secondary">{label}</p>
      <p className="mt-1 font-mono text-lg font-semibold text-text-primary">{value}</p>
      {hint && <p className="text-[11px] text-text-muted">{hint}</p>}
    </div>
  );
}

function TopBrokers({ title, rows, tone, onPick }: {
  title: string;
  rows: BrokerTotal[] | undefined;
  tone: 'up' | 'down';
  onPick: (code: string) => void;
}) {
  return (
    <div className="card">
      <h2 className={`mb-3 text-sm font-semibold ${tone === 'up' ? 'text-up' : 'text-down'}`}>{title}</h2>
      {!rows ? (
        <div className="space-y-2">{Array.from({ length: 5 }, (_, i) => <div key={i} className="skeleton h-7" />)}</div>
      ) : rows.length === 0 ? (
        <p className="py-4 text-center text-xs text-text-muted">No trades for these filters.</p>
      ) : (
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-bg-border text-text-muted">
              <th className="py-1.5 text-left font-medium">Broker</th>
              <th className="py-1.5 text-right font-medium">Shares</th>
              <th className="py-1.5 text-right font-medium">Amount</th>
              <th className="py-1.5 text-right font-medium">Trades</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.broker_code} className="table-row">
                <td className="py-1.5">
                  <button type="button" onClick={() => onPick(row.broker_code)} title={`Filter by broker ${row.broker_code}`} className="text-left hover:opacity-80">
                    <BrokerBadge brokerCode={row.broker_code} name={row.name} shortName={row.short_name} logoUrl={row.logo_url} />
                  </button>
                </td>
                <td className={`py-1.5 text-right font-mono ${tone === 'up' ? 'text-up' : 'text-down'}`}>{formatCount(row.quantity)}</td>
                <td className="py-1.5 text-right font-mono text-text-primary">{formatNprCompact(row.amount)}</td>
                <td className="py-1.5 text-right font-mono text-text-secondary">{formatCount(row.trades)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function SortHeader({ label, sortKey, ordering, onSort, align = 'right' }: {
  label: string; sortKey: SortKey; ordering: string; onSort: (key: SortKey) => void; align?: 'left' | 'right';
}) {
  const active = ordering.replace('-', '') === sortKey;
  const Icon = !active ? ArrowUpDown : ordering.startsWith('-') ? ArrowDown : ArrowUp;
  return (
    <th className={`px-3 py-2 font-medium ${align === 'right' ? 'text-right' : 'text-left'}`}
      aria-sort={active ? (ordering.startsWith('-') ? 'descending' : 'ascending') : 'none'}>
      <button type="button" onClick={() => onSort(sortKey)}
        className={`inline-flex items-center gap-1 hover:text-text-primary ${active ? 'text-text-primary' : ''}`}>
        {label}
        <Icon size={11} className={active ? '' : 'opacity-40'} />
      </button>
    </th>
  );
}

const fieldClass =
  'w-full rounded-md border border-bg-border bg-bg-card px-3 py-2 text-sm text-text-primary outline-none transition focus:border-accent';

// ─── Page ────────────────────────────────────────────────────────────────────

export default function FloorsheetPage() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [filters, setFilters] = useState<Filters>({ date: '', ...EMPTY_FILTERS });
  // Text inputs apply after a short pause, so typing does not fire a request per key.
  const [draft, setDraft] = useState({ buyer: '', seller: '', search: '' });
  const [ordering, setOrdering] = useState('-trade_time');
  const [page, setPage] = useState(1);
  const [version, setVersion] = useState(0);

  const [summary, setSummary] = useState<FloorsheetSummary | null>(null);
  const [rows, setRows] = useState<FloorsheetRow[] | null>(null);
  const [count, setCount] = useState(0);
  const [error, setError] = useState('');
  // The date the summary filled in itself: its summary is already loaded, so no refetch for it.
  const autoDate = useRef<string | null>(null);

  useEffect(() => {
    allActiveCompanies().then(setCompanies).catch(() => setCompanies([]));
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      setFilters((f) => (f.buyer === draft.buyer && f.seller === draft.seller && f.search === draft.search ? f : { ...f, ...draft }));
      setPage(1);
    }, 400);
    return () => clearTimeout(timer);
  }, [draft]);

  // Summary: without a date the backend picks the latest one and says which.
  useEffect(() => {
    if (autoDate.current && autoDate.current === filters.date) {
      autoDate.current = null;
      return;
    }
    let cancelled = false;
    setSummary(null);
    setError('');
    apiClient.get<FloorsheetSummary>('/floorsheet/summary/', { params: toParams(filters) })
      .then(({ data }) => {
        if (cancelled) return;
        setSummary(data);
        if (!filters.date && data.date) {
          autoDate.current = data.date;
          setFilters((f) => ({ ...f, date: data.date! }));
        }
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err?.response?.status === 403
          ? 'You do not have permission to view floorsheet data.'
          : 'Unable to load the floorsheet summary.');
      });
    return () => { cancelled = true; };
  }, [filters, version]);

  // Trades: wait for the date so the first page is not an all-history query.
  useEffect(() => {
    if (!filters.date) return;
    let cancelled = false;
    setRows(null);
    apiClient.get<{ count: number; results: FloorsheetRow[] }>('/floorsheet/', {
      params: { ...toParams(filters), ordering: `${ordering},-id`, page, page_size: PAGE_SIZE },
    })
      .then(({ data }) => { if (!cancelled) { setRows(data.results); setCount(data.count); } })
      .catch(() => { if (!cancelled) { setRows([]); setError('Unable to load floorsheet trades.'); } });
    return () => { cancelled = true; };
  }, [filters, ordering, page, version]);

  const setFilter = (patch: Partial<Filters>) => {
    setFilters((f) => ({ ...f, ...patch }));
    setPage(1);
  };
  const pickBroker = (side: 'buyer' | 'seller', code: string) => {
    setDraft((d) => ({ ...d, [side]: code }));
    setFilter({ [side]: code });
  };
  const clearFilters = () => {
    setDraft({ buyer: '', seller: '', search: '' });
    setFilters((f) => ({ ...f, ...EMPTY_FILTERS }));
    setPage(1);
  };
  const onSort = (key: SortKey) => {
    setOrdering((current) => (current === `-${key}` ? key : `-${key}`));
    setPage(1);
  };

  const filtersActive = Boolean(filters.symbol || filters.buyer || filters.seller || filters.search);
  const pages = Math.max(1, Math.ceil(count / PAGE_SIZE));
  const firstRow = count === 0 ? 0 : (page - 1) * PAGE_SIZE + 1;
  const lastRow = Math.min(page * PAGE_SIZE, count);
  const sessionLabel = summary?.first_trade && summary?.last_trade
    ? `${tradeTime(summary.first_trade)} – ${tradeTime(summary.last_trade)} NPT`
    : undefined;
  const averageRate = useMemo(() => {
    if (!summary?.quantity || summary.amount == null) return null;
    return Number(summary.amount) / summary.quantity;
  }, [summary]);

  return (
    <div className="space-y-5">
      <PageHeader
        title="Floorsheet"
        subtitle="Every stored trade for the tracked companies: buyer and seller broker, quantity, rate and amount."
        actions={
          <>
            <button type="button" onClick={() => setVersion((v) => v + 1)} className="btn-ghost flex items-center gap-2 text-xs">
              <RefreshCw size={13} className={!summary || !rows ? 'animate-spin' : ''} />
              Refresh
            </button>
            <Link to="/reports" className="btn-ghost flex items-center gap-2 text-xs">
              <Download size={13} /> Export
            </Link>
          </>
        }
      />

      {error && (
        <div role="alert" className="flex items-center gap-2 rounded-md border border-down/30 bg-down/10 px-4 py-3 text-sm text-down">
          <AlertTriangle size={15} /> {error}
        </div>
      )}

      {/* Filters */}
      <div className="card grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-[160px_180px_1fr_1fr_1.4fr_auto] xl:items-end">
        <label className="block">
          <span className="mb-1 block text-xs text-text-secondary">Date</span>
          <select
            value={filters.date}
            onChange={(e) => setFilter({ date: e.target.value })}
            className={fieldClass}
            disabled={!summary?.dates.length}
          >
            {!filters.date && <option value="">Loading…</option>}
            {(summary?.dates ?? (filters.date ? [filters.date] : [])).map((d) => (
              <option key={d} value={d}>{formatTradeDate(d)}{d === summary?.latest_date ? ' (latest)' : ''}</option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="mb-1 block text-xs text-text-secondary">Symbol</span>
          <select value={filters.symbol} onChange={(e) => setFilter({ symbol: e.target.value })} className={fieldClass}>
            <option value="">All companies</option>
            {companies.map((c) => <option key={c.id} value={c.symbol}>{c.symbol} — {c.name}</option>)}
          </select>
        </label>
        <label className="block">
          <span className="mb-1 block text-xs text-text-secondary">Buyer broker no.</span>
          <input inputMode="numeric" value={draft.buyer} onChange={(e) => setDraft((d) => ({ ...d, buyer: e.target.value }))}
            placeholder="e.g. 58" className={`${fieldClass} font-mono`} />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs text-text-secondary">Seller broker no.</span>
          <input inputMode="numeric" value={draft.seller} onChange={(e) => setDraft((d) => ({ ...d, seller: e.target.value }))}
            placeholder="e.g. 45" className={`${fieldClass} font-mono`} />
        </label>
        <label className="block">
          <span className="mb-1 block text-xs text-text-secondary">Search</span>
          <span className="relative block">
            <Search size={14} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
            <input type="search" value={draft.search} onChange={(e) => setDraft((d) => ({ ...d, search: e.target.value }))}
              placeholder="Contract no., symbol or broker" className={`${fieldClass} pl-9`} />
          </span>
        </label>
        <button type="button" onClick={clearFilters} disabled={!filtersActive}
          className="btn-ghost flex items-center justify-center gap-1.5 border border-bg-border py-2 disabled:cursor-not-allowed disabled:opacity-40">
          <X size={13} /> Clear
        </button>
      </div>

      {/* Totals */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <Stat label="Trades" value={summary ? formatCount(summary.trades) : '—'} hint={summary?.date ? formatTradeDate(summary.date) : undefined} />
        <Stat label="Shares traded" value={summary ? formatCount(summary.quantity ?? 0) : '—'} />
        <Stat label="Turnover" value={summary ? formatNprCompact(summary.amount ?? 0) : '—'} />
        <Stat label="Average rate" value={averageRate !== null ? `Rs ${averageRate.toFixed(2)}` : '—'} hint={filters.symbol ? undefined : 'across all selected symbols'} />
        <Stat label="Companies" value={summary ? String(summary.companies) : '—'} hint={sessionLabel} />
      </div>

      {/* Top brokers */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <TopBrokers title="Top Buyers" rows={summary?.top_buyers} tone="up" onPick={(code) => pickBroker('buyer', code)} />
        <TopBrokers title="Top Sellers" rows={summary?.top_sellers} tone="down" onPick={(code) => pickBroker('seller', code)} />
      </div>

      {/* Trades */}
      <div className="card overflow-hidden p-0">
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-bg-border px-4 py-3">
          <h2 className="text-sm font-semibold text-text-primary">All Transactions</h2>
          <span className="text-xs text-text-muted">
            {rows ? `${formatCount(firstRow)}–${formatCount(lastRow)} of ${formatCount(count)}` : 'Loading…'}
          </span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[860px] text-xs">
            <thead className="bg-bg-elevated text-text-muted">
              <tr>
                <th className="px-3 py-2 text-left font-medium">#</th>
                <SortHeader label="Time" sortKey="trade_time" ordering={ordering} onSort={onSort} align="left" />
                <th className="px-3 py-2 text-left font-medium">Contract no.</th>
                <th className="px-3 py-2 text-left font-medium">Symbol</th>
                <th className="px-3 py-2 text-left font-medium">Buyer</th>
                <th className="px-3 py-2 text-left font-medium">Seller</th>
                <SortHeader label="Qty" sortKey="quantity" ordering={ordering} onSort={onSort} />
                <SortHeader label="Rate" sortKey="rate" ordering={ordering} onSort={onSort} />
                <SortHeader label="Amount" sortKey="amount" ordering={ordering} onSort={onSort} />
              </tr>
            </thead>
            <tbody>
              {!rows ? (
                Array.from({ length: 10 }, (_, i) => (
                  <tr key={i} className="border-b border-bg-border">
                    <td colSpan={9} className="px-3 py-2.5"><div className="skeleton h-4" /></td>
                  </tr>
                ))
              ) : rows.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-3 py-12 text-center text-sm text-text-muted">
                    No trades match these filters.
                    {filtersActive && (
                      <button type="button" onClick={clearFilters} className="ml-2 text-accent-light hover:underline">Clear filters</button>
                    )}
                  </td>
                </tr>
              ) : rows.map((row, i) => (
                <tr key={row.id} className="table-row">
                  <td className="px-3 py-1.5 font-mono text-text-muted">{firstRow + i}</td>
                  <td className="px-3 py-1.5 font-mono text-text-secondary">{tradeTime(row.trade_time)}</td>
                  <td className="px-3 py-1.5 font-mono text-text-muted">{row.transaction_id}</td>
                  <td className="px-3 py-1.5">
                    <Link to={`/companies/${row.symbol}`} className="flex items-center gap-2 font-mono font-semibold text-accent-light hover:underline">
                      <CompanyLogo symbol={row.symbol} logoUrl={companies.find((c) => c.symbol === row.symbol)?.logo_url} size="sm" />
                      {row.symbol}
                    </Link>
                  </td>
                  <td className="px-3 py-1.5">
                    <button type="button" onClick={() => pickBroker('buyer', row.buyer_broker)} title="Filter by this buyer" className="hover:opacity-80">
                      <BrokerBadge brokerCode={row.buyer_broker} name={row.buyer_broker_name} shortName={row.buyer_broker_short_name} logoUrl={row.buyer_broker_logo_url} />
                    </button>
                  </td>
                  <td className="px-3 py-1.5">
                    <button type="button" onClick={() => pickBroker('seller', row.seller_broker)} title="Filter by this seller" className="hover:opacity-80">
                      <BrokerBadge brokerCode={row.seller_broker} name={row.seller_broker_name} shortName={row.seller_broker_short_name} logoUrl={row.seller_broker_logo_url} />
                    </button>
                  </td>
                  <td className="px-3 py-1.5 text-right font-mono text-text-primary">{formatCount(row.quantity)}</td>
                  <td className="px-3 py-1.5 text-right font-mono text-text-primary">{Number(row.rate).toFixed(2)}</td>
                  <td className="px-3 py-1.5 text-right font-mono text-text-primary">{rs(row.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex items-center justify-between gap-2 border-t border-bg-border px-4 py-2.5 text-xs text-text-secondary">
          <span>Page {page} of {formatCount(pages)}</span>
          <div className="flex gap-1">
            <button type="button" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1 || !rows}
              className="btn-ghost flex items-center gap-1 border border-bg-border disabled:opacity-40">
              <ChevronLeft size={13} /> Prev
            </button>
            <button type="button" onClick={() => setPage((p) => Math.min(pages, p + 1))} disabled={page >= pages || !rows}
              className="btn-ghost flex items-center gap-1 border border-bg-border disabled:opacity-40">
              Next <ChevronRight size={13} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
