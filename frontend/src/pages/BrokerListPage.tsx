import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { AlertTriangle, ArrowUpRight, ChevronDown, ChevronsUpDown, ChevronUp, LayoutGrid, Search, Table2, X } from 'lucide-react';
import clsx from 'clsx';
import PageHeader from '../components/common/PageHeader';
import { BrokerLogo } from '../components/brokers/BrokerBadge';
import BrokerDirectoryCard, { displayName, hostOf, membershipLabel } from '../components/brokers/BrokerDirectoryCard';
import { BuySellBar } from '../components/brokers/BrokerTurnoverTable';
import { RankBadge } from '../components/brokers/TopBrokers';
import { formatCount, formatNprArab, formatTradeDate } from '../components/market/format';
import { formatTradeTime, selectClass } from '../components/market/TopListControls';
import { analysisApi, type BrokerListResponse, type BrokerListRow } from '../api/analysis';

// Broker Analysis -> Broker List (/brokers): every NEPSE broker.
//   Directory: cards grouped A–Z, by head-office city or membership type, with website / TMS links
//              and offices (synced by `manage.py sync_broker_directory`).
//   Activity:  turnover across the tracked companies over a recent window (BrokerListAPIView).

type View = 'directory' | 'activity';
type GroupBy = 'letter' | 'city' | 'membership' | 'none';
type Show = 'all' | 'active' | 'suspended' | 'traded';
type SortKey = 'broker_no' | 'name' | 'rank' | 'buy_amount' | 'sell_amount' | 'turnover' | 'trades';

const SHOW_LABELS: Record<Show, string> = { all: 'All', active: 'Active', suspended: 'Suspended', traded: 'Traded in period' };
const GROUP_LABELS: Record<GroupBy, string> = {
  letter: 'Name (A–Z)', city: 'Head office city', membership: 'Membership type', none: 'Broker number',
};

const COLUMNS: { key: SortKey; label: string; align: 'left' | 'right'; className?: string }[] = [
  { key: 'broker_no', label: 'No.', align: 'left' },
  { key: 'name', label: 'Broker', align: 'left' },
  { key: 'rank', label: 'Rank', align: 'left' },
  { key: 'buy_amount', label: 'Buy Amt', align: 'right', className: 'text-up' },
  { key: 'sell_amount', label: 'Sell Amt', align: 'right', className: 'text-down' },
  { key: 'turnover', label: 'Turnover', align: 'right' },
  { key: 'trades', label: 'Trades', align: 'right' },
];
const TEXT_KEYS = new Set<SortKey>(['broker_no', 'name', 'rank']);

const byNumber = (a: BrokerListRow, b: BrokerListRow) => (a.broker_no ?? 9999) - (b.broker_no ?? 9999);
const byName = (a: BrokerListRow, b: BrokerListRow) => displayName(a.name).localeCompare(displayName(b.name), 'en', { sensitivity: 'base' });

function sortValue(row: BrokerListRow, key: SortKey): number | string | null {
  if (key === 'name') return displayName(row.name).toLowerCase();
  if (key === 'broker_no') return row.broker_no;
  if (key === 'rank') return row.rank;
  return Number(row[key]);
}

function groupKey(row: BrokerListRow, groupBy: GroupBy) {
  if (groupBy === 'letter') return /[a-z]/i.test(row.name.charAt(0)) ? row.name.charAt(0).toUpperCase() : '#';
  if (groupBy === 'city') return row.city || 'Unknown';
  if (groupBy === 'membership') return row.membership_type ? `${membershipLabel(row.membership_type)} members` : 'Unknown';
  return 'All brokers';
}

function StatCard({ label, value, hint }: { label: string; value: string; hint?: React.ReactNode }) {
  return (
    <div className="card">
      <p className="text-[10px] uppercase tracking-widest text-text-muted">{label}</p>
      <p className="mt-1 font-mono text-2xl font-bold tabular-nums text-text-primary">{value}</p>
      {hint && <p className="mt-0.5 text-[11px] text-text-muted">{hint}</p>}
    </div>
  );
}

