import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { AlertTriangle, Search } from 'lucide-react';
import PageHeader from '../components/common/PageHeader';
import BrokerPodium from '../components/brokers/BrokerPodium';
import BrokerTurnoverTable from '../components/brokers/BrokerTurnoverTable';
import { formatCount, formatNprArab } from '../components/market/format';
import { analysisApi, type TopBrokerResponse } from '../api/analysis';

const dayLabel = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' });

function StatCard({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="card">
      <p className="text-[10px] uppercase tracking-widest text-text-muted">{label}</p>
      <p className="mt-1 font-mono text-xl font-bold tabular-nums text-text-primary">{value}</p>
      {hint && <p className="mt-0.5 text-[11px] text-text-muted">{hint}</p>}
    </div>
  );
}

export default function TopBrokerPage() {
  // Empty = let the API pick the latest complete trading day.
  // The day lives in the URL (?date=) so a broker's page can link back to the same day.
  const [searchParams, setSearchParams] = useSearchParams();
  const date = searchParams.get('date') ?? '';
  const setDate = (value: string) => setSearchParams(value ? { date: value } : {}, { replace: true });
  const [data, setData] = useState<TopBrokerResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [search, setSearch] = useState('');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError('');
    analysisApi.getTopBrokers(date || undefined)
      .then((d) => { if (!cancelled) setData(d); })
      .catch(() => { if (!cancelled) setError('Unable to load the broker ranking. Check your access and try again.'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [date]);

  const ranks = useMemo(() => new Map(data?.results.map((r, i) => [r.broker, i + 1])), [data]);
  const rows = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!data || !q) return data?.results ?? [];
    return data.results.filter((r) => `${r.name} ${r.short_name} ${r.broker_code}`.toLowerCase().includes(q));
  }, [data, search]);

  const dateSelect = data && data.available_dates.length > 0 && (
    <label className="flex items-center gap-2 text-xs text-text-muted">
      Trading day
      <select className="input" value={data.date ?? ''} onChange={(e) => setDate(e.target.value)} disabled={loading}>
        {data.available_dates.map((d) => (
          <option key={d.date} value={d.date}>
            {dayLabel(d.date)}{d.is_complete ? '' : ` · partial (${d.companies} co.)`}
          </option>
        ))}
      </select>
    </label>
  );

  return (
    <div className="space-y-5">
      <PageHeader
        title="Top Brokers"
        subtitle={data ? `Brokers ranked by turnover (buy + sell) · Tracked companies (${data.expected_companies})` : 'Brokers ranked by turnover (buy + sell)'}
        actions={(
          <>
            {dateSelect}
            <Link to="/broker-analysis" className="btn-ghost flex items-center gap-1.5 text-xs">
              <Search size={13} /> Broker Explorer (date range)
            </Link>
          </>
        )}
      />

      {error && <div className="card text-sm text-down">{error}</div>}
      {loading && !data && <div className="card text-sm text-text-muted">Loading broker ranking…</div>}

      {data && !data.date && (
        <div className="card py-10 text-center text-sm text-text-muted">No floorsheet data has been collected yet.</div>
      )}

      {data?.date && (
        <div className={loading ? 'pointer-events-none space-y-5 opacity-60 transition-opacity' : 'space-y-5'}>
          {!data.is_complete && (
            <div className="card flex items-start gap-2 border-amber-500/40 text-xs text-amber-500">
              <AlertTriangle size={14} className="mt-0.5 shrink-0" />
              Partial day: floorsheet trades exist for only {data.companies} of {data.expected_companies} tracked companies on {dayLabel(data.date)}, so these totals and ranks are incomplete.
            </div>
          )}

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            <StatCard label="Total Amount" value={`Rs ${formatNprArab(data.summary.total_amount)}`} hint={dayLabel(data.date)} />
            <StatCard label="Total Quantity" value={formatCount(data.summary.total_quantity)} hint="shares traded" />
            <StatCard label="Total Transactions" value={formatCount(data.summary.transaction_count)} hint={`${data.summary.active_brokers} active brokers`} />
          </div>

          {data.results.length === 0 ? (
            <div className="card py-10 text-center text-sm text-text-muted">No trades recorded on {dayLabel(data.date)}.</div>
          ) : (
            <>
              <section className="card">
                <h2 className="text-sm font-semibold text-text-primary">Top 3 by turnover</h2>
                <BrokerPodium rows={data.podium} />
              </section>

              <section className="card space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h2 className="text-sm font-semibold text-text-primary">Broker ranking</h2>
                    <p className="text-[11px] text-text-muted">
                      Turnover = buy amount + sell amount, so each trade counts for both of its brokers. Click a broker for their detail on this day.
                    </p>
                  </div>
                  <input
                    aria-label="Search brokers by name or number"
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                    placeholder="Search name or broker number"
                    className="input w-full sm:max-w-xs"
                  />
                </div>
                <BrokerTurnoverTable rows={rows} ranks={ranks} day={data.date} />
              </section>
            </>
          )}
        </div>
      )}
    </div>
  );
}
