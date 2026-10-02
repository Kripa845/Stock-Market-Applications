import { useEffect, useState } from 'react';
import { marketIntelligenceApi, type MarketBreadth } from '../../api/marketIntelligence';

function pct(value: number | string | null) {
  return value == null ? '—' : `${Number(value).toFixed(1)}%`;
}

export default function MarketBreadthWidget() {
  const [data, setData] = useState<MarketBreadth | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    marketIntelligenceApi.getBreadth().then(setData).catch(() => setError(true));
  }, []);

  return (
    <section className="card space-y-3 p-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-text-primary">Market breadth</h2>
          <p className="text-[11px] text-text-muted">Computed from tracked stocks · not investment advice</p>
        </div>
        {data && <span className="text-[11px] text-text-muted">Session {data.date}</span>}
      </div>
      {error && <p className="text-xs text-text-secondary">Breadth snapshots are unavailable. Run the market intelligence backfill.</p>}
      {!data && !error && <p className="text-xs text-text-secondary">Loading breadth…</p>}
      {data && (
        <>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            {([
              ['Advances', data.advances, 'text-up'], ['Declines', data.declines, 'text-down'],
              ['Above 50 DMA', `${pct(data.above_50_dma_pct)} (${data.valid_50_dma_count})`, 'text-text-primary'],
              ['Above 200 DMA', `${pct(data.above_200_dma_pct)} (${data.valid_200_dma_count})`, 'text-text-primary'],
            ] as [string, string | number, string][]).map(([label, value, color]) => (
              <div key={String(label)} className="rounded border border-bg-border bg-bg-elevated p-2">
                <p className="text-[10px] uppercase text-text-muted">{label}</p>
                <p className={`mt-1 font-mono text-sm ${color}`}>{value}</p>
              </div>
            ))}
          </div>
          <p className="text-[10px] text-text-muted">
            Tracked Basket (turnover-weighted): {data.proxy_index.level == null ? '—' : Number(data.proxy_index.level).toFixed(2)}
            {' · '}method {data.proxy_index.methodology_version}
            {' · '}excluded possible corporate actions: {data.corporate_action_excluded_count}
            {' · '}updated {new Date(data.computed_at).toLocaleString()}
          </p>
        </>
      )}
    </section>
  );
}
