import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AlertTriangle, ArrowLeft, Info } from 'lucide-react';
import clsx from 'clsx';
import PageHeader from '../components/common/PageHeader';
import CompanyLogo from '../components/companies/CompanyLogo';
import { changeTone, formatCount, formatNprCompact, formatPct, formatPrice, formatTradeDate } from '../components/market/format';
import {
  PageSizeSelect, Pager, PeriodChips, ResetButton, SectorSelect, TopListTabs, useTopListParams,
} from '../components/market/TopListControls';
import { marketApi, type ActivityMetric, type TopActivityResponse, type TopActivityRow } from '../api/market';

// Market Overview -> Top Turnover / Volume / Transactions (/market/turnover, /volume, /transactions)
// for the TRACKED companies: each metric summed over the period's sessions, official closes only
// (NEPSE's live feed has no turnover, volume or trade counts).  Ranking is done by the backend.

const METRICS: Record<ActivityMetric, { title: string; column: string; subtitle: string; chip: string; format: (n: number) => string }> = {
  turnover: {
    title: 'Top Turnover', column: 'Turnover (Rs)', chip: 'bg-amber-400/10 text-amber-400',
    subtitle: 'Tracked companies with the most money traded', format: (n) => formatNprCompact(n),
  },
  volume: {
    title: 'Top Volume', column: 'Volume (shares)', chip: 'bg-sky-400/10 text-sky-400',
    subtitle: 'Tracked companies with the most shares traded', format: (n) => formatCount(n),
  },
  transactions: {
    title: 'Top Transactions', column: 'Transactions', chip: 'bg-violet-400/10 text-violet-400',
    subtitle: 'Tracked companies with the most trades', format: (n) => formatCount(n),
  },
};

const toneText = { up: 'text-up', down: 'text-down', flat: 'text-text-muted' };

function ActivityRow({ row, rank, metric, multiSession }: { row: TopActivityRow; rank: number; metric: ActivityMetric; multiSession: boolean }) {
  const navigate = useNavigate();
  const spec = METRICS[metric];
  return (
    <tr onClick={() => navigate(`/companies/${row.symbol}`)}
      className="cursor-pointer border-b border-bg-border last:border-0 hover:bg-blue-500/10">
      <td className="py-2.5 pl-4 pr-2 text-text-muted">{rank}</td>
      <td className="py-2.5 pr-2">
        <span className="flex min-w-0 items-center gap-2.5">
          <CompanyLogo symbol={row.symbol} name={row.name} logoUrl={row.logo_url} size="sm" />
          <span className="min-w-0">
            <span className="block font-semibold text-text-primary">{row.symbol}</span>
            <span className="block max-w-[220px] truncate text-[11px] text-text-muted" title={row.name}>{row.name}</span>
          </span>
        </span>
      </td>
      <td className="px-2 text-right font-mono text-text-primary">{row.ltp == null ? '—' : formatPrice(row.ltp)}</td>
      <td className={`px-2 text-right font-mono ${toneText[changeTone(row.change_pct)]}`}>{formatPct(row.change_pct)}</td>
      <td className="px-2 text-right font-mono font-semibold text-text-primary"
        title={row.complete ? undefined : 'Some sessions have no trade count yet, so this total is incomplete'}>
        {spec.format(row.value)}{!row.complete && <span className="text-amber-400">*</span>}
      </td>
      {multiSession && <td className="px-2 text-right font-mono text-text-secondary">{row.sessions_traded}</td>}
      <td className="py-2.5 pl-2 pr-4 text-center text-text-secondary">{row.sector}</td>
    </tr>
  );
}

