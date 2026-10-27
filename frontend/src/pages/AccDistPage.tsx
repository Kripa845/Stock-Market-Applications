import { useState } from 'react';
import { CircleHelp } from 'lucide-react';
import PageHeader from '../components/common/PageHeader';
import AccDistPanel from '../components/brokers/acc-dist/AccDistPanel';
import type { AccDistPeriod, AccDistSnapshot } from '../api/accDist';
import { formatTradeDate } from '../components/market/format';
import { useAccDist, useWatchlistSymbols } from '../hooks/useAccDist';

// Market-wide accumulation / distribution: which brokers are net buying or selling which
// stocks.  The period is shared, so changing it in either panel reloads both tables;
// filters, watchlist and rank order are per panel.

function HelpTip() {
  return (
    <span className="group relative inline-flex">
      <button type="button" className="text-text-muted hover:text-text-primary" aria-label="How this is calculated">
        <CircleHelp size={16} />
      </button>
      <span
        role="tooltip"
        className="pointer-events-none absolute right-0 top-full z-20 mt-2 w-72 rounded-lg border border-bg-border bg-bg-elevated p-3 text-xs leading-relaxed text-text-secondary opacity-0 shadow-lg transition-opacity group-focus-within:opacity-100 group-hover:opacity-100"
      >
        From collected floorsheet trades, for each stock and broker: Tot Qnt = shares bought − shares sold,
        Tot Amt = value bought − value sold. <b className="text-text-primary">Accumulation</b> lists net buyers,
        <b className="text-text-primary"> Distribution</b> net sellers, ranked by absolute Tot Amt. Avg Rate is the
        broker's average buy (or sell) price. Float Qnty % is Tot Qnt as a share of public (free-float) shares;
        * marks stocks where only listed shares are known. Periods count trading sessions.
      </span>
    </span>
  );
}

/** "21 sessions · 17 Sep 2026 – 26 Oct 2026" */
function coverage(data: AccDistSnapshot | null) {
  if (!data) return 'Stocks being accumulated or distributed by brokers.';
  if (!data.sessions) return 'No floorsheet trades collected yet.';
  const range = data.start_date === data.end_date
    ? formatTradeDate(data.end_date)
    : `${formatTradeDate(data.start_date)} – ${formatTradeDate(data.end_date)}`;
  return `Stocks being accumulated or distributed by brokers · ${data.sessions} session${data.sessions === 1 ? '' : 's'} · ${range}`;
}

export default function AccDistPage() {
  const [period, setPeriod] = useState<AccDistPeriod>('1D');
  const { data, loading, error, reload } = useAccDist(period);
  const watchlist = useWatchlistSymbols();

  const shared = { period, onPeriodChange: setPeriod, loading, error, onRetry: reload, watchlist };

  return (
    <div className="space-y-6">
      <PageHeader
        title="Accumulation and Distribution"
        subtitle={coverage(data)}
        actions={<HelpTip />}
      />

      <div className="card grid gap-8 xl:grid-cols-2 xl:gap-6">
        <AccDistPanel side="accumulation" rows={data?.accumulation} {...shared} />
        <AccDistPanel side="distribution" rows={data?.distribution} {...shared} />
      </div>
    </div>
  );
}
