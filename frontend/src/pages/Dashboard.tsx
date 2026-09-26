import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { analysisApi, type BrokerAnalysisResponse } from '../api/analysis';
import RoleDashboard from '../components/dashboard/RoleDashboard';

/**
 * Single unified dashboard for all roles.
 * RoleDashboard reads the user's actual permissions from AuthContext and
 * renders only the widgets the user is permitted to see.
 */
export default function Dashboard() {
  const { hasPermission } = useAuth();
  const canViewBrokerActivity = hasPermission('view_analysis');
  const [data, setData] = useState<BrokerAnalysisResponse | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    if (!canViewBrokerActivity) return;
    analysisApi.getBrokerAnalysis({ page: 1 }).then(setData).catch(() => setError(true));
  }, [canViewBrokerActivity]);

  const buyer = data?.most_active_buyers[0];
  const seller = data?.most_active_sellers[0];
  const netBuyer = data?.top_net_buyers[0];
  const netSeller = data?.top_net_sellers[0];
  const activity = [
    ['Most Active Buyer', buyer ? `Broker #${buyer.broker} · ${buyer.buy_quantity.toLocaleString()} buy-side qty` : '—', 'text-up'],
    ['Most Active Seller', seller ? `Broker #${seller.broker} · ${seller.sell_quantity.toLocaleString()} sell-side qty` : '—', 'text-down'],
    ['Top Net Buyer', netBuyer ? `Broker #${netBuyer.broker} · +${netBuyer.net_quantity.toLocaleString()}` : '—', 'text-up'],
    ['Top Net Seller', netSeller ? `Broker #${netSeller.broker} · ${netSeller.net_quantity.toLocaleString()}` : '—', 'text-down'],
  ] as const;

  return <div className="space-y-5"><RoleDashboard />{canViewBrokerActivity && <section className="card">
    <div className="mb-3 flex flex-wrap items-center justify-between gap-2"><div><h2 className="text-sm font-semibold text-text-primary">Floorsheet / Broker Behavior</h2><p className="text-[11px] text-text-muted">Sampled trading sessions only</p></div><Link to="/broker-analysis" className="text-xs text-accent-light hover:underline">View All Broker Analysis →</Link></div>
    {error ? <p className="text-xs text-text-muted">Broker activity is temporarily unavailable.</p> : !data ? <p className="text-xs text-text-muted">Loading sampled broker activity…</p> : data.summary.sampled_trading_days === 0 ? <p className="text-xs text-text-muted">No floorsheet data has been collected yet.</p> : <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{activity.map(([label, value, color]) => <div key={label} className="rounded border border-bg-border p-3"><p className="text-[10px] uppercase tracking-widest text-text-muted">{label}</p><p className={`mt-1 text-xs font-mono ${color}`}>{value}</p></div>)}</div>}
  </section>}</div>;
}
