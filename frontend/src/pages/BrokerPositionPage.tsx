// Broker Acc / Dist chart: one broker's buying and selling across up to 8 tracked stocks over
// 1D ... 1Y, as lines on one time axis (accumulation / distribution, cumulative or per interval),
// as shares of the broker's buying or selling (pie), or for one stock against its price.
// All state lives in the URL (?symbols=&broker=&range=&tab=&filter=&self=&focus=) so views can be linked.
import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useQuery, keepPreviousData } from '@tanstack/react-query';
import { AlertTriangle, Info, RefreshCw, TrendingUp, X } from 'lucide-react';

import PageHeader from '../components/common/PageHeader';
import BrokerBadge from '../components/brokers/BrokerBadge';
import Picker, { type PickerOption } from '../components/brokers/position/Picker';
import AccDistLineChart, { type LineSeries } from '../components/brokers/position/AccDistLineChart';
import AccDistPie from '../components/brokers/position/AccDistPie';
import PositionPriceView from '../components/brokers/position/PositionPriceView';
import { seriesColor, signed, toneText } from '../components/brokers/position/format';
import { formatCount, formatTradeDate } from '../components/market/format';
import {
  MAX_ACTIVITY_STOCKS, POSITION_RANGES, brokerActivityApi, type BrokerActivity, type PositionRange,
} from '../api/brokerPosition';
import { analysisApi } from '../api/analysis';
import { getCompanies } from '../api/companies';
import type { Company } from '../types/company';

const TABS = [
  { key: 'acc', label: 'Accumulation' },
  { key: 'dist', label: 'Distribution' },
  { key: 'accpie', label: 'Accumulation Pie Chart' },
  { key: 'distpie', label: 'Distribution Pie Chart' },
  { key: 'price', label: 'Position vs Price' },
] as const;
type Tab = (typeof TABS)[number]['key'];

const FILTERS = [
  { key: 'cum', label: 'Cumulative Quantity' },
  { key: 'cumnet', label: 'Cumulative Net Quantity' },
  { key: 'buy', label: 'Buy Quantity' },
  { key: 'sell', label: 'Sell Quantity' },
  { key: 'net', label: 'Net Quantity' },
] as const;
type Filter = (typeof FILTERS)[number]['key'];

const DEFAULT_STOCKS = 5;
const timeFormat = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Kathmandu', hour: '2-digit', minute: '2-digit', hour12: false });
const dateOnly = (iso: string) => new Date(`${iso.slice(0, 10)}T00:00:00`);

// The companies API pages by 20; the picker needs all of them.
async function allActiveCompanies(): Promise<Company[]> {
  const all: Company[] = [];
  for (let page = 1; ; page += 1) {
    const data = await getCompanies({ status: 'active', page });
    all.push(...data.results);
    if (!data.next) return all;
  }
}

function running(values: number[]) {
  let total = 0;
  return values.map((v) => (total += v));
}

/** The line values for one stock under the chosen tab and filter. */
function lineValues(bought: number[], sold: number[], tab: Tab, filter: Filter) {
  if (filter === 'buy') return bought;
  if (filter === 'sell') return sold;
  const net = bought.map((b, i) => b - sold[i]);
  if (filter === 'net') return net;
  if (filter === 'cumnet') return running(net);
  return running(tab === 'dist' ? sold : bought);
}

function filterTitle(tab: Tab, filter: Filter) {
  if (filter === 'cum') return tab === 'dist' ? 'Cumulative quantity sold' : 'Cumulative quantity bought';
  if (filter === 'cumnet') return 'Cumulative net quantity (bought − sold)';
  if (filter === 'buy') return 'Quantity bought per interval';
  if (filter === 'sell') return 'Quantity sold per interval';
  return 'Net quantity per interval (bought − sold)';
}

/** Keep each stock's colour while it stays selected; a new stock takes the lowest free slot. */
function useColourSlots(symbols: string[]) {
  const slots = useRef<Record<string, number>>({});
  return useMemo(() => {
    const next: Record<string, number> = {};
    symbols.forEach((s) => { if (slots.current[s] != null) next[s] = slots.current[s]; });
    symbols.forEach((s) => {
      if (next[s] != null) return;
      const used = new Set(Object.values(next));
      let slot = 0;
      while (used.has(slot)) slot += 1;
      next[s] = slot;
    });
    slots.current = next;
    return next;
  }, [symbols]);
}

