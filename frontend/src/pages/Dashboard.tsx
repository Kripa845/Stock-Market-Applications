import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { analysisApi, type BrokerActivity, type BrokerAnalysisResponse } from '../api/analysis';
import BrokerBadge from '../components/brokers/BrokerBadge';
import { formatCount, formatTradeDate } from '../components/market/format';
import RoleDashboard from '../components/dashboard/RoleDashboard';
import Section from '../components/common/Section';

/**
 * Single unified dashboard for all roles.
 * RoleDashboard reads the user's actual permissions from AuthContext and
 * renders only the widgets the user is permitted to see.
 */

interface BrokerTile {
  label: string;
  row: BrokerActivity | undefined;
  value: (row: BrokerActivity) => string;
  tone: string;
}

function BrokerHighlight({ label, row, value, tone }: BrokerTile) {
  return (
    <div className="card flex h-full flex-col gap-3">
      <p className="text-xs font-medium uppercase tracking-wide text-text-secondary">{label}</p>
      {row ? (
        <>
          <Link to={`/broker-analysis/${encodeURIComponent(row.broker)}`} className="min-w-0 text-sm hover:opacity-80">
            <BrokerBadge brokerCode={row.broker_code || row.broker} name={row.broker_name || row.name}
              shortName={row.short_name} logoUrl={row.logo_url} />
          </Link>
          <p className={`font-mono text-lg font-bold ${tone}`}>{value(row)}</p>
        </>
      ) : (
        <p className="text-sm text-text-muted">—</p>
      )}
    </div>
  );
}

function BrokerSection() {
  const [data, setData] = useState<BrokerAnalysisResponse | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    analysisApi.getBrokerAnalysis({ page: 1 }).then(setData).catch(() => setError(true));
  }, []);

  const dates = data?.sampled_dates ?? [];
  const range = dates.length
    ? `${dates.length} floorsheet sessions · ${formatTradeDate(dates[dates.length - 1])} – ${formatTradeDate(dates[0])}`
    : 'Floorsheet sessions';
  const tiles: BrokerTile[] = data ? [
    { label: 'Most active buyer', row: data.most_active_buyers[0], value: (r) => `${formatCount(r.buy_quantity)} shares bought`, tone: 'text-up' },
    { label: 'Most active seller', row: data.most_active_sellers[0], value: (r) => `${formatCount(r.sell_quantity)} shares sold`, tone: 'text-down' },
    { label: 'Top net buyer', row: data.top_net_buyers[0], value: (r) => `+${formatCount(r.net_quantity)} net`, tone: 'text-up' },
    { label: 'Top net seller', row: data.top_net_sellers[0], value: (r) => `${formatCount(r.net_quantity)} net`, tone: 'text-down' },
  ] : [];

  return (
    <Section
      title="Broker activity"
      subtitle={`${range} · tracked companies`}
      action={<Link to="/broker-analysis" className="text-xs text-accent-light hover:underline">View broker analysis →</Link>}
    >
      {error ? (
        <p className="text-xs text-text-muted">Broker activity is temporarily unavailable.</p>
      ) : !data ? (
        <p className="text-xs text-text-muted">Loading broker activity…</p>
      ) : data.summary.sampled_trading_days === 0 ? (
        <p className="text-xs text-text-muted">No floorsheet data has been collected yet.</p>
      ) : (
        <div className="grid grid-cols-1 items-stretch gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {tiles.map((tile) => <BrokerHighlight key={tile.label} {...tile} />)}
        </div>
      )}
    </Section>
  );
}

export default function Dashboard() {
  const { hasPermission } = useAuth();
  return (
    <div className="space-y-8">
      <RoleDashboard />
      {hasPermission('view_analysis') && <BrokerSection />}
    </div>
  );
}
