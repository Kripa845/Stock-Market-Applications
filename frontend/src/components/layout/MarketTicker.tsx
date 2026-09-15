import { useEffect, useState } from 'react';
import { TrendingUp, TrendingDown, Activity } from 'lucide-react';
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

  return (
    <div className="h-9 bg-bg-secondary border-b border-bg-border flex items-center overflow-hidden select-none shrink-0">
      {/* Status pill */}
      <div className="flex items-center gap-1.5 px-4 border-r border-bg-border shrink-0 h-full">
        <span className="w-1.5 h-1.5 rounded-full bg-up animate-pulse" />
        <span className="text-xs text-up font-medium whitespace-nowrap">Market Open</span>
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

      {/* NEPSE index pill */}
      <div className="flex items-center gap-2 px-4 border-l border-bg-border shrink-0 h-full">
        <Activity size={12} className="text-accent-light" />
        <span className="text-xs text-text-secondary">NEPSE</span>
        <span className="text-xs font-mono font-semibold text-text-primary">Live data</span>
      </div>
    </div>
  );
}
