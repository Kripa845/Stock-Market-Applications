import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { marketIntelligenceApi, type RankedStock, type RankingMetric } from '../../api/marketIntelligence';

const TABS: { id: RankingMetric; label: string }[] = [
  { id: 'gainers', label: 'Gainers' }, { id: 'losers', label: 'Losers' },
  { id: 'volume', label: 'Top volume' }, { id: 'turnover', label: 'Top turnover' },
];

export default function MarketRankings() {
  const navigate = useNavigate();
  const [metric, setMetric] = useState<RankingMetric>('gainers');
  const [rows, setRows] = useState<RankedStock[]>([]);
  const [date, setDate] = useState<string | null>(null);
  const [updated, setUpdated] = useState<string | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    setError(false);
    marketIntelligenceApi.getRankings(metric)
      .then((response) => { setRows(response.results); setDate(response.date); setUpdated(response.computed_at); })
      .catch(() => setError(true));
  }, [metric]);

  return (
    <section className="card space-y-3 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-text-primary">Daily rankings</h2>
          <p className="text-[11px] text-text-muted">Latest close, not live · tracked stocks</p>
        </div>
        {date && <span className="text-[11px] text-text-muted">Session {date}{updated ? ` · updated ${new Date(updated).toLocaleString()}` : ''}</span>}
      </div>
      <div className="flex flex-wrap gap-1">
        {TABS.map((tab) => (
          <button key={tab.id} onClick={() => setMetric(tab.id)}
            className={`rounded px-2.5 py-1 text-xs ${metric === tab.id ? 'bg-accent text-white' : 'text-text-secondary hover:bg-bg-elevated'}`}>
            {tab.label}
          </button>
        ))}
      </div>
      {error && <p className="text-xs text-text-secondary">Rankings are unavailable.</p>}
      {!error && rows.length === 0 && <p className="text-xs text-text-secondary">No rows for this ranking.</p>}
      {rows.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[540px] text-xs">
            <thead className="border-b border-bg-border text-text-muted">
              <tr><th className="py-2 text-left">Symbol</th><th className="text-left">Sector</th><th className="text-right">Close</th><th className="text-right">Change</th><th className="text-right">Volume</th><th className="text-right">Turnover</th></tr>
            </thead>
            <tbody>{rows.map((row) => {
              const change = row.change_pct == null ? null : Number(row.change_pct);
              return <tr key={row.company_id} className="table-row cursor-pointer" onClick={() => navigate(`/companies/${row.symbol}`)}>
                <td className="py-2 font-semibold text-accent-light">{row.symbol}</td>
                <td className="text-text-secondary">{row.sector}</td>
                <td className="text-right font-mono">{Number(row.close).toFixed(2)}</td>
                <td className={`text-right font-mono ${change == null ? 'text-text-muted' : change >= 0 ? 'text-up' : 'text-down'}`}>{change == null ? '—' : `${change > 0 ? '+' : ''}${change.toFixed(2)}%`}{row.possible_corporate_action ? ' *' : ''}</td>
                <td className="text-right font-mono">{row.volume.toLocaleString()}</td>
                <td className="text-right font-mono">{Number(row.turnover).toLocaleString(undefined, { maximumFractionDigits: 0 })}</td>
              </tr>;
            })}</tbody>
          </table>
        </div>
      )}
      <p className="text-[10px] text-text-muted">* Possible corporate-action session; change excluded from return rankings.</p>
    </section>
  );
}