export default function BrokerPositionPage() {
  const [params, setParams] = useSearchParams();
  const symbolsParam = params.get('symbols') ?? params.get('symbol') ?? '';
  const symbols = useMemo(
    () => symbolsParam.split(',').map((s) => s.trim().toUpperCase()).filter(Boolean).slice(0, MAX_ACTIVITY_STOCKS),
    [symbolsParam],
  );
  const broker = params.get('broker') ?? '';
  const range = (POSITION_RANGES as readonly string[]).includes(params.get('range') ?? '') ? params.get('range') as PositionRange : '1M';
  const tab = (TABS.some((t) => t.key === params.get('tab')) ? params.get('tab') : 'acc') as Tab;
  const filter = (FILTERS.some((f) => f.key === params.get('filter')) ? params.get('filter') : 'cum') as Filter;
  const excludeSelf = params.get('self') === '0';
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [highlight, setHighlight] = useState<string | null>(null);
  const slots = useColourSlots(symbols);

  const update = (patch: Record<string, string>) => {
    const next = new URLSearchParams(params);
    next.delete('symbol');
    // An empty `symbols=` is kept: it means "none selected", not "use the defaults".
    Object.entries(patch).forEach(([key, value]) => (value || key === 'symbols' ? next.set(key, value) : next.delete(key)));
    setParams(next, { replace: true });
  };

  /** Change the selection; hidden / highlighted stocks that stay selected keep their state. */
  const select = (values: string[]) => {
    setHidden((h) => new Set([...h].filter((s) => values.includes(s))));
    setHighlight((current) => (current && values.includes(current) ? current : null));
    update({ symbols: values.join(',') });
  };

  const companies = useQuery({ queryKey: ['companies', 'all-active'], queryFn: allActiveCompanies, staleTime: 10 * 60_000 });
  const brokers = useQuery({ queryKey: ['analysis', 'broker-list'], queryFn: () => analysisApi.getBrokerList(), staleTime: 10 * 60_000 });

  // Open on the first few tracked companies only when the URL has no selection at all.
  useEffect(() => {
    if (!params.has('symbols') && !params.has('symbol') && companies.data?.length) {
      update({ symbols: companies.data.slice(0, DEFAULT_STOCKS).map((c) => c.symbol).join(',') });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [symbolsParam, companies.data]);

  const activity = useQuery({
    queryKey: ['broker-activity', symbols.join(','), broker, range, excludeSelf],
    queryFn: () => brokerActivityApi.get({ symbols, broker, range, excludeSelf }),
    enabled: symbols.length > 0,
    placeholderData: keepPreviousData,
  });
  const data: BrokerActivity | undefined = activity.data;
  const activeBroker = broker || data?.broker || '';
  const meta = data?.broker_metadata[activeBroker];
  const detail = (activity.error as { response?: { data?: { detail?: string } } } | null)?.response?.data?.detail;

  const shortLabel = (i: number) => {
    const t = data?.times[i];
    if (!t) return '';
    if (data?.mode === 'intraday') return timeFormat.format(new Date(t));
    const d = dateOnly(t);
    return d.toLocaleDateString('en-GB', range === '6M' || range === '1Y'
      ? { day: 'numeric', month: 'short', year: '2-digit' } : { day: 'numeric', month: 'short' });
  };
  const longLabel = (i: number) => {
    const t = data?.times[i];
    if (!t) return '';
    return data?.mode === 'intraday' ? `${formatTradeDate(t.slice(0, 10))} · ${timeFormat.format(new Date(t))}` : formatTradeDate(t);
  };

  const lines: LineSeries[] = useMemo(() => (data?.series ?? []).map((s) => {
    const values = lineValues(s.bought, s.sold, tab, filter);
    const cumulative = filter === 'cum' || filter === 'cumnet';
    return { symbol: s.symbol, slot: slots[s.symbol] ?? 0, values, total: cumulative ? values[values.length - 1] ?? 0 : values.reduce((a, v) => a + v, 0) };
  }), [data, tab, filter, slots]);

  const toggle = (symbol: string) => {
    setHidden((h) => {
      const next = new Set(h);
      if (next.has(symbol)) next.delete(symbol); else next.add(symbol);
      return next;
    });
    // A hidden line can't stay highlighted.
    setHighlight((current) => (current === symbol ? null : current));
  };

  // The dropdown mirrors the chips: colour dot while selected, muted + "hidden" while hidden.
  const stockOptions: PickerOption[] = (companies.data ?? []).map((c) => {
    const isHidden = hidden.has(c.symbol);
    return {
      value: c.symbol,
      label: c.symbol,
      hint: isHidden ? `hidden · ${c.name}` : c.name,
      color: slots[c.symbol] != null ? (isHidden ? 'var(--trading-muted)' : seriesColor(slots[c.symbol])) : undefined,
      muted: isHidden,
    };
  });
  const brokerOptions: PickerOption[] = useMemo(() => {
    const directory = (brokers.data?.results ?? []).map((b) => ({ value: b.broker_code, label: b.broker_code, hint: b.name }));
    const known = new Set(directory.map((o) => o.value));
    const extra = (data?.top_brokers ?? []).filter((b) => !known.has(b.broker)).map((b) => ({ value: b.broker, label: b.broker }));
    return [...directory, ...extra].sort((a, b) => a.value.localeCompare(b.value, undefined, { numeric: true }));
  }, [brokers.data, data?.top_brokers]);

  const isPie = tab === 'accpie' || tab === 'distpie';
  const focus = symbols.includes(params.get('focus') ?? '') ? params.get('focus') as string : symbols[0] ?? '';

  return (
    <div className="space-y-5">
      <PageHeader
        title="Broker Acc / Dist Chart"
        subtitle="One broker's accumulation (buying) and distribution (selling) in your tracked stocks over time."
        actions={
          <button type="button" onClick={() => activity.refetch()} className="btn-ghost flex items-center gap-2 text-xs">
            <RefreshCw size={13} className={activity.isFetching ? 'animate-spin' : ''} /> Refresh
          </button>
        }
      />

      {/* Timeframe and self-trade switch */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div role="group" aria-label="Timeframe" className="flex gap-0.5 rounded-lg border border-bg-border bg-bg-card p-1">
          {POSITION_RANGES.map((r) => (
            <button key={r} type="button" aria-pressed={r === range} onClick={() => update({ range: r })}
              className={`rounded-md px-3.5 py-1.5 font-mono text-xs font-semibold tracking-wider transition ${
                r === range ? 'bg-accent text-white' : 'text-text-secondary hover:text-text-primary'
              }`}>
              {r}
            </button>
          ))}
        </div>
        <label className="flex items-center gap-2 text-xs text-text-secondary">
          <input type="checkbox" checked={excludeSelf} onChange={(e) => update({ self: e.target.checked ? '0' : '' })} />
          Exclude self-trades (same broker both sides)
        </label>
      </div>

      {/* Chart type tabs */}
      <div role="tablist" aria-label="Chart type" className="flex gap-1 overflow-x-auto border-b border-bg-border">
        {TABS.map((t) => (
          <button key={t.key} type="button" role="tab" aria-selected={tab === t.key} onClick={() => update({ tab: t.key === 'acc' ? '' : t.key })}
            className={`-mb-px whitespace-nowrap border-b-2 px-3.5 py-2.5 text-sm transition ${
              tab === t.key ? 'border-accent font-semibold text-text-primary' : 'border-transparent text-text-secondary hover:text-text-primary'
            }`}>
            {t.label}
          </button>
        ))}
      </div>

      {/* Filters */}
      <div className="grid grid-cols-1 gap-3 md:grid-cols-[2.2fr_1fr_1fr]">
        <Picker label="Add stock(s)" placeholder="Select tracked stocks" heading={`Tracked companies · up to ${MAX_ACTIVITY_STOCKS}`}
          options={stockOptions} selected={symbols} multi max={MAX_ACTIVITY_STOCKS} onChange={select}
          onHover={(value) => setHighlight(value && symbols.includes(value) && !hidden.has(value) ? value : null)} />
        <Picker label="Select broker" placeholder={data?.broker ? `Most active: ${data.broker}` : 'Select broker'}
          options={brokerOptions} selected={broker ? [broker] : []} onChange={(values) => update({ broker: values[0] ?? '' })} />
        <Picker label="Filter type" placeholder="Select filter" clearable={false} disabled={isPie || tab === 'price'}
          options={FILTERS.map((f) => ({ value: f.key, label: f.label }))} selected={[filter]}
          onChange={(values) => update({ filter: values[0] === 'cum' ? '' : values[0] ?? '' })} />
      </div>

      {/* Selected stocks: click to show / hide, x to remove */}
      <div className="flex min-h-8 flex-wrap items-center gap-2">
        {symbols.length === 0 && <span className="text-sm text-text-muted">No stock selected. Open Add stock(s) to pick from your tracked list.</span>}
        {symbols.map((s) => {
          const on = !hidden.has(s);
          const colour = seriesColor(slots[s] ?? 0);
          const lit = on && highlight === s;
          return (
            <span key={s} role="button" tabIndex={0} aria-pressed={on} onClick={() => toggle(s)}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(s); } }}
              onMouseEnter={() => on && setHighlight(s)} onMouseLeave={() => setHighlight(null)}
              onFocus={() => on && setHighlight(s)} onBlur={() => setHighlight(null)}
              title={on ? `Hide ${s}` : `Show ${s}`}
              className={`inline-flex cursor-pointer select-none items-center gap-1.5 rounded-full border py-1 pl-2.5 pr-1 text-xs font-semibold transition ${
                !on ? 'border-bg-border text-text-muted opacity-60'
                  : lit ? 'border-accent bg-accent/15 text-text-primary'
                    : 'border-bg-border bg-bg-card text-text-primary hover:border-accent/60'
              }`}>
              <span className="h-2.5 w-2.5 rounded-full" style={{ background: on ? colour : 'var(--trading-muted)' }} />
              <span className={on ? '' : 'line-through'}>{s}</span>
              <button type="button" aria-label={`Remove ${s}`} onClick={(e) => { e.stopPropagation(); select(symbols.filter((x) => x !== s)); }}
                className="rounded-full p-0.5 text-text-muted hover:bg-bg-elevated hover:text-text-primary">
                <X size={12} />
              </button>
            </span>
          );
        })}
        {symbols.length > 0 && (
          <span className="text-[11px] text-text-muted">
            Hover to highlight · click to show / hide
            {hidden.size > 0 && (
              <> · <button type="button" onClick={() => setHidden(new Set())} className="font-semibold text-accent hover:underline">Show all</button></>
            )}
          </span>
        )}
      </div>

      {data && data.top_brokers.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="text-text-muted">Most active across these stocks ({data.range}):</span>
          {data.top_brokers.map((b) => (
            <button key={b.broker} type="button" onClick={() => update({ broker: b.broker })}
              title={`${data.broker_metadata[b.broker]?.name ?? `Broker ${b.broker}`} · bought ${formatCount(b.bought)}, sold ${formatCount(b.sold)}`}
              className={`rounded-full border px-2.5 py-1 font-mono transition ${
                b.broker === activeBroker ? 'border-accent bg-accent/15 text-text-primary' : 'border-bg-border text-text-secondary hover:border-accent/60'
              }`}>
              #{b.broker} <span className={toneText(b.net)}>{signed(b.net)}</span>
            </button>
          ))}
        </div>
      )}

      <section className="card !p-5">
        {symbols.length === 0 ? (
          <p className="py-16 text-center text-sm text-text-muted">Pick one or more tracked stocks to draw the chart.</p>
        ) : activity.error ? (
          <div role="alert" className="flex items-center gap-2 rounded-md border border-down/30 bg-down/10 px-4 py-3 text-sm text-down">
            <AlertTriangle size={15} /> {detail ?? 'Unable to load broker activity.'}
          </div>
        ) : !data ? (
          <div className="skeleton h-[480px] rounded-xl" />
        ) : !data.sessions ? (
          <p className="py-16 text-center text-sm text-text-muted">No floorsheet sessions are stored for these stocks.</p>
        ) : (
          <div className={`space-y-4 transition-opacity ${activity.isFetching ? 'opacity-60' : ''}`}>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <BrokerBadge brokerCode={activeBroker} name={meta?.name} shortName={meta?.short_name} logoUrl={meta?.logo_url} />
                <h2 className="text-base font-semibold text-text-primary">
                  {tab === 'price' ? `Position vs price · ${focus}`
                    : isPie ? (tab === 'accpie' ? 'Accumulation share' : 'Distribution share') : filterTitle(tab, filter)}
                </h2>
              </div>
              <span className="text-xs text-text-muted">
                {data.sessions} session{data.sessions === 1 ? '' : 's'} · {formatTradeDate(data.start_date)}
                {data.end_date !== data.start_date && ` – ${formatTradeDate(data.end_date)}`}
                {data.mode === 'intraday' && ` · ${data.bucket_minutes}-minute buckets`}
              </span>
            </div>

            {tab === 'price' ? (
              <>
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <span className="text-text-muted">Stock:</span>
                  {symbols.map((s) => (
                    <button key={s} type="button" onClick={() => update({ focus: s })}
                      className={`rounded-full border px-2.5 py-1 font-semibold transition ${
                        s === focus ? 'border-accent bg-accent/15 text-text-primary' : 'border-bg-border text-text-secondary hover:border-accent/60'
                      }`}>
                      {s}
                    </button>
                  ))}
                </div>
                <PositionPriceView symbol={focus} broker={activeBroker} range={range} excludeSelf={excludeSelf} />
              </>
            ) : isPie ? (
              <AccDistPie side={tab === 'accpie' ? 'bought' : 'sold'}
                slices={data.series.filter((s) => !hidden.has(s.symbol)).map((s) => ({
                  symbol: s.symbol, slot: slots[s.symbol] ?? 0, value: tab === 'accpie' ? s.totals.bought : s.totals.sold,
                }))} />
            ) : (
              <AccDistLineChart times={data.times} shortLabel={shortLabel} longLabel={longLabel} series={lines}
                hidden={hidden} highlight={highlight} yTitle={FILTERS.find((f) => f.key === filter)?.label ?? ''} onToggle={toggle}
                onHighlight={setHighlight} />
            )}

            {data.warnings.map((w) => <p key={w} className="flex items-center gap-2 text-xs text-down"><AlertTriangle size={13} /> {w}</p>)}
          </div>
        )}
      </section>

      {data && tab !== 'price' && data.series.length > 0 && (
        <div className="overflow-x-auto rounded-md border border-bg-border">
          <table className="w-full text-xs">
            <thead className="bg-bg-elevated text-[11px] uppercase tracking-wide text-text-muted">
              <tr>
                {['Stock', 'Bought', 'Sold', 'Net', 'Avg buy', 'Avg sell', 'Trades'].map((h, i) => (
                  <th key={h} className={`px-3 py-2 font-medium ${i ? 'text-right' : 'text-left'}`}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.series.map((s) => (
                <tr key={s.symbol} className="table-row font-mono">
                  <td className="px-3 py-2 text-left font-sans">
                    <span className="inline-flex items-center gap-2 font-semibold text-text-primary">
                      <span className="h-2.5 w-2.5 rounded-full" style={{ background: seriesColor(slots[s.symbol] ?? 0) }} />{s.symbol}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-right text-text-secondary">{formatCount(s.totals.bought)}</td>
                  <td className="px-3 py-2 text-right text-text-secondary">{formatCount(s.totals.sold)}</td>
                  <td className={`px-3 py-2 text-right ${toneText(s.totals.net)}`}>{signed(s.totals.net)}</td>
                  <td className="px-3 py-2 text-right text-text-secondary">{s.totals.avg_buy_price?.toFixed(2) ?? '—'}</td>
                  <td className="px-3 py-2 text-right text-text-secondary">{s.totals.avg_sell_price?.toFixed(2) ?? '—'}</td>
                  <td className="px-3 py-2 text-right text-text-secondary">{formatCount(s.totals.trades)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="flex max-w-4xl items-start gap-2 text-xs text-text-muted">
        <Info size={13} className="mt-0.5 shrink-0" />
        <span>
          Accumulation = shares the broker bought, distribution = shares it sold, from the stored floorsheet of your tracked stocks.
          Cumulative lines start at 0 at the start of the range: they show buying or selling <em>within</em> the range, not holdings.
          1D / 2D use each trade's own time (1- / 5-minute buckets); 1W … 1Y are per session, counted back over stored sessions.
          Broker numbers are trading members: one broker's buying can be many clients. Up to {MAX_ACTIVITY_STOCKS} stocks at once so every line keeps a distinct colour.
          {' '}<Link to="/broker-acc-dist" className="inline-flex items-center gap-1 text-accent hover:underline"><TrendingUp size={12} /> Market-wide Acc/Dist</Link>
        </span>
      </p>
    </div>
  );
}
