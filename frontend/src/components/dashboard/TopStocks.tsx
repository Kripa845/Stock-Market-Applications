// import { useEffect, useState } from 'react';
// import { useNavigate } from 'react-router-dom';
// import { TrendingUp, TrendingDown } from 'lucide-react';
// import Sparkline from '../common/Sparkline';
// import { getCompanies } from '../../api/companies';
// import type { Company } from '../../types/company';
// import { useLiveRefresh } from '../../hooks/useLiveRefresh';

// export default function TopStocks() {
//   const navigate = useNavigate();
//   const [companies, setCompanies] = useState<Company[]>([]);

//   const load = () => getCompanies({ status: 'active' })
//     .then(data => setCompanies(data.results.slice(0, 10)));

//   useEffect(() => { load(); }, []);
//   useLiveRefresh(load);

//   return (
//     <div className="card flex flex-col gap-3">
//       <div className="flex items-center justify-between">
//         <h3 className="text-sm font-semibold text-text-primary">Top Stocks</h3>
//         <button
//           onClick={() => navigate('/stocks')}
//           className="text-xs text-accent-light hover:text-accent transition-colors"
//         >
//           View all
//         </button>
//       </div>

//       <div className="overflow-x-auto">
//         <table className="w-full text-xs">
//           <thead>
//             <tr className="text-text-muted border-b border-bg-border">
//               <th className="text-left py-2 font-medium">Symbol</th>
//               <th className="text-left py-2 font-medium hidden sm:table-cell">Company</th>
//               <th className="text-right py-2 font-medium">Price</th>
//               <th className="text-right py-2 font-medium">Change</th>
//               <th className="text-right py-2 font-medium hidden md:table-cell">Volume</th>
//               <th className="text-right py-2 font-medium hidden lg:table-cell">7D Trend</th>
//             </tr>
//           </thead>
//           <tbody>
//             {companies.map((company) => {
//               const pos = company.price_change_percent >= 0;
//               return (
//                 <tr
//                   key={company.id}
//                   className="table-row cursor-pointer"
//                   onClick={() => navigate(`/stocks/${company.symbol.toLowerCase()}`)}
//                 >
//                   <td className="py-2.5">
//                     <span className="inline-flex items-center justify-center w-12 h-6 rounded bg-accent-glow border border-accent-dim text-accent-light font-bold font-mono text-[11px]">
//                       {company.symbol}
//                     </span>
//                   </td>
//                   <td className="py-2.5 text-text-secondary hidden sm:table-cell max-w-[120px] truncate pr-2">
//                     {company.name}
//                   </td>
//                   <td className="py-2.5 text-right font-mono text-text-primary font-medium">
//                     {company.latest_price.toFixed(2)}
//                   </td>
//                   <td className={`py-2.5 text-right font-medium ${pos ? 'text-up' : 'text-down'}`}>
//                     <span className="inline-flex items-center justify-end gap-1">
//                       {pos ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
//                       {pos ? '+' : ''}{company.price_change_percent.toFixed(2)}%
//                     </span>
//                   </td>
//                   <td className="py-2.5 text-right text-text-secondary hidden md:table-cell font-mono">
//                     {company.volume_24h >= 1_000_000
//                       ? `${(company.volume_24h / 1_000_000).toFixed(1)}M`
//                       : `${(company.volume_24h / 1_000).toFixed(0)}K`}
//                   </td>
//                   <td className="py-2.5 text-right hidden lg:table-cell">
//                     <div className="flex justify-end">
//                       <Sparkline data={company.sparkline} positive={pos} width={64} height={24} />
//                     </div>
//                   </td>
//                 </tr>
//               );
//             })}
//           </tbody>
//         </table>
//       </div>
//     </div>
//   );
// }
import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { TrendingUp, TrendingDown } from 'lucide-react';
import Sparkline from '../common/Sparkline';
import { getCompanies } from '../../api/companies';
import type { Company } from '../../types/company';
import { useLiveRefresh } from '../../hooks/useLiveRefresh';

