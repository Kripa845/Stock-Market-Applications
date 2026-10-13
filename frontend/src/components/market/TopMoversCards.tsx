import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { AlertTriangle, ArrowDown, ArrowUp, ChevronRight, TrendingDown, TrendingUp, type LucideIcon } from 'lucide-react';
import { marketApi, type MoverPeriod, type MoversResponse, type TrackedRow } from '../../api/market';
import CompanyLogo from '../companies/CompanyLogo';
import { formatPct, formatPrice, formatTradeDate } from './format';

// Top Gainers / Top Losers of the TRACKED companies for the Market Overview page.
// Ranking is done by the backend (services/movers.py); this only formats.

const ROWS = 10;
const PERIODS: { id: MoverPeriod; label: string }[] = [
  { id: '1D', label: '1D' }, { id: '5S', label: '5 sessions' }, { id: '20S', label: '20 sessions' },
];

interface SideSpec { title: string; icon: LucideIcon; tone: string; chip: string; arrow: LucideIcon; link: string }

const GAINERS: SideSpec = { title: 'Top Gainers', icon: TrendingUp, tone: 'text-up', chip: 'bg-up/10 text-up', arrow: ArrowUp, link: '/market/gainers' };
const LOSERS: SideSpec = { title: 'Top Losers', icon: TrendingDown, tone: 'text-down', chip: 'bg-down/10 text-down', arrow: ArrowDown, link: '/market/losers' };

function MoversCard({ spec, rows, emptyText }: { spec: SideSpec; rows: TrackedRow[]; emptyText: string }) {
  const navigate = useNavigate();
  const Icon = spec.icon;
  const Arrow = spec.arrow;
  return (
    <div className="card h-full">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-text-primary">
          <Icon size={15} className={spec.tone} /> {spec.title}
        </h3>
        <Link to={spec.link} className="flex items-center gap-0.5 text-xs text-accent-light hover:underline">
          View all <ChevronRight size={13} />
        </Link>
      </div>
      {rows.length === 0 ? (
        <p className="py-6 text-center text-xs text-text-muted">{emptyText}</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-bg-border text-xs font-semibold uppercase tracking-wide text-text-secondary">
              <th className="py-2 text-left font-semibold">Symbol</th>
              <th className="py-2 text-right font-semibold">LTP</th>
              <th className="py-2 text-right font-semibold">Ch</th>
              <th className="py-2 text-right font-semibold">Ch %</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => {
              const ch = row.change == null ? null : Number(row.change);
              return (
                <tr key={row.symbol} onClick={() => navigate(`/companies/${row.symbol}`)}
                  className="cursor-pointer border-b border-bg-border last:border-0 hover:bg-blue-500/10">
                  <td className="py-2">
                    <span className="flex min-w-0 items-center gap-2">
                      <CompanyLogo symbol={row.symbol} name={row.name} logoUrl={row.logo_url} size="sm" />
                      <span className="min-w-0">
                        <span className="block font-semibold text-accent-light">
                          {row.symbol}{row.adjusted && <span className="ml-0.5 text-amber-400" title="Adjusted for a corporate action">*</span>}
                        </span>
                        <span className="block max-w-[160px] truncate text-[11px] text-text-muted" title={row.name}>{row.name}</span>
                      </span>
                    </span>
                  </td>
                  <td className="py-2 text-right font-mono text-text-primary">{formatPrice(row.close)}</td>
                  <td className={`py-2 text-right font-mono ${spec.tone}`}>
                    {ch === null ? '—' : `${ch > 0 ? '+' : ''}${ch.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`}
                  </td>
                  <td className="py-2 pl-2 text-right">
                    <span className={`inline-flex min-w-[72px] items-center justify-center gap-1 rounded-md px-2 py-0.5 font-mono text-xs ${spec.chip}`}>
                      {row.change_pct != null && <Arrow size={11} />}{formatPct(row.change_pct)}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default function TopMoversCards() {
  const [period, setPeriod] = useState<MoverPeriod>('1D');
  const [data, setData] = useState<MoversResponse | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setData(null);                                   // never show another period's rows while loading
    setError(false);
    marketApi.movers(period, ROWS)
      .then((movers) => { if (!cancelled) setData(movers); })
      .catch(() => { if (!cancelled) setError(true); });
    return () => { cancelled = true; };
  }, [period]);

  const empty = data?.reason ?? 'No rows for this session.';
  return (
    <section className="space-y-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-text-muted">
          Tracked companies{data?.as_of ? ` · session ${formatTradeDate(data.as_of)}` : ''}
          {data?.base_date && period !== '1D' ? ` vs ${formatTradeDate(data.base_date)}` : ''} · not live
        </p>
        <div className="inline-flex gap-1 rounded-lg bg-bg-elevated p-0.5 text-xs font-semibold">
          {PERIODS.map((p) => (
            <button key={p.id} onClick={() => setPeriod(p.id)}
              className={`rounded-md px-3 py-1 ${period === p.id ? 'bg-accent/15 text-accent-light' : 'text-text-secondary hover:text-text-primary'}`}>
              {p.label}
            </button>
          ))}
        </div>
      </div>
      {error && (
        <div className="card flex items-center justify-center gap-2 py-8 text-sm text-down">
          <AlertTriangle size={14} /> Could not load the top gainers and losers.
        </div>
      )}
      {!error && !data && <div className="card py-8 text-center text-sm text-text-muted">Loading gainers and losers…</div>}
      {data && (
        <div className="grid items-stretch gap-4 lg:grid-cols-2">
          <MoversCard spec={GAINERS} rows={data.gainers} emptyText={empty} />
          <MoversCard spec={LOSERS} rows={data.losers} emptyText={empty} />
        </div>
      )}
    </section>
  );
}
