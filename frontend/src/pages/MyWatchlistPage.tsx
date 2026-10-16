import { useCallback, useEffect, useMemo, useState, type FormEvent, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import {
  AlertTriangle, ArrowDown, ArrowUp, ChevronsUpDown, Pencil, Plus, PlusCircle, RefreshCw, Search, Star, Trash2, X,
} from 'lucide-react';
import CompanyLogo from '../components/companies/CompanyLogo';
import Sparkline from '../components/common/Sparkline';
import { formatCount, formatPrice } from '../components/market/format';
import { getCompanies } from '../api/companies';
import {
  marketApi,
  type NamedWatchlist,
  type WatchlistItemRow,
  type WatchlistSummary,
} from '../api/market';
import { useAuth } from '../contexts/AuthContext';
import type { Company } from '../types/company';

type SortKey =
  | 'symbol' | 'ltp' | 'high' | 'low' | 'change' | 'change_pct' | 'volume' | 'turnover'
  | 'units' | 'wacc' | 'current_value' | 'investment' | 'profit';

const EMPTY_SUMMARY: WatchlistSummary = {
  total_units: 0, average_wacc: 0, current_value: 0, investment: 0, profit: 0, profit_pct: 0,
};

const num = (value: number | string | null | undefined) =>
  value === null || value === undefined ? null : Number(value);

/** Indian grouping, up to 2 decimals (2,18,14,297.3). */
const money = (value: number | string | null | undefined) => {
  const n = num(value);
  return n === null || Number.isNaN(n) ? '—' : n.toLocaleString('en-IN', { maximumFractionDigits: 2 });
};

const signed = (value: number | null, text: string) => (value !== null && value > 0 ? `+${text}` : text);

const tone = (value: number | null) =>
  value === null || value === 0 ? 'text-text-secondary' : value > 0 ? 'text-up' : 'text-down';

const errorText = (error: unknown, fallback: string) => {
  const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
  return typeof detail === 'string' ? detail : fallback;
};

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: ReactNode }) {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onMouseDown={onClose}>
      <div className="card w-full max-w-md space-y-4" onMouseDown={(event) => event.stopPropagation()}>
        <div className="flex items-center justify-between">
          <h3 className="text-base font-semibold text-text-primary">{title}</h3>
          <button onClick={onClose} className="text-text-secondary hover:text-text-primary" aria-label="Close"><X size={16} /></button>
        </div>
        {children}
      </div>
    </div>
  );
}

const inputClass =
  'w-full rounded-md border border-bg-border bg-bg-primary px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-teal-500 focus:outline-none';

function HoldingFields({ units, wacc, setUnits, setWacc }: {
  units: string; wacc: string; setUnits: (v: string) => void; setWacc: (v: string) => void;
}) {
  return (
    <div className="grid grid-cols-2 gap-3">
      <label className="space-y-1 text-xs text-text-secondary">
        <span>Units</span>
        <input type="number" min={0} step={1} value={units} onChange={(e) => setUnits(e.target.value)} className={inputClass} placeholder="0" />
      </label>
      <label className="space-y-1 text-xs text-text-secondary">
        <span>WACC (Rs.)</span>
        <input type="number" min={0} step="0.01" value={wacc} onChange={(e) => setWacc(e.target.value)} className={inputClass} placeholder="0" />
      </label>
    </div>
  );
}

const holdingFrom = (units: string, wacc: string) => ({
  units: units === '' ? 0 : Math.max(0, Math.floor(Number(units))),
  wacc: wacc === '' ? 0 : Math.max(0, Number(wacc)),
});

