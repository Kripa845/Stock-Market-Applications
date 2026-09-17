import { useCallback, useEffect, useState } from 'react';
import { Search, TrendingDown, TrendingUp } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import PageHeader from '../components/common/PageHeader';
import Badge from '../components/common/Badge';
import EmptyState from '../components/common/EmptyState';
import { getCompanies } from '../api/companies';
import type { Company } from '../types/company';
import { useLiveRefresh } from '../hooks/useLiveRefresh';

export default function MarketPage() {
  const navigate = useNavigate();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const loadCompanies = useCallback(() => {
    setLoading(true);
    getCompanies({ search: search || undefined, status: 'active' })
      .then((data) => setCompanies(data.results))
      .catch(() => setError('Unable to load companies.'))
      .finally(() => setLoading(false));
  }, [search]);

  useEffect(() => { loadCompanies(); }, [loadCompanies]);
  useLiveRefresh(loadCompanies);

  return (
    <div className="space-y-6">
      <PageHeader title="Market Overview" subtitle="Live company prices from the backend." />
      <div className="relative max-w-md">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-muted" />
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search companies"
          className="w-full bg-bg-card border border-bg-border rounded-lg pl-9 pr-3 py-2 text-sm text-text-primary"
        />
      </div>
      {error && (
        <div className="text-sm text-down">
          {error}{' '}
          <button onClick={loadCompanies} className="underline">Retry</button>
        </div>
      )}
      {loading && <p className="text-text-secondary">Loading companies...</p>}
      {!loading && !error && companies.length === 0 && (
        <EmptyState
          title="No companies found"
          description="The backend returned no active companies for this search."
        />
      )}
      {!loading && companies.length > 0 && (
        <div className="card overflow-x-auto">
          <table className="w-full min-w-[720px] text-sm">
            <thead>
              <tr className="border-b border-bg-border text-text-secondary">
                <th className="text-left py-3">Symbol</th>
                <th className="text-left py-3">Company</th>
                <th className="text-left py-3">Sector</th>
                <th className="text-right py-3">Price</th>
                <th className="text-right py-3">Change</th>
                <th className="text-right py-3">Volume</th>
                <th className="text-right py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {companies.map((company) => {
                const positive = company.price_change_percent >= 0;
                return (
                  <tr
                    key={company.id}
                    onClick={() => navigate(`/companies/${company.symbol}`)}
                    className="table-row cursor-pointer"
                  >
                    <td className="py-3 font-mono font-semibold text-accent-light">
                      {company.symbol}
                    </td>
                    <td className="py-3 text-text-primary">{company.name}</td>
                    <td className="py-3">
                      <Badge variant="gray">{company.sector}</Badge>
                    </td>
                    <td className="py-3 text-right font-mono">
                      Rs. {company.latest_price.toFixed(2)}
                    </td>
                    <td className={`py-3 text-right font-mono ${positive ? 'text-up' : 'text-down'}`}>
                      {positive ? <TrendingUp size={13} className="inline" /> : <TrendingDown size={13} className="inline" />}
                      {' '}{positive ? '+' : ''}{company.price_change_percent.toFixed(2)}%
                    </td>
                    <td className="py-3 text-right font-mono">
                      {company.volume_24h.toLocaleString()}
                    </td>
                    <td className="py-3 text-right">
                      <Badge variant={company.is_tracked ? 'green' : 'gray'}>
                        {company.is_tracked ? 'Tracked' : 'Untracked'}
                      </Badge>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
