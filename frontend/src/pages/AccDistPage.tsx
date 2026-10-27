import { useState } from 'react';
import { CircleHelp } from 'lucide-react';
import PageHeader from '../components/common/PageHeader';
import AccDistPanel from '../components/brokers/acc-dist/AccDistPanel';
import type { AccDistPeriod } from '../api/accDist';
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
        For each stock and broker, net quantity = shares bought − shares sold over the period.
        <b className="text-text-primary"> Accumulation</b> lists the largest net buyers,
        <b className="text-text-primary"> Distribution</b> the largest net sellers. Tot Amt is the net traded value,
        Avg Rate the average price, and Float Qnty % the net quantity as a share of the stock's free float.
        Rows are ranked by absolute Tot Amt.
      </span>
    </span>
  );
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
        subtitle="Stocks being accumulated or distributed by brokers."
        actions={<HelpTip />}
      />

      <div className="card grid gap-8 xl:grid-cols-2 xl:gap-6">
        <AccDistPanel side="accumulation" rows={data?.accumulation} {...shared} />
        <AccDistPanel side="distribution" rows={data?.distribution} {...shared} />
      </div>
    </div>
  );
}
