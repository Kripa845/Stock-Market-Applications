import { useEffect, useState } from 'react';
import { TrendingUp, TrendingDown } from 'lucide-react';
import { getCompanies } from '../../api/companies';
import type { Company } from '../../types/company';
import { useLiveRefresh } from '../../hooks/useLiveRefresh';

export default function MarketTicker() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const load = () => getCompanies({ status: 'active' })
    .then(data => setCompanies(data.results));
  useEffect(() => { load(); }, []);
  useLiveRefresh(load);
  const items = [...companies, ...companies];
  const dates = companies.map(company => company.latest_price_date).filter((date): date is string => Boolean(date)).sort();
  const latestDate = dates[dates.length - 1];

  return (
    <div className="h-9 bg-bg-secondary border-b border-bg-border flex items-center overflow-hidden select-none shrink-0">
      {/* Status pill */}
      <div className="flex items-center gap-1.5 px-4 border-r border-bg-border shrink-0 h-full">
        <span className="text-xs text-text-secondary font-medium whitespace-nowrap">Latest close{latestDate ? ` · ${latestDate}` : ''}</span>
      </div>

      {/* Scrolling ticker */}
      <div className="flex-1 overflow-hidden relative">
        <div className="ticker-scroll">
          {items.map((company, i) => {
            const pos = company.price_change_percent >= 0;
            return (
              <span key={i} className="inline-flex items-center gap-2 px-5 text-xs">
                <span className="font-semibold text-text-primary font-mono">{company.symbol}</span>
                <span className="text-text-secondary font-mono">Rs.{company.latest_price.toFixed(2)}</span>
                <span className={`flex items-center gap-0.5 font-medium ${pos ? 'text-up' : 'text-down'}`}>
                  {pos ? <TrendingUp size={10} /> : <TrendingDown size={10} />}
                  {pos ? '+' : ''}{company.price_change_percent.toFixed(2)}%
                </span>
                <span className="text-bg-border">|</span>
              </span>
            );
          })}
        </div>
      </div>

    </div>
  );
}
