import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import PageHeader from '../../components/common/PageHeader';
import EmptyState from '../../components/common/EmptyState';
import { getCompanies } from '../../api/companies';
import { stocksApi } from '../../api/stocks';
import { useLiveRefresh } from '../../hooks/useLiveRefresh';
import type { Company, DailyPrice, FloorsheetTransaction } from '../../types';

interface WatchlistItem {
  company: Company;
  prices: DailyPrice[];
  floorsheet: FloorsheetTransaction[];
  floorDate: string | null;
}

interface FloorsheetFilters {
  company: string;
  date: string;
  buyer_broker: string;
  seller_broker: string;
}

export default function WatchlistPage() {
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [floorRows, setFloorRows] = useState<FloorsheetTransaction[]>([]);
  const [floorCount, setFloorCount] = useState(0);
  const [floorLoading, setFloorLoading] = useState(false);
  const [floorFilters, setFloorFilters] = useState<FloorsheetFilters>({ company: '', date: '', buyer_broker: '', seller_broker: '' });

  const loadWatchlist = useCallback(async () => {
    setLoading(true);
    try {
      const response = await getCompanies({ tracked_only: true });
      const trackedCompanies = response.results;
      const loaded = await Promise.all(trackedCompanies.map(async (company) => {
        const priceData = await stocksApi.getPrices(company.id, '30d');
        const floorData = await stocksApi.getFloorsheet(company.id);
        return {
          company,
          prices: priceData.prices,
          floorsheet: floorData.transactions,
          floorDate: floorData.date,
        };
      }));
      setItems(loaded);
      setError('');
    } catch {
      setError('Unable to load the tracked companies and market data.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadWatchlist(); }, [loadWatchlist]);
  useLiveRefresh(loadWatchlist, 15000);

  const searchFloorsheet = useCallback(async (filters = floorFilters) => {
    setFloorLoading(true);
    try {
      const response = await stocksApi.searchFloorsheet({
        company: filters.company ? Number(filters.company) : undefined,
        date: filters.date || undefined,
        buyer_broker: filters.buyer_broker || undefined,
        seller_broker: filters.seller_broker || undefined,
      });
      setFloorRows(response.results);
      setFloorCount(response.count);
    } catch {
      setError('Unable to load floorsheet search results.');
    } finally {
      setFloorLoading(false);
    }
  }, [floorFilters]);

  useEffect(() => { searchFloorsheet(); }, [searchFloorsheet]);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Live Trading"
        subtitle="Latest trading values for every tracked company."
        actions={<button onClick={loadWatchlist} className="btn-ghost flex items-center gap-2" disabled={loading}><RefreshCw size={14} className={loading ? 'animate-spin' : ''} />Refresh</button>}
      />
      {error && <div className="flex items-center gap-2 text-sm text-down"><AlertTriangle size={14} />{error}<button onClick={loadWatchlist} className="underline">Retry</button></div>}
      {loading && items.length === 0 && <p className="text-text-secondary">Loading watchlist...</p>}
      {!loading && !error && items.length === 0 && <EmptyState title="No tracked companies" description="Mark companies as tracked to populate the watchlist." />}
      {items.length > 0 && <div className="card overflow-x-auto">
        <table className="w-full min-w-[1050px] text-sm">
          <thead><tr className="border-b border-bg-border text-text-secondary">
            <th className="text-left py-3 font-medium">Company</th>
            <th className="text-left py-3 font-medium">Date</th>
            <th className="text-right py-3 font-medium">Open</th>
            <th className="text-right py-3 font-medium">High</th>
            <th className="text-right py-3 font-medium">Low</th>
            <th className="text-right py-3 font-medium">Close</th>
            <th className="text-right py-3 font-medium">Volume</th>
            <th className="text-right py-3 font-medium">Turnover</th>
            <th className="text-right py-3 font-medium">Floorsheet</th>
          </tr></thead>
          <tbody>{items.map(({ company, prices, floorsheet, floorDate }) => {
            const latest = prices[prices.length - 1];
            return <tr key={company.id} className="table-row">
              <td className="py-3"><p className="font-mono font-semibold text-accent-light">{company.symbol}</p><p className="text-xs text-text-muted">{company.name}</p></td>
              <td className="py-3 text-text-secondary">{latest?.date || 'No data'}</td>
              <td className="py-3 text-right font-mono">{latest ? Number(latest.open).toFixed(2) : '—'}</td>
              <td className="py-3 text-right font-mono text-up">{latest ? Number(latest.high).toFixed(2) : '—'}</td>
              <td className="py-3 text-right font-mono text-down">{latest ? Number(latest.low).toFixed(2) : '—'}</td>
              <td className="py-3 text-right font-mono font-semibold text-text-primary">{latest ? Number(latest.close).toFixed(2) : '—'}</td>
              <td className="py-3 text-right font-mono">{latest ? latest.volume.toLocaleString() : '—'}</td>
              <td className="py-3 text-right font-mono">{latest ? Number(latest.turnover).toLocaleString() : '—'}</td>
              <td className="py-3 text-right text-xs text-text-secondary">{floorsheet.length ? `${floorsheet.length} on ${floorDate}` : 'Not collected'}</td>
            </tr>;
          })}</tbody>
        </table>
      </div>}
      <section className="space-y-4">
        <div><h2 className="text-lg font-semibold text-text-primary">Floorsheet</h2><p className="text-sm text-text-secondary">Search transactions for tracked companies by date and broker.</p></div>
        <div className="card grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          <select value={floorFilters.company} onChange={event => setFloorFilters(current => ({ ...current, company: event.target.value }))} className="rounded-lg border border-bg-border bg-bg-card px-3 py-2 text-sm text-text-primary"><option value="">All tracked companies</option>{items.map(({ company }) => <option key={company.id} value={company.id}>{company.symbol} - {company.name}</option>)}</select>
          <input type="date" value={floorFilters.date} onChange={event => setFloorFilters(current => ({ ...current, date: event.target.value }))} className="rounded-lg border border-bg-border bg-bg-card px-3 py-2 text-sm text-text-primary" />
          <input value={floorFilters.buyer_broker} onChange={event => setFloorFilters(current => ({ ...current, buyer_broker: event.target.value }))} placeholder="Buyer broker" className="rounded-lg border border-bg-border bg-bg-card px-3 py-2 text-sm text-text-primary" />
          <input value={floorFilters.seller_broker} onChange={event => setFloorFilters(current => ({ ...current, seller_broker: event.target.value }))} placeholder="Seller broker" className="rounded-lg border border-bg-border bg-bg-card px-3 py-2 text-sm text-text-primary" />
          <button onClick={() => searchFloorsheet()} className="btn-primary flex items-center justify-center gap-2" disabled={floorLoading}><RefreshCw size={14} className={floorLoading ? 'animate-spin' : ''} />Search</button>
        </div>
        <div className="card overflow-x-auto"><div className="mb-4 flex items-center justify-between"><h3 className="text-sm font-semibold text-text-primary">Transaction results</h3><span className="text-xs text-text-muted">{floorCount} transactions</span></div><table className="w-full min-w-[850px] text-sm"><thead><tr className="border-b border-bg-border text-text-secondary"><th className="text-left py-3 font-medium">Company</th><th className="text-left py-3 font-medium">Date</th><th className="text-left py-3 font-medium">Transaction</th><th className="text-left py-3 font-medium">Buyer broker</th><th className="text-left py-3 font-medium">Seller broker</th><th className="text-right py-3 font-medium">Quantity</th><th className="text-right py-3 font-medium">Rate</th><th className="text-right py-3 font-medium">Amount</th></tr></thead><tbody>{floorRows.map(row => { const company = items.find(item => item.company.id === row.company)?.company; return <tr key={row.id} className="table-row"><td className="py-3 font-mono text-accent-light">{company?.symbol || `#${row.company}`}</td><td className="py-3 text-text-secondary">{row.date}</td><td className="py-3 text-text-muted">{row.transaction_id || '—'}</td><td className="py-3 text-text-secondary">{row.buyer_broker}</td><td className="py-3 text-text-secondary">{row.seller_broker}</td><td className="py-3 text-right font-mono">{row.quantity.toLocaleString()}</td><td className="py-3 text-right font-mono">{Number(row.rate).toFixed(2)}</td><td className="py-3 text-right font-mono">{row.amount ? Number(row.amount).toLocaleString() : '—'}</td></tr>; })}</tbody></table>{!floorLoading && floorRows.length === 0 && <p className="py-8 text-center text-sm text-text-muted">No floorsheet transactions match these filters.</p>}</div>
      </section>
    </div>
  );
}