export default function TopStocks() {
  const navigate = useNavigate();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const load = useCallback(async () => {
    try {
      const data = await getCompanies({ status: 'active' });
      setCompanies(data.results ? data.results.slice(0, 10) : []);
    } catch (error) {
      console.error('Failed to load top stocks:', error);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    let isMounted = true;
    
    getCompanies({ status: 'active' })
      .then((data) => {
        if (isMounted) {
          setCompanies(data.results ? data.results.slice(0, 10) : []);
          setIsLoading(false);
        }
      })
      .catch((err) => {
        if (isMounted) console.error('Failed to fetch companies:', err);
      });

    return () => {
      isMounted = false;
    };
  }, []);

  useLiveRefresh(load);

  // Helper function for clean currency/volume formatting
  const formatVolume = (vol: number) => {
    if (!vol) return '0';
    if (vol >= 1_000_000_000) return `${(vol / 1_000_000_000).toFixed(1)}B`;
    if (vol >= 1_000_000) return `${(vol / 1_000_000).toFixed(1)}M`;
    if (vol >= 1_000) return `${(vol / 1_000).toFixed(0)}K`;
    return vol.toString();
  };

  return (
    <div className="card flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text-primary">Top Stocks</h3>
        <button
          onClick={() => navigate('/stocks')}
          className="text-xs text-accent-light hover:text-accent transition-colors cursor-pointer"
        >
          View all
        </button>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-text-muted border-b border-bg-border">
              <th className="text-left py-2 font-medium">Symbol</th>
              <th className="text-left py-2 font-medium hidden sm:table-cell">Company</th>
              <th className="text-right py-2 font-medium">Price</th>
              <th className="text-right py-2 font-medium">Change</th>
              <th className="text-right py-2 font-medium hidden md:table-cell">Volume</th>
              <th className="text-right py-2 font-medium hidden lg:table-cell">7D Trend</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={6} className="py-6 text-center text-text-muted">
                  Loading top stocks...
                </td>
              </tr>
            ) : companies.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-6 text-center text-text-muted">
                  No active stocks available.
                </td>
              </tr>
            ) : (
              companies.map((company) => {
                const pos = (company.price_change_percent ?? 0) >= 0;
                
                return (
                  <tr
                    key={company.id}
                    className="table-row cursor-pointer hover:bg-bg-hover transition-colors"
                    onClick={() => navigate(`/stocks/${company.symbol.toLowerCase()}`)}
                  >
                    <td className="py-2.5">
                      <span className="inline-flex items-center justify-center w-12 h-6 rounded bg-accent-glow border border-accent-dim text-accent-light font-bold font-mono text-[11px]">
                        {company.symbol}
                      </span>
                    </td>
                    <td className="py-2.5 text-text-secondary hidden sm:table-cell max-w-[120px] truncate pr-2">
                      {company.name}
                    </td>
                    <td className="py-2.5 text-right font-mono text-text-primary font-medium">
                      {company.latest_price ? company.latest_price.toFixed(2) : '0.00'}
                    </td>
                    <td className={`py-2.5 text-right font-medium ${pos ? 'text-up' : 'text-down'}`}>
                      <span className="inline-flex items-center justify-end gap-1">
                        {pos ? <TrendingUp size={11} /> : <TrendingDown size={11} />}
                        {pos ? '+' : ''}{(company.price_change_percent ?? 0).toFixed(2)}%
                      </span>
                    </td>
                    <td className="py-2.5 text-right text-text-secondary hidden md:table-cell font-mono">
                      {formatVolume(company.volume_24h)}
                    </td>
                    <td className="py-2.5 text-right hidden lg:table-cell">
                      <div className="flex justify-end">
                        {company.sparkline && company.sparkline.length > 0 ? (
                          <Sparkline data={company.sparkline} positive={pos} width={64} height={24} />
                        ) : (
                          <span className="text-text-muted text-[10px]">N/A</span>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}