import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ExternalLink } from 'lucide-react';
import PageHeader from '../components/common/PageHeader';
import EmptyState from '../components/common/EmptyState';
import CompanyLogo from '../components/companies/CompanyLogo';
import BrokerAccumulationPanel from '../components/brokers/accumulation/BrokerAccumulationPanel';
import { getCompanies } from '../api/companies';
import type { Company } from '../types/company';

// Broker accumulation / distribution for any stock the user can see.  The stock is kept in
// ?symbol= so the view can be bookmarked; the same panel also sits on the stock page.

export default function BrokerDistributionPage() {
  const [params, setParams] = useSearchParams();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    getCompanies({ status: 'active' })
      .then((data) => setCompanies([...data.results].sort((a, b) => a.symbol.localeCompare(b.symbol))))
      .catch(() => setError('Unable to load companies.'))
      .finally(() => setLoading(false));
  }, []);

  const requested = params.get('symbol')?.toUpperCase() ?? '';
  const company = companies.find((item) => item.symbol === requested) ?? companies[0];
  const select = (symbol: string) => setParams({ symbol }, { replace: true });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Broker Accumulation & Distribution"
        subtitle="Which brokers are net buying or net selling a stock over a range, from collected floorsheet trades."
        actions={company && (
          <Link to={`/companies/${company.symbol}`} className="btn-ghost flex items-center gap-2 text-xs">
            <ExternalLink size={14} />Open {company.symbol}
          </Link>
        )}
      />

      {loading ? (
        <p className="text-sm text-text-secondary">Loading companies…</p>
      ) : error ? (
        <p className="text-sm text-down">{error}</p>
      ) : !company ? (
        <EmptyState title="No companies" description="You don't have access to any active company yet." />
      ) : (
        <>
          <div className="card flex flex-wrap items-center gap-4 py-3">
            <CompanyLogo symbol={company.symbol} name={company.name} logoUrl={company.logo_url} size="md" />
            <div className="min-w-0">
              <p className="font-semibold text-text-primary">{company.symbol}</p>
              <p className="truncate text-xs text-text-muted">{company.name} · {company.sector}</p>
            </div>
            <label className="ml-auto flex items-center gap-2 text-xs text-text-secondary">
              Stock
              <select
                value={company.symbol}
                onChange={(event) => select(event.target.value)}
                className="input w-56 py-1.5 text-sm"
                aria-label="Stock"
              >
                {companies.map((item) => (
                  <option key={item.id} value={item.symbol}>{item.symbol} — {item.name}</option>
                ))}
              </select>
            </label>
          </div>

          <BrokerAccumulationPanel key={company.symbol} symbol={company.symbol} />
        </>
      )}
    </div>
  );
}