export default function TopActivityPage({ metric }: { metric: ActivityMetric }) {
  const filters = useTopListParams();
  const { params, period, sector, page, pageSize, update } = filters;

  const [data, setData] = useState<TopActivityResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(false);
    marketApi.topActivity({ metric, period, sector, page, page_size: pageSize })
      .then((response) => { if (!cancelled) setData(response); })
      .catch(() => { if (!cancelled) setError(true); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [metric, period, sector, page, pageSize, retry]);

  const spec = METRICS[metric];
  const rows = data?.rows ?? [];
  const multiSession = period !== 'today';
  const incomplete = rows.some((r) => !r.complete);

  return (
    <div className="space-y-4">
      <PageHeader
        title={spec.title}
        subtitle={spec.subtitle}
        actions={(
          <Link to="/market" className="btn-ghost flex items-center gap-1.5 px-2.5 py-1.5 text-xs">
            <ArrowLeft size={13} /> Market Overview
          </Link>
        )}
      />
      <TopListTabs />

      <div className="card space-y-3 !p-0">
        <div className="flex flex-wrap items-center justify-between gap-3 px-4 pt-4">
          <h2 className={`rounded-md px-3 py-1.5 text-sm font-semibold ${spec.chip}`}>{spec.title}</h2>
          <div className="flex flex-wrap items-center gap-3">
            <SectorSelect value={sector} sectors={data?.sectors ?? []} onChange={(v) => update({ sector: v })} />
            <PageSizeSelect value={pageSize} onChange={filters.setPageSize} />
            <ResetButton disabled={!params.toString()} onClick={filters.reset} />
          </div>
        </div>

        <PeriodChips value={period} onChange={filters.setPeriod} />

        {data?.as_of && (
          <p className="flex flex-wrap items-center gap-x-2 gap-y-1 px-4 text-[11px] text-text-muted">
            <span className="font-semibold text-text-secondary">Official close</span>
            <span>
              · {multiSession && data.first_session
                ? `sum of sessions ${formatTradeDate(data.first_session)} – ${formatTradeDate(data.as_of)}`
                : `session ${formatTradeDate(data.as_of)}`}
            </span>
            <span>· Ch % over the same period</span>
            {data.market_open && <span>· today&apos;s numbers appear after the 18:00 price crawl</span>}
          </p>
        )}
        {(data?.warning || (metric === 'transactions' && incomplete)) && (
          <p className="mx-4 flex items-start gap-1.5 rounded-md border border-yellow-400/30 bg-yellow-400/10 px-3 py-2 text-xs text-yellow-400">
            <Info size={13} className="mt-px shrink-0" />
            <span>
              {data?.warning}{data?.warning && incomplete ? ' ' : ''}
              {incomplete && 'Totals marked * are incomplete: trade counts are only collected for recent sessions.'}
            </span>
          </p>
        )}

        {error ? (
          <div className="flex items-center justify-center gap-2 py-12 text-sm text-down">
            <AlertTriangle size={14} /> Could not load the {spec.title.toLowerCase()}.
            <button onClick={() => setRetry((t) => t + 1)} className="underline">Retry</button>
          </div>
        ) : !data && loading ? (
          <p className="py-12 text-center text-sm text-text-muted">Loading {spec.title.toLowerCase()}…</p>
        ) : (
          <div className={clsx('overflow-x-auto transition-opacity', loading && 'opacity-60')}>
            <table className="w-full min-w-[760px] text-xs">
              <thead>
                <tr className="border-y border-bg-border text-[11px] font-semibold uppercase tracking-wide text-text-secondary">
                  <th className="py-2.5 pl-4 pr-2 text-left font-semibold">#</th>
                  <th className="pr-2 text-left font-semibold">Symbol</th>
                  <th className="px-2 text-right font-semibold">LTP</th>
                  <th className="px-2 text-right font-semibold">Ch %</th>
                  <th className="px-2 text-right font-semibold">{spec.column}</th>
                  {multiSession && <th className="px-2 text-right font-semibold">Sessions</th>}
                  <th className="pl-2 pr-4 text-center font-semibold">Sector</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row, i) => (
                  <ActivityRow key={row.symbol} row={row} rank={(page - 1) * pageSize + i + 1} metric={metric} multiSession={multiSession} />
                ))}
                {!loading && rows.length === 0 && (
                  <tr>
                    <td colSpan={multiSession ? 7 : 6} className="px-4 py-12 text-center text-sm text-text-muted">
                      {data?.reason ?? `No trades for this period${sector ? ` in ${sector}` : ''}.`}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        <Pager page={page} pages={data?.pages ?? 1} pageSize={pageSize} total={data?.total ?? 0}
          onPage={(p) => update({ page: p > 1 ? p : null })} />
      </div>
    </div>
  );
}