function ActivityTable({ rows, range, onSort, sort }: {
  rows: BrokerListRow[]; range: string; sort: { key: SortKey; desc: boolean }; onSort: (key: SortKey) => void;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[960px] text-xs">
        <thead>
          <tr className="border-b border-bg-border text-[11px] uppercase text-text-secondary">
            {COLUMNS.map((column) => {
              const active = sort.key === column.key;
              const Icon = !active ? ChevronsUpDown : sort.desc ? ChevronDown : ChevronUp;
              return (
                <th key={column.key} aria-sort={active ? (sort.desc ? 'descending' : 'ascending') : undefined}
                  className={`whitespace-nowrap px-2 py-3 font-semibold first:pl-4 ${column.align === 'left' ? 'text-left' : 'text-right'}`}>
                  <button type="button" onClick={() => onSort(column.key)}
                    className={clsx('inline-flex items-center gap-0.5 uppercase hover:text-text-primary', column.className, active && 'text-text-primary')}>
                    {column.label}<Icon size={11} className={active ? '' : 'opacity-50'} />
                  </button>
                </th>
              );
            })}
            <th className="w-32 px-2 py-3 text-left font-semibold">Buy / Sell</th>
            <th className="px-2 py-3 pr-4 text-left font-semibold">Website</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.broker_code} className={clsx('table-row', !row.is_active && 'opacity-60')}>
              <td className="py-2 pl-4 pr-2 font-mono text-text-secondary">{row.broker_no ?? row.broker_code}</td>
              <td className="max-w-[280px] px-2 py-2">
                <Link to={`/broker-analysis/${encodeURIComponent(row.broker_code)}${range}`}
                  title="Open in Broker Explorer" className="flex min-w-0 items-center gap-2 hover:text-accent-light">
                  <BrokerLogo brokerCode={row.broker_code} name={row.name} shortName={row.short_name} logoUrl={row.logo_url} />
                  <span className="min-w-0">
                    <span className="block truncate font-medium text-text-primary" title={row.name}>{displayName(row.name)}</span>
                    <span className="flex gap-1.5 text-[10px] text-text-muted">
                      {row.city && <span>{row.city}</span>}
                      {!row.is_active && <span className="text-down">{row.nepse_status === 'SUSPEND' ? 'Suspended' : 'Inactive'}</span>}
                      {!row.in_directory && <span className="text-yellow-400">Not in directory</span>}
                    </span>
                  </span>
                </Link>
              </td>
              <td className="px-2 py-2">{row.rank ? <RankBadge rank={row.rank} /> : <span className="text-text-muted">—</span>}</td>
              <td className="px-2 py-2 text-right font-mono">{row.rank ? formatNprArab(row.buy_amount) : '—'}</td>
              <td className="px-2 py-2 text-right font-mono">{row.rank ? formatNprArab(row.sell_amount) : '—'}</td>
              <td className="px-2 py-2 text-right font-mono font-semibold text-text-primary">{row.rank ? formatNprArab(row.turnover) : '—'}</td>
              <td className="px-2 py-2 text-right font-mono">{row.rank ? formatCount(row.trades) : '—'}</td>
              <td className="px-2 py-2">{row.rank ? <BuySellBar buy={Number(row.buy_amount)} sell={Number(row.sell_amount)} /> : null}</td>
              <td className="max-w-[180px] px-2 py-2 pr-4">
                {row.website ? (
                  <a href={row.website} target="_blank" rel="noreferrer" title={row.website}
                    className="inline-flex max-w-full items-center gap-0.5 text-accent-light hover:underline">
                    <span className="truncate">{hostOf(row.website)}</span><ArrowUpRight size={11} className="shrink-0" />
                  </a>
                ) : <span className="text-text-muted">—</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function BrokerListPage() {
  const [params, setParams] = useSearchParams();
  const days = Number(params.get('days')) || undefined;
  const view: View = params.get('view') === 'activity' ? 'activity' : 'directory';
  const [data, setData] = useState<BrokerListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [tick, setTick] = useState(0);          // bumped by Retry
  const [search, setSearch] = useState('');
  const [show, setShow] = useState<Show>('all');
  const [groupBy, setGroupBy] = useState<GroupBy>('letter');
  const [sort, setSort] = useState<{ key: SortKey; desc: boolean }>({ key: 'broker_no', desc: false });

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(false);
    analysisApi.getBrokerList(days)
      .then((response) => { if (!cancelled) setData(response); })
      .catch(() => { if (!cancelled) setError(true); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [days, tick]);

  const update = (changes: Record<string, string | null>) => {
    const next = new URLSearchParams(params);
    Object.entries(changes).forEach(([key, value]) => (value ? next.set(key, value) : next.delete(key)));
    setParams(next, { replace: true });
  };

  const results = useMemo(() => data?.results ?? [], [data]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return results.filter((row) => {
      if (show === 'active' && !row.is_active) return false;
      if (show === 'suspended' && row.is_active) return false;
      if (show === 'traded' && row.rank === null) return false;
      if (!q) return true;
      const haystack = [row.name, row.short_name, row.broker_code, row.city, row.address, row.website, ...row.branches.map((b) => b.name)];
      return haystack.join(' ').toLowerCase().includes(q);
    });
  }, [results, search, show]);

  const groups = useMemo(() => {
    const map = new Map<string, BrokerListRow[]>();
    [...filtered].sort(groupBy === 'letter' ? byName : byNumber).forEach((row) => {
      const key = groupKey(row, groupBy);
      map.set(key, [...(map.get(key) ?? []), row]);
    });
    const entries = [...map.entries()];
    // Letters in order; other groupings biggest first, "Unknown" always last.
    if (groupBy === 'letter') return entries.sort(([a], [b]) => a.localeCompare(b));
    return entries.sort(([a, left], [b, right]) =>
      (a === 'Unknown' ? 1 : 0) - (b === 'Unknown' ? 1 : 0) || right.length - left.length || a.localeCompare(b));
  }, [filtered, groupBy]);

  const tableRows = useMemo(() => {
    const factor = sort.desc ? -1 : 1;
    return [...filtered].sort((a, b) => {
      const left = sortValue(a, sort.key);
      const right = sortValue(b, sort.key);
      if (left === null) return 1;            // brokers without a number / rank always last
      if (right === null) return -1;
      return (typeof left === 'string' ? left.localeCompare(String(right)) : left - Number(right)) * factor;
    });
  }, [filtered, sort]);

  // Text-like columns start ascending, amounts descending.
  const toggleSort = (key: SortKey) => setSort((current) => (
    current.key === key ? { key, desc: !current.desc } : { key, desc: !TEXT_KEYS.has(key) }
  ));

  const stats = useMemo(() => ({
    suspended: results.filter((row) => !row.is_active).length,
    selfClearing: results.filter((row) => /self clearing/i.test(row.membership_type)).length,
    clearing: results.filter((row) => row.membership_type && !/self clearing/i.test(row.membership_type)).length,
    offices: results.reduce((total, row) => total + row.branches.length, 0),
    outside: results.reduce((total, row) => total + row.branches.filter((b) => !/kathmandu|lalitpur|bhaktapur/i.test(b.name)).length, 0),
  }), [results]);

  const range = data?.start_date && data.end_date ? `?start_date=${data.start_date}&end_date=${data.end_date}` : '';
  const windowLabel = data?.start_date && data.end_date
    ? `${formatTradeDate(data.start_date)} – ${formatTradeDate(data.end_date)}`
    : 'no floorsheet collected';
  const filtersActive = Boolean(search) || show !== 'all';

  return (
    <div className="space-y-5">
      <PageHeader title="Broker List" subtitle="Every NEPSE broker with its website, TMS login and offices" />

      {error && (
        <div className="card flex items-center justify-center gap-2 py-10 text-sm text-down">
          <AlertTriangle size={14} /> Could not load the broker list.
          <button onClick={() => setTick((t) => t + 1)} className="underline">Retry</button>
        </div>
      )}
      {!error && loading && !data && (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }, (_, i) => <div key={i} className="skeleton h-56 rounded-md" />)}
        </div>
      )}

      {data && !error && (
        <>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatCard label="Brokers" value={formatCount(data.summary.brokers)}
              hint={<>{formatCount(data.summary.active_brokers)} active{stats.suspended > 0 && <span className="text-down"> · {stats.suspended} suspended</span>}</>} />
            <StatCard label="Clearing members" value={formatCount(stats.clearing)} hint={`+ ${stats.selfClearing} self clearing`} />
            <StatCard label="Offices" value={formatCount(stats.offices)} hint={`${stats.outside} outside the valley`} />
            <StatCard label="Traded in period" value={formatCount(data.summary.trading_brokers)} hint={windowLabel} />
          </div>

          {/* Sticky toolbar: view, search, filters and (A–Z) letter jumps stay reachable while scrolling.
              -top-6 cancels <main>'s p-6 so it docks flush with the top edge instead of 24px below it. */}
          <div className="card sticky -top-6 z-20 space-y-3 !p-3 shadow-lg shadow-black/30">
            <div className="flex flex-wrap items-center gap-2">
              <div className="flex rounded-lg border border-bg-border p-0.5" role="tablist" aria-label="Broker list view">
                {([['directory', 'Directory', LayoutGrid], ['activity', 'Activity', Table2]] as const).map(([key, label, Icon]) => (
                  <button key={key} type="button" role="tab" aria-selected={view === key}
                    onClick={() => update({ view: key === 'directory' ? null : key })}
                    className={clsx('inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold transition-colors',
                      view === key ? 'bg-accent text-white' : 'text-text-muted hover:text-text-primary')}>
                    <Icon size={13} /> {label}
                  </button>
                ))}
              </div>

              <label className="relative min-w-[200px] flex-1">
                <span className="sr-only">Search brokers</span>
                <Search size={14} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-text-muted" />
                <input
                  type="search"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search name, number, city or website"
                  className={`${selectClass} w-full !py-2 pl-8 pr-8`}
                />
                {search && (
                  <button type="button" onClick={() => setSearch('')} aria-label="Clear search"
                    className="absolute right-2 top-1/2 -translate-y-1/2 rounded p-0.5 text-text-muted hover:text-text-primary">
                    <X size={13} />
                  </button>
                )}
              </label>

              {view === 'directory' && (
                <label className="flex items-center gap-2 text-xs text-text-muted">
                  Group
                  <select className={`${selectClass} !py-2`} value={groupBy} onChange={(e) => setGroupBy(e.target.value as GroupBy)}>
                    {(Object.keys(GROUP_LABELS) as GroupBy[]).map((key) => <option key={key} value={key}>{GROUP_LABELS[key]}</option>)}
                  </select>
                </label>
              )}
              <label className="flex items-center gap-2 text-xs text-text-muted" title="Window for turnover and ranks">
                Period
                <select className={`${selectClass} !py-2`} value={data.days} disabled={loading} onChange={(e) => update({ days: e.target.value })}>
                  {data.day_choices.map((choice) => <option key={choice} value={choice}>Last {choice} days</option>)}
                </select>
              </label>
            </div>

            <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
              <div className="flex flex-wrap gap-1" role="group" aria-label="Show brokers">
                {(Object.keys(SHOW_LABELS) as Show[]).map((key) => (
                  <button key={key} type="button" onClick={() => setShow(key)} aria-pressed={show === key}
                    className={clsx('rounded-full border px-3 py-1 text-[11px] font-medium transition-colors',
                      show === key ? 'border-accent/60 bg-accent/15 text-accent-light' : 'border-bg-border text-text-muted hover:text-text-primary')}>
                    {SHOW_LABELS[key]}
                  </button>
                ))}
              </div>
              <p className="ml-auto text-[11px] text-text-muted">
                <span className="font-semibold text-text-secondary">{filtered.length}</span> of {results.length} brokers
                {filtersActive && (
                  <button type="button" onClick={() => { setSearch(''); setShow('all'); }} className="ml-2 text-accent-light hover:underline">
                    Clear filters
                  </button>
                )}
              </p>
            </div>

            {view === 'directory' && groupBy === 'letter' && groups.length > 1 && (
              <nav aria-label="Jump to letter" className="flex flex-wrap gap-1 border-t border-bg-border pt-2.5">
                {groups.map(([name, rows]) => (
                  <a key={name} href={`#brokers-${name}`} title={`${rows.length} broker${rows.length > 1 ? 's' : ''}`}
                    className="flex h-7 min-w-7 items-center justify-center rounded-md px-1.5 font-mono text-xs font-semibold text-text-secondary transition-colors hover:bg-accent/15 hover:text-accent-light">
                    {name}
                  </a>
                ))}
              </nav>
            )}
          </div>

          <div className={clsx('space-y-6 transition-opacity', loading && 'pointer-events-none opacity-60')}>
            {filtered.length === 0 ? (
              <div className="card flex flex-col items-center gap-2 py-14 text-center text-sm text-text-muted">
                <Search size={20} />
                {results.length ? 'No brokers match these filters.' : 'The broker directory is empty: run `manage.py sync_broker_directory`.'}
                {filtersActive && (
                  <button type="button" onClick={() => { setSearch(''); setShow('all'); }} className="text-xs text-accent-light hover:underline">
                    Clear filters
                  </button>
                )}
              </div>
            ) : view === 'directory' ? (
              groups.map(([name, rows]) => (
                <section key={name} id={`brokers-${name}`} className="scroll-mt-44 space-y-3" aria-label={name}>
                  {groupBy !== 'none' && (
                    <div className="flex items-center gap-3">
                      <h2 className={clsx('font-semibold text-text-primary', groupBy === 'letter'
                        ? 'flex h-8 min-w-8 items-center justify-center rounded-lg bg-accent/15 px-2 font-mono text-base text-accent-light'
                        : 'text-sm')}>
                        {name}
                      </h2>
                      <span className="text-xs text-text-muted">{rows.length} broker{rows.length > 1 ? 's' : ''}</span>
                      <span className="h-px flex-1 bg-bg-border" aria-hidden="true" />
                    </div>
                  )}
                  <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
                    {rows.map((row) => <BrokerDirectoryCard key={row.broker_code} row={row} range={range} />)}
                  </div>
                </section>
              ))
            ) : (
              <section className="card !p-0">
                <ActivityTable rows={tableRows} range={range} sort={sort} onSort={toggleSort} />
                <p className="border-t border-bg-border px-4 py-3 text-[11px] text-text-muted">
                  Turnover = buy amount + sell amount across your tracked companies over {windowLabel}. Click a broker for the Broker Explorer detail.
                </p>
              </section>
            )}

            <p className="text-center text-[11px] text-text-muted">
              Directory synced <span className="font-mono">{formatTradeTime(data.directory_synced_at) ?? 'never'}</span>
              {' '}from NEPSE (broker details) and ShareHub (websites, offices) · <span className="font-mono">manage.py sync_broker_directory</span>
            </p>
          </div>
        </>
      )}
    </div>
  );
}
