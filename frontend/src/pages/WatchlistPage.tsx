import { useCallback, useEffect, useState } from 'react';
import { RefreshCw, AlertTriangle } from 'lucide-react';
import PageHeader from '../components/common/PageHeader';
import BrokerBadge from '../components/brokers/BrokerBadge';
import CompanyLogo from '../components/companies/CompanyLogo';
import EmptyState from '../components/common/EmptyState';
import { dashboardApi } from '../api/dashboard';
import { stocksApi } from '../api/stocks';
import { useAuth } from '../contexts/AuthContext';
import type { Company } from '../types/company';
import type { FloorsheetTransaction } from '../types';

interface FloorsheetFilters {
  company: string;
  date: string;
  buyer_broker: string;
  seller_broker: string;
}

export default function WatchlistPage() {
  const { hasPermission } = useAuth();
  const canViewMarketData = hasPermission('view_market_data');

  const [items, setItems] = useState<{ company: Company; floorsheet: FloorsheetTransaction[]; floorDate: string | null }[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [floorRows, setFloorRows] = useState<FloorsheetTransaction[]>([]);
  const [floorCount, setFloorCount] = useState(0);
  const [floorLoading, setFloorLoading] = useState(false);
  const [floorFilters, setFloorFilters] = useState<FloorsheetFilters>({ company: '', date: '', buyer_broker: '', seller_broker: '' });

  const loadWatchlist = useCallback(async () => {
    setLoading(true);
    try {
      const response = await dashboardApi.viewer();
      const tracked = response.companies ?? [];
      setError('');
      if (canViewMarketData) {
        const loaded = await Promise.all(tracked.map(async (company) => {
          const floorData = await stocksApi.getFloorsheet(company.id);
          return {
            company,
            floorsheet: floorData.transactions,
            floorDate: floorData.date,
          };
        }));
        setItems(loaded);
      } else {
        setItems(tracked.map((company) => ({ company, floorsheet: [], floorDate: null })));
      }
    } catch {
      setError('Unable to load the watchlist.');
    } finally {
      setLoading(false);
    }
  }, [canViewMarketData]);

  useEffect(() => { loadWatchlist(); }, [loadWatchlist]);

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
            <th className="text-right py-3 font-medium">Close</th>
            <th className="text-right py-3 font-medium">High 24h</th>
            <th className="text-right py-3 font-medium">Low 24h</th>
            <th className="text-right py-3 font-medium">Volume 24h</th>
            <th className="text-right py-3 font-medium">Turnover 24h</th>
            <th className="text-right py-3 font-medium">Floorsheet</th>
          </tr></thead>
          <tbody>{items.map(({ company, floorsheet, floorDate }) => {
            return <tr key={company.id} className="table-row">
              <td className="py-3"><div className="flex items-center gap-2"><CompanyLogo symbol={company.symbol} name={company.name} logoUrl={company.logo_url} size="sm" /><span><span className="block font-mono font-semibold text-accent-light">{company.symbol}</span><span className="block text-xs text-text-muted">{company.name}</span></span></div></td>
              <td className="py-3 text-right font-mono font-semibold text-text-primary">{company.latest_price ? Number(company.latest_price).toFixed(2) : 'â€”'}</td>
              <td className="py-3 text-right font-mono text-up">{company.high_24h ? Number(company.high_24h).toFixed(2) : 'â€”'}</td>
              <td className="py-3 text-right font-mono text-down">{company.low_24h ? Number(company.low_24h).toFixed(2) : 'â€”'}</td>
              <td className="py-3 text-right font-mono">{company.volume_24h ? company.volume_24h.toLocaleString() : 'â€”'}</td>
              <td className="py-3 text-right font-mono">{company.turnover_24h ? Number(company.turnover_24h).toLocaleString() : 'â€”'}</td>
              <td className="py-3 text-right text-xs text-text-secondary">{floorsheet.length ? `${floorsheet.length} on ${floorDate}` : 'Not collected'}</td>
            </tr>;
          })}</tbody>
        </table>
      </div>}
      <section className="space-y-4">
        <div><h2 className="text-lg font-semibold text-text-primary">Floorsheet</h2><p className="text-sm text-text-secondary">Search transactions for tracked companies by date and broker.</p></div>
        {canViewMarketData ? (
          <>
            <div className="card grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
              <select value={floorFilters.company} onChange={event => setFloorFilters(current => ({ ...current, company: event.target.value }))} className="rounded-lg border border-bg-border bg-bg-card px-3 py-2 text-sm text-text-primary"><option value="">All tracked companies</option>{items.map(({ company }) => <option key={company.id} value={company.id}>{company.symbol} - {company.name}</option>)}</select>
              <input type="date" value={floorFilters.date} onChange={event => setFloorFilters(current => ({ ...current, date: event.target.value }))} className="rounded-lg border border-bg-border bg-bg-card px-3 py-2 text-sm text-text-primary" />
              <input value={floorFilters.buyer_broker} onChange={event => setFloorFilters(current => ({ ...current, buyer_broker: event.target.value }))} placeholder="Buyer broker" className="rounded-lg border border-bg-border bg-bg-card px-3 py-2 text-sm text-text-primary" />
              <input value={floorFilters.seller_broker} onChange={event => setFloorFilters(current => ({ ...current, seller_broker: event.target.value }))} placeholder="Seller broker" className="rounded-lg border border-bg-border bg-bg-card px-3 py-2 text-sm text-text-primary" />
              <button onClick={() => searchFloorsheet()} className="btn-primary flex items-center justify-center gap-2" disabled={floorLoading}><RefreshCw size={14} className={floorLoading ? 'animate-spin' : ''} />Search</button>
            </div>
            <div className="card overflow-x-auto"><div className="mb-4 flex items-center justify-between"><h3 className="text-sm font-semibold text-text-primary">Transaction results</h3><span className="text-xs text-text-muted">{floorCount} transactions</span></div><table className="w-full min-w-[850px] text-sm"><thead><tr className="border-b border-bg-border text-text-secondary"><th className="text-left py-3 font-medium">Company</th><th className="text-left py-3 font-medium">Date</th><th className="text-left py-3 font-medium">Transaction</th><th className="text-left py-3 font-medium">Buyer broker</th><th className="text-left py-3 font-medium">Seller broker</th><th className="text-right py-3 font-medium">Quantity</th><th className="text-right py-3 font-medium">Rate</th><th className="text-right py-3 font-medium">Amount</th></tr></thead><tbody>{floorRows.map(row => { const company = items.find(item => item.company.id === row.company)?.company; return <tr key={row.id} className="table-row"><td className="py-3"><span className="flex items-center gap-2 font-mono text-accent-light"><CompanyLogo symbol={company?.symbol || String(row.company)} name={company?.name} logoUrl={company?.logo_url} size="sm" />{company?.symbol || `#${row.company}`}</span></td><td className="py-3 text-text-secondary">{row.date}</td><td className="py-3 text-text-muted">{row.transaction_id || 'â€”'}</td><td className="py-3"><BrokerBadge brokerCode={row.buyer_broker} name={row.buyer_broker_name} shortName={row.buyer_broker_short_name} logoUrl={row.buyer_broker_logo_url} /></td><td className="py-3"><BrokerBadge brokerCode={row.seller_broker} name={row.seller_broker_name} shortName={row.seller_broker_short_name} logoUrl={row.seller_broker_logo_url} /></td><td className="py-3 text-right font-mono">{row.quantity.toLocaleString()}</td><td className="py-3 text-right font-mono">{Number(row.rate).toFixed(2)}</td><td className="py-3 text-right font-mono">{row.amount ? Number(row.amount).toLocaleString() : 'â€”'}</td></tr>; })}</tbody></table>{!floorLoading && floorRows.length === 0 && <p className="py-8 text-center text-sm text-text-muted">No floorsheet transactions match these filters.</p>}</div>
          </>
        ) : (
          <div className="card py-8 text-center">
            <p className="text-sm text-text-muted">You do not have permission to view market data.</p>
          </div>
        )}
      </section>
    </div>
  );
}