function AddCompanyModal({ watchlist, savedSymbols, onClose, onAdded }: {
  watchlist: NamedWatchlist;
  savedSymbols: Set<string>;
  onClose: () => void;
  onAdded: () => void;
}) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<Company[]>([]);
  const [searching, setSearching] = useState(false);
  const [selected, setSelected] = useState<Company | null>(null);
  const [units, setUnits] = useState('');
  const [wacc, setWacc] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    setSearching(true);
    const timer = window.setTimeout(() => {
      getCompanies({ search: query.trim() || undefined, status: 'active' })
        .then((data) => { if (!cancelled) setResults(data.results); })
        .catch(() => { if (!cancelled) setError('Unable to search companies.'); })
        .finally(() => { if (!cancelled) setSearching(false); });
    }, 250);
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [query]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!selected) return;
    setSaving(true);
    setError('');
    try {
      await marketApi.addWatchlistItem(watchlist.id, selected.symbol, holdingFrom(units, wacc));
      onAdded();
    } catch (err) {
      setError(errorText(err, 'Unable to add the company.'));
      setSaving(false);
    }
  };

  return (
    <Modal title={`Add company to ${watchlist.name}`} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <div className="relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
          <input autoFocus value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search symbol or company name" className={`${inputClass} pl-8`} />
        </div>
        <div className="max-h-64 overflow-y-auto rounded-md border border-bg-border">
          {results.map((company) => {
            const saved = savedSymbols.has(company.symbol);
            const active = selected?.id === company.id;
            return (
              <button
                key={company.id}
                type="button"
                disabled={saved}
                onClick={() => setSelected(company)}
                className={`flex w-full items-center gap-2 border-b border-bg-border px-3 py-2 text-left text-sm last:border-b-0 ${active ? 'bg-teal-500/15' : 'hover:bg-bg-elevated'} ${saved ? 'cursor-not-allowed opacity-50' : ''}`}
              >
                <CompanyLogo symbol={company.symbol} name={company.name} logoUrl={company.logo_url} size="sm" />
                <span className="min-w-0 flex-1">
                  <span className="block font-mono font-semibold text-accent-light">{company.symbol}</span>
                  <span className="block truncate text-xs text-text-muted">{company.name}</span>
                </span>
                {saved && <span className="text-xs text-text-muted">Added</span>}
              </button>
            );
          })}
          {!searching && results.length === 0 && <p className="px-3 py-6 text-center text-sm text-text-muted">No companies match.</p>}
          {searching && results.length === 0 && <p className="px-3 py-6 text-center text-sm text-text-muted">Searching…</p>}
        </div>
        {selected && (
          <div className="space-y-3">
            <p className="text-xs text-text-secondary">Holding for <span className="font-mono font-semibold text-text-primary">{selected.symbol}</span> (optional)</p>
            <HoldingFields units={units} wacc={wacc} setUnits={setUnits} setWacc={setWacc} />
          </div>
        )}
        {error && <p className="text-sm text-down">{error}</p>}
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="btn-ghost">Cancel</button>
          <button type="submit" disabled={!selected || saving} className="rounded-md bg-teal-600 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-500 disabled:opacity-50">
            {saving ? 'Adding…' : 'Add'}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function EditHoldingModal({ row, onClose, onSaved }: { row: WatchlistItemRow; onClose: () => void; onSaved: () => void }) {
  const [units, setUnits] = useState(String(row.units ?? 0));
  const [wacc, setWacc] = useState(String(num(row.wacc) ?? 0));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setSaving(true);
    setError('');
    try {
      await marketApi.updateWatchlistItem(row.watchlist_id, row.id, holdingFrom(units, wacc));
      onSaved();
    } catch (err) {
      setError(errorText(err, 'Unable to save the holding.'));
      setSaving(false);
    }
  };

  return (
    <Modal title={`Edit ${row.symbol}`} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <HoldingFields units={units} wacc={wacc} setUnits={setUnits} setWacc={setWacc} />
        {error && <p className="text-sm text-down">{error}</p>}
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="btn-ghost">Cancel</button>
          <button type="submit" disabled={saving} className="rounded-md bg-teal-600 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-500 disabled:opacity-50">
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function NameModal({ title, initial, onClose, onSubmit }: {
  title: string; initial: string; onClose: () => void; onSubmit: (name: string) => Promise<void>;
}) {
  const [name, setName] = useState(initial);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    setError('');
    try {
      await onSubmit(name.trim());
    } catch (err) {
      setError(errorText(err, 'Unable to save the watchlist.'));
      setSaving(false);
    }
  };

  return (
    <Modal title={title} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <input autoFocus maxLength={60} value={name} onChange={(e) => setName(e.target.value)} placeholder="Watchlist name" className={inputClass} />
        {error && <p className="text-sm text-down">{error}</p>}
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="btn-ghost">Cancel</button>
          <button type="submit" disabled={!name.trim() || saving} className="rounded-md bg-teal-600 px-4 py-2 text-sm font-semibold text-white hover:bg-teal-500 disabled:opacity-50">
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function SummaryCard({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="rounded-md border border-bg-border bg-bg-elevated px-4 py-3">
      <p className="text-xs text-text-secondary">{label}</p>
      <div className="mt-1 text-base font-semibold text-sky-400">{children}</div>
    </div>
  );
}

const ALIGN = { left: 'text-left', right: 'text-right', center: 'text-center' } as const;

const COLUMNS: { key: SortKey | null; label: string; align: 'left' | 'right' | 'center' }[] = [
  { key: 'symbol', label: 'Symbol', align: 'left' },
  { key: null, label: '', align: 'left' },
  { key: 'ltp', label: 'LTP', align: 'right' },
  { key: 'high', label: 'High', align: 'right' },
  { key: 'low', label: 'Low', align: 'right' },
  { key: 'change', label: 'CH', align: 'right' },
  { key: 'change_pct', label: 'CH %', align: 'center' },
  { key: 'volume', label: 'Quantity', align: 'right' },
  { key: 'turnover', label: 'Turnover', align: 'right' },
  { key: 'units', label: 'Units', align: 'right' },
  { key: 'wacc', label: 'WACC', align: 'right' },
  { key: 'current_value', label: 'Current Value', align: 'right' },
  { key: 'investment', label: 'Investment', align: 'right' },
  { key: 'profit', label: 'Profit', align: 'right' },
  { key: null, label: 'Action', align: 'center' },
];

export default function MyWatchlistPage() {
  const { hasPermission } = useAuth();
  const canAdd = hasPermission('add_watchlist');
  const canRemove = hasPermission('remove_watchlist');

  const [lists, setLists] = useState<NamedWatchlist[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [rows, setRows] = useState<WatchlistItemRow[]>([]);
  const [summary, setSummary] = useState<WatchlistSummary>(EMPTY_SUMMARY);
  const [loadingLists, setLoadingLists] = useState(true);
  const [loadingRows, setLoadingRows] = useState(false);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');
  const [sort, setSort] = useState<{ key: SortKey; dir: 'asc' | 'desc' } | null>(null);
  const [modal, setModal] = useState<
    | { kind: 'add' }
    | { kind: 'edit'; row: WatchlistItemRow }
    | { kind: 'create' }
    | { kind: 'rename'; list: NamedWatchlist }
    | null
  >(null);

  const selected = lists.find((list) => list.id === selectedId) ?? null;

  const loadLists = useCallback(async (focusId?: number) => {
    setLoadingLists(true);
    try {
      const data = await marketApi.watchlists();
      setLists(data);
      setSelectedId((current) => {
        const wanted = focusId ?? current;
        if (wanted && data.some((list) => list.id === wanted)) return wanted;
        return (data.find((list) => list.is_default) ?? data[0])?.id ?? null;
      });
      setError('');
    } catch {
      setError('Unable to load your watchlists.');
    } finally {
      setLoadingLists(false);
    }
  }, []);

  const loadRows = useCallback(async (id: number) => {
    setLoadingRows(true);
    try {
      const data = await marketApi.watchlistItems(id);
      setRows(data.rows);
      setSummary(data.summary);
      setLists((current) => current.map((list) => (list.id === id ? { ...list, item_count: data.rows.length } : list)));
      setError('');
    } catch {
      setError('Unable to load this watchlist.');
    } finally {
      setLoadingRows(false);
    }
  }, []);

  useEffect(() => { loadLists(); }, [loadLists]);
  useEffect(() => {
    if (selectedId === null) { setRows([]); setSummary(EMPTY_SUMMARY); return; }
    loadRows(selectedId);
  }, [selectedId, loadRows]);

  const visibleRows = useMemo(() => {
    const term = search.trim().toLowerCase();
    const filtered = term
      ? rows.filter((row) => row.symbol.toLowerCase().includes(term) || row.name.toLowerCase().includes(term))
      : rows;
    if (!sort) return filtered;
    const factor = sort.dir === 'asc' ? 1 : -1;
    return [...filtered].sort((a, b) => {
      if (sort.key === 'symbol') return a.symbol.localeCompare(b.symbol) * factor;
      const left = num(a[sort.key]);
      const right = num(b[sort.key]);
      if (left === null) return 1;
      if (right === null) return -1;
      return (left - right) * factor;
    });
  }, [rows, search, sort]);

  const toggleSort = (key: SortKey) =>
    setSort((current) => (current?.key !== key ? { key, dir: 'desc' } : current.dir === 'desc' ? { key, dir: 'asc' } : null));

  const makeDefault = async (list: NamedWatchlist) => {
    if (list.is_default || !canAdd) return;
    try {
      await marketApi.updateWatchlist(list.id, { is_default: true });
      setLists((current) => current.map((item) => ({ ...item, is_default: item.id === list.id })));
    } catch (err) {
      setError(errorText(err, 'Unable to change the default watchlist.'));
    }
  };

  const deleteList = async (list: NamedWatchlist) => {
    if (!window.confirm(`Delete the watchlist "${list.name}" and its ${list.item_count ?? 0} companies?`)) return;
    try {
      await marketApi.deleteWatchlist(list.id);
      setSelectedId(null);
      await loadLists();
    } catch (err) {
      setError(errorText(err, 'Unable to delete the watchlist.'));
    }
  };

  const removeRow = async (row: WatchlistItemRow) => {
    if (!window.confirm(`Remove ${row.symbol} from ${selected?.name ?? 'this watchlist'}?`)) return;
    try {
      await marketApi.removeWatchlistItem(row.watchlist_id, row.id);
      await loadRows(row.watchlist_id);
    } catch (err) {
      setError(errorText(err, 'Unable to remove the company.'));
    }
  };

  const latestDate = rows.reduce<string | null>((max, row) => (row.trade_date && (!max || row.trade_date > max) ? row.trade_date : max), null);
  const profitPct = num(summary.profit_pct) ?? 0;

  return (
    <div className="space-y-4">
      <div className="card space-y-4">
        <div className="flex items-center gap-3">
          <span className="rounded-md bg-bg-elevated px-3 py-1.5 text-sm font-semibold text-text-primary">My Watchlist</span>
          {canAdd && (
            <button onClick={() => setModal({ kind: 'create' })} className="text-text-primary hover:text-teal-400" title="New watchlist" aria-label="New watchlist">
              <PlusCircle size={18} />
            </button>
          )}
          <button
            onClick={() => (selectedId !== null ? loadRows(selectedId) : loadLists())}
            className="ml-auto btn-ghost flex items-center gap-2"
            disabled={loadingRows || loadingLists}
          >
            <RefreshCw size={14} className={loadingRows || loadingLists ? 'animate-spin' : ''} />Refresh
          </button>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
          <SummaryCard label="Total Units">Rs. {formatCount(summary.total_units)} units</SummaryCard>
          <SummaryCard label="Average Wacc">Rs. {money(summary.average_wacc)}</SummaryCard>
          <SummaryCard label="Current Value">Rs. {money(summary.current_value)}</SummaryCard>
          <SummaryCard label="Investment">Rs. {money(summary.investment)}</SummaryCard>
          <SummaryCard label="Profit">
            <span className="flex items-center gap-3">
              <span className={tone(num(summary.profit))}>Rs. {money(summary.profit)}</span>
              <span className={`flex items-center gap-1 rounded px-2 py-0.5 text-xs ${profitPct < 0 ? 'bg-down/10 text-down' : 'bg-sky-500/10 text-sky-400'}`}>
                {profitPct < 0 ? <ArrowDown size={12} /> : <ArrowUp size={12} />}{Math.abs(profitPct)}%
              </span>
            </span>
          </SummaryCard>
        </div>

        <div className="flex flex-wrap gap-2">
          {lists.map((list) => {
            const active = list.id === selectedId;
            return (
              <div
                key={list.id}
                className={`flex min-w-[220px] items-center gap-2 rounded-md border px-3 py-2 text-sm ${active ? 'border-teal-700 bg-teal-900/40 text-text-primary' : 'border-bg-border bg-bg-elevated text-text-secondary hover:text-text-primary'}`}
              >
                <button onClick={() => setSelectedId(list.id)} className="flex-1 text-left font-medium">
                  {list.name}
                  {list.item_count !== null && <span className="ml-2 text-xs text-text-muted">{list.item_count}</span>}
                </button>
                {active && canAdd && (
                  <button onClick={() => setModal({ kind: 'rename', list })} title="Rename" aria-label="Rename watchlist" className="text-text-muted hover:text-text-primary"><Pencil size={13} /></button>
                )}
                {active && canRemove && (
                  <button onClick={() => deleteList(list)} title="Delete watchlist" aria-label="Delete watchlist" className="text-text-muted hover:text-down"><Trash2 size={13} /></button>
                )}
                <button
                  onClick={() => makeDefault(list)}
                  title={list.is_default ? 'Default watchlist' : 'Make default'}
                  aria-label={list.is_default ? 'Default watchlist' : 'Make default'}
                  className={list.is_default ? 'text-text-primary' : 'text-text-muted hover:text-text-primary'}
                >
                  <Star size={15} fill={list.is_default ? 'currentColor' : 'none'} />
                </button>
              </div>
            );
          })}
        </div>

        {error && (
          <div className="flex items-center gap-2 text-sm text-down">
            <AlertTriangle size={14} />{error}
          </div>
        )}

        {selected && (
          <>
            <div className="flex flex-wrap items-end justify-between gap-2">
              <h2 className="text-base font-semibold text-text-primary">{selected.name}</h2>
              {latestDate && <span className="text-xs text-text-muted">Prices as of {latestDate} close</span>}
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <div className="relative">
                <Search size={13} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
                <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search" className={`${inputClass} w-56 py-1.5 pl-8`} />
              </div>
              {canAdd && (
                <button onClick={() => setModal({ kind: 'add' })} className="flex items-center gap-1 rounded-md bg-teal-700 px-3 py-1.5 text-xs font-semibold text-white hover:bg-teal-600">
                  <Plus size={13} />ADD
                </button>
              )}
            </div>

            <div className="overflow-x-auto rounded-md border border-bg-border">
              <table className="w-full min-w-[1250px] text-xs">
                <thead className="bg-bg-secondary">
                  <tr className="border-b border-bg-border text-text-secondary">
                    {COLUMNS.map((column, index) => {
                      const sortable = column.key !== null;
                      const active = sortable && sort?.key === column.key;
                      return (
                        <th key={index} className={`px-3 py-2.5 font-semibold uppercase ${ALIGN[column.align]}`}>
                          {sortable ? (
                            <button onClick={() => toggleSort(column.key as SortKey)} className={`inline-flex items-center gap-1 uppercase hover:text-text-primary ${active ? 'text-text-primary' : ''}`}>
                              {column.label}
                              {active ? (sort?.dir === 'asc' ? <ArrowUp size={11} /> : <ArrowDown size={11} />) : <ChevronsUpDown size={11} />}
                            </button>
                          ) : column.label}
                        </th>
                      );
                    })}
                  </tr>
                </thead>
                <tbody>
                  {visibleRows.map((row) => {
                    const change = num(row.change);
                    const changePct = num(row.change_pct);
                    const profit = num(row.profit);
                    const closes = row.sparkline.map((point) => Number(point.close));
                    const trendUp = closes.length < 2 || closes[closes.length - 1] >= closes[0];
                    return (
                      <tr key={row.id} className="border-b border-bg-border last:border-b-0 hover:bg-bg-elevated">
                        <td className="px-3 py-2">
                          <Link to={`/companies/${row.symbol}`} className="flex items-center gap-2" title={row.name}>
                            <CompanyLogo symbol={row.symbol} name={row.name} logoUrl={row.logo_url} size="sm" />
                            <span className="font-mono font-semibold text-sky-400 hover:underline">{row.symbol}</span>
                          </Link>
                        </td>
                        <td className="px-3 py-2">
                          {closes.length >= 2 ? <Sparkline data={closes} width={150} height={30} positive={trendUp} /> : <span className="text-text-muted">—</span>}
                        </td>
                        <td className="px-3 py-2 text-right font-mono font-semibold text-text-primary">{money(row.ltp)}</td>
                        <td className="px-3 py-2 text-right font-mono">{money(row.high)}</td>
                        <td className="px-3 py-2 text-right font-mono">{money(row.low)}</td>
                        <td className={`px-3 py-2 text-right font-mono ${tone(change)}`}>{change === null ? '—' : signed(change, money(change))}</td>
                        <td className="px-3 py-2 text-center">
                          {changePct === null ? <span className="text-text-muted">—</span> : (
                            <span className={`inline-flex items-center gap-1 rounded px-2 py-0.5 font-mono ${changePct > 0 ? 'bg-up/10 text-up' : changePct < 0 ? 'bg-down/10 text-down' : 'bg-bg-elevated text-text-secondary'}`}>
                              {changePct > 0 ? <ArrowUp size={11} /> : changePct < 0 ? <ArrowDown size={11} /> : null}
                              {changePct.toFixed(2)}%
                            </span>
                          )}
                        </td>
                        <td className="px-3 py-2 text-right font-mono">{formatCount(row.volume)}</td>
                        <td className="px-3 py-2 text-right font-mono">{money(row.turnover)}</td>
                        <td className="px-3 py-2 text-right font-mono">{formatCount(row.units)}</td>
                        <td className="px-3 py-2 text-right font-mono">{money(row.wacc)}</td>
                        <td className="px-3 py-2 text-right font-mono">{money(row.current_value)}</td>
                        <td className="px-3 py-2 text-right font-mono">{money(row.investment)}</td>
                        <td className="px-3 py-2 text-right font-mono">
                          <span className={tone(profit)}>{profit === null ? '—' : formatPrice(profit)}</span>{' '}
                          <span className="text-sky-400">({num(row.profit_pct) ?? 0} %)</span>
                        </td>
                        <td className="px-3 py-2">
                          <div className="flex items-center justify-center gap-2">
                            {canAdd && (
                              <button onClick={() => setModal({ kind: 'edit', row })} className="rounded bg-white p-1 text-sky-600 hover:bg-sky-50" title="Edit units / WACC" aria-label={`Edit ${row.symbol}`}>
                                <Pencil size={13} />
                              </button>
                            )}
                            {canRemove && (
                              <button onClick={() => removeRow(row)} className="rounded bg-white p-1 text-red-500 hover:bg-red-50" title="Remove" aria-label={`Remove ${row.symbol}`}>
                                <X size={13} />
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              {!loadingRows && visibleRows.length === 0 && (
                <p className="py-10 text-center text-sm text-text-muted">
                  {rows.length === 0 ? `No companies in ${selected.name} yet.${canAdd ? ' Use + ADD to add any listed company.' : ''}` : 'No companies match your search.'}
                </p>
              )}
              {loadingRows && rows.length === 0 && <p className="py-10 text-center text-sm text-text-muted">Loading…</p>}
            </div>
          </>
        )}
        {!loadingLists && lists.length === 0 && !error && (
          <p className="py-10 text-center text-sm text-text-muted">You have no watchlists yet.</p>
        )}
      </div>

      {modal?.kind === 'add' && selected && (
        <AddCompanyModal
          watchlist={selected}
          savedSymbols={new Set(rows.map((row) => row.symbol))}
          onClose={() => setModal(null)}
          onAdded={() => { setModal(null); loadRows(selected.id); }}
        />
      )}
      {modal?.kind === 'edit' && (
        <EditHoldingModal
          row={modal.row}
          onClose={() => setModal(null)}
          onSaved={() => { setModal(null); loadRows(modal.row.watchlist_id); }}
        />
      )}
      {modal?.kind === 'create' && (
        <NameModal
          title="New watchlist"
          initial=""
          onClose={() => setModal(null)}
          onSubmit={async (name) => {
            const created = await marketApi.createWatchlist(name);
            setModal(null);
            await loadLists(created.id);
          }}
        />
      )}
      {modal?.kind === 'rename' && (
        <NameModal
          title="Rename watchlist"
          initial={modal.list.name}
          onClose={() => setModal(null)}
          onSubmit={async (name) => {
            const updated = await marketApi.updateWatchlist(modal.list.id, { name });
            setLists((current) => current.map((list) => (list.id === updated.id ? { ...list, name: updated.name } : list)));
            setModal(null);
          }}
        />
      )}
    </div>
  );
}
