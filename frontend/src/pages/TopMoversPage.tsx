import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AlertTriangle, ArrowDown, ArrowLeft, ArrowUp, Info, Radio } from 'lucide-react';
import clsx from 'clsx';
import PageHeader from '../components/common/PageHeader';
import CompanyLogo from '../components/companies/CompanyLogo';
import { formatPct, formatPrice, formatTradeDate } from '../components/market/format';
import {
  Filter, PageSizeSelect, Pager, PeriodChips, POLL_MS, ResetButton, SectorSelect, TopListTabs,
  formatTradeTime, selectClass, useTopListParams,
} from '../components/market/TopListControls';
import { marketApi, type TopMoversResponse, type TopMoversRow, type TopMoversSide } from '../api/market';

// Market Overview -> Top Gainers / Top Losers (/market/gainers, /market/losers) for the TRACKED
// companies.  Ranking is done by the backend (services/top_movers.py); this only formats.

const SIDES: Record<TopMoversSide, { title: string; tone: string; chip: string; Arrow: typeof ArrowUp }> = {
  gainers: { title: 'Top Gainers', tone: 'text-up', chip: 'bg-up/10 text-up', Arrow: ArrowUp },
  losers: { title: 'Top Losers', tone: 'text-down', chip: 'bg-down/10 text-down', Arrow: ArrowDown },
};

function signed(value: number) {
  const n = Number(value);
  return `${n > 0 ? '+' : ''}${n.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`;
}

function MoverRow({ row, side, fallbackDate }: { row: TopMoversRow; side: TopMoversSide; fallbackDate: string | null }) {
  const navigate = useNavigate();
  const { tone, chip, Arrow } = SIDES[side];
  return (
    <tr onClick={() => navigate(`/companies/${row.symbol}`)}
      className="cursor-pointer border-b border-bg-border last:border-0 hover:bg-blue-500/10">
      <td className="py-2.5 pl-4 pr-2">
        <span className="flex min-w-0 items-center gap-2.5">
          <CompanyLogo symbol={row.symbol} name={row.name} logoUrl={row.logo_url} size="sm" />
          <span className="min-w-0">
            <span className="block font-semibold text-text-primary">{row.symbol}</span>
            <span className="block max-w-[220px] truncate text-[11px] text-text-muted" title={row.name}>{row.name}</span>
          </span>
        </span>
      </td>
      <td className="px-2 text-right font-mono font-semibold text-text-primary">{formatPrice(row.ltp)}</td>
      <td className={`px-2 text-right font-mono ${tone}`}>{signed(row.change)}</td>
      <td className="px-2 text-center">
        <span className={`inline-flex min-w-[76px] items-center justify-center gap-1 rounded-md px-2 py-0.5 font-mono text-xs ${chip}`}
          title={row.adjusted ? 'Measured against the exchange-adjusted previous close (bonus / right shares)' : undefined}>
          <Arrow size={11} />{formatPct(row.change_pct)}{row.adjusted && <span className="text-amber-400">*</span>}
        </span>
      </td>
      <td className="px-2 text-center text-text-secondary">{row.sector}</td>
      <td className="whitespace-nowrap py-2.5 pl-2 pr-4 text-center font-mono text-text-secondary">
        {formatTradeTime(row.last_updated) ?? formatTradeDate(fallbackDate)}
      </td>
    </tr>
  );
}

export default function TopMoversPage({ side }: { side: TopMoversSide }) {
  const filters = useTopListParams();
  const { params, period, sector, page, pageSize, update } = filters;
  const adjusted = params.get('adjusted') !== 'false';

  const [data, setData] = useState<TopMoversResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [tick, setTick] = useState(0);          // bumped by the poller and Retry

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(false);
    marketApi.topMovers({ type: side, period, sector, adjusted, page, page_size: pageSize })
      .then((response) => { if (!cancelled) setData(response); })
      .catch(() => { if (!cancelled) setError(true); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [side, period, sector, adjusted, page, pageSize, tick]);

  // Refresh every minute while the market is open (the backend knows the trading days and holidays).
  const marketOpen = !!data?.market_open;
  useEffect(() => {
    if (!marketOpen) return;
    const timer = window.setInterval(() => setTick((t) => t + 1), POLL_MS);
    return () => window.clearInterval(timer);
  }, [marketOpen]);

  const spec = SIDES[side];
  const rows = data?.rows ?? [];

  return (
    <div className="space-y-4">
      <PageHeader
        title={spec.title}
        subtitle="Biggest price moves among the tracked companies"
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
            <Filter label="Adjusted Price">
              <select value={adjusted ? 'true' : 'false'} onChange={(e) => update({ adjusted: e.target.value === 'true' ? null : 'false' })}
                className={selectClass}>
                <option value="true">Yes</option>
                <option value="false">No</option>
              </select>
            </Filter>
            <PageSizeSelect value={pageSize} onChange={filters.setPageSize} />
            <ResetButton disabled={!params.toString()} onClick={filters.reset} />
          </div>
        </div>

        <PeriodChips value={period} onChange={filters.setPeriod} />

        {data?.as_of && (
          <p className="flex flex-wrap items-center gap-x-2 gap-y-1 px-4 text-[11px] text-text-muted">
            {data.live ? (
              <span className="inline-flex items-center gap-1 font-semibold text-up"><Radio size={11} /> Live · unofficial until the close</span>
            ) : (
              <span className="font-semibold text-text-secondary">Official close</span>
            )}
            <span>· session {formatTradeDate(data.as_of)}{data.base_date ? ` vs ${formatTradeDate(data.base_date)}` : ''}</span>
            {marketOpen && <span>· refreshes every minute</span>}
            <span>· <span className="text-amber-400">*</span> adjusted for bonus / right shares</span>
          </p>
        )}
        {data?.live && data.stale && (
          <p className="mx-4 flex items-center gap-1.5 rounded-md border border-yellow-400/30 bg-yellow-400/10 px-3 py-2 text-xs text-yellow-400">
            <Info size={13} /> The live feed has not updated for over 10 minutes; prices may be behind.
          </p>
        )}

        {error ? (
          <div className="flex items-center justify-center gap-2 py-12 text-sm text-down">
            <AlertTriangle size={14} /> Could not load the {spec.title.toLowerCase()}.
            <button onClick={() => setTick((t) => t + 1)} className="underline">Retry</button>
          </div>
        ) : !data && loading ? (
          <p className="py-12 text-center text-sm text-text-muted">Loading {spec.title.toLowerCase()}…</p>
        ) : (
          <div className={clsx('overflow-x-auto transition-opacity', loading && 'opacity-60')}>
            <table className="w-full min-w-[820px] text-xs">
              <thead>
                <tr className="border-y border-bg-border text-[11px] font-semibold uppercase tracking-wide text-text-secondary">
                  <th className="py-2.5 pl-4 pr-2 text-left font-semibold">Symbol</th>
                  <th className="px-2 text-right font-semibold">LTP</th>
                  <th className="px-2 text-right font-semibold">Ch</th>
                  <th className="px-2 text-center font-semibold">Ch %</th>
                  <th className="px-2 text-center font-semibold">Sector</th>
                  <th className="pl-2 pr-4 text-center font-semibold">Last Updated Date</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => <MoverRow key={row.symbol} row={row} side={side} fallbackDate={data?.as_of ?? null} />)}
                {!loading && rows.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-12 text-center text-sm text-text-muted">
                      {data?.reason ?? `No ${side} for this period${sector ? ` in ${sector}` : ''}.`}
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
