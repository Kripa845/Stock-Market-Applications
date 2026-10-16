import { useCallback, useEffect, useId, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowDown, ArrowUp, ChevronRight, Star } from 'lucide-react';
import CompanyLogo from '../companies/CompanyLogo';
import { marketApi, type WatchlistItemRow } from '../../api/market';
import { useAuth } from '../../contexts/AuthContext';
import { useLiveRefresh } from '../../hooks/useLiveRefresh';
import { formatPrice } from './format';

// "Watchlist" cards for the signed-in user's default list (GET /market/watchlists/ + /items/):
// logo, symbol, latest crawled close, change and a full-width area sparkline, tinted by direction.
// Used on the Market Overview page and, for signed-in users only, the landing page.
// Renders nothing for visitors or users without view_watchlist.

const MAX_CARDS = 8;
const REFRESH_MS = 60_000; // end-of-day prices; no need for the 5 s live cadence

type Variant = 'app' | 'landing';

const styles: Record<Variant, { frame: string; border: string; title: string; muted: string; symbol: string; surface: string }> = {
  app: {
    frame: 'card',
    border: 'border-bg-border',
    title: 'text-text-primary',
    muted: 'text-text-muted',
    symbol: 'text-sky-400',
    surface: 'bg-bg-elevated',
  },
  landing: {
    frame: 'rounded-2xl border border-[color:var(--l-border)] bg-gradient-to-b from-[var(--l-card-from)] to-[var(--l-card-to)] p-4',
    border: 'border-[color:var(--l-border)]',
    title: 'text-[color:var(--l-text)]',
    muted: 'text-[color:var(--l-faint)]',
    symbol: 'text-[color:var(--l-accent)]',
    surface: 'bg-[var(--l-surface)]',
  },
};

function AreaSparkline({ data, up }: { data: number[]; up: boolean }) {
  const gradientId = useId();
  if (data.length < 2) return <div className="h-12" />;
  const width = 200;
  const height = 48;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const points = data.map((value, index) => {
    const x = (index / (data.length - 1)) * width;
    const y = 2 + ((max - value) / range) * (height - 4);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const color = up ? '#26a69a' : '#ef5350';
  return (
    <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" className="h-12 w-full" aria-hidden>
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity={0.45} />
          <stop offset="100%" stopColor={color} stopOpacity={0.05} />
        </linearGradient>
      </defs>
      <polygon points={`0,${height} ${points.join(' ')} ${width},${height}`} fill={`url(#${gradientId})`} />
      <polyline points={points.join(' ')} fill="none" stroke={color} strokeWidth={1.5} vectorEffect="non-scaling-stroke" strokeLinejoin="round" />
    </svg>
  );
}

function WatchCard({ row, variant }: { row: WatchlistItemRow; variant: Variant }) {
  const pct = row.change_pct === null ? null : Number(row.change_pct);
  const change = row.change === null ? null : Number(row.change);
  const closes = row.sparkline.map((point) => Number(point.close));
  const up = pct === null ? closes.length < 2 || closes[closes.length - 1] >= closes[0] : pct >= 0;
  const tint = pct === null || pct === 0
    ? `border-transparent ${styles[variant].surface}`
    : up ? 'border-up/20 bg-up/10' : 'border-down/20 bg-down/10';
  const tone = pct === null || pct === 0 ? styles[variant].muted : up ? 'text-up' : 'text-down';
  return (
    <Link
      to={`/companies/${row.symbol}`}
      title={row.name}
      className={`group flex flex-col overflow-hidden rounded-lg border ${tint} transition hover:-translate-y-0.5`}
    >
      <div className="space-y-1.5 px-3 pt-3">
        <div className="flex items-center gap-2">
          <CompanyLogo symbol={row.symbol} name={row.name} logoUrl={row.logo_url} size="sm" />
          <span className={`font-mono text-sm font-semibold ${styles[variant].symbol} group-hover:underline`}>{row.symbol}</span>
        </div>
        <p className={`font-mono text-base font-bold ${styles[variant].title}`}>{formatPrice(row.ltp)}</p>
        <div className="flex items-center gap-2 text-xs">
          <span className={`font-mono ${tone}`}>
            {change === null ? '—' : `${change > 0 ? '+' : ''}${change.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`}
          </span>
          {pct !== null && (
            <span className={`inline-flex items-center gap-0.5 rounded px-1.5 py-0.5 font-mono ${pct > 0 ? 'bg-up/15 text-up' : pct < 0 ? 'bg-down/15 text-down' : `bg-black/10 ${styles[variant].muted}`}`}>
              {pct > 0 ? <ArrowUp size={10} /> : pct < 0 ? <ArrowDown size={10} /> : null}
              {Math.abs(pct).toFixed(2)}%
            </span>
          )}
        </div>
      </div>
      <div className="mt-2">
        <AreaSparkline data={closes} up={up} />
      </div>
    </Link>
  );
}

export default function WatchlistStrip({ variant = 'app' }: { variant?: Variant }) {
  const { user, hasPermission } = useAuth();
  const allowed = Boolean(user) && hasPermission('view_watchlist');
  const [rows, setRows] = useState<WatchlistItemRow[] | null>(null);
  const [listName, setListName] = useState('Watchlist');
  const [failed, setFailed] = useState(false);

  const load = useCallback(() => {
    if (!allowed) return;
    marketApi.watchlists()
      .then((lists) => {
        const list = lists.find((item) => item.is_default) ?? lists[0];
        if (!list) { setRows([]); return; }
        setListName(list.name);
        return marketApi.watchlistItems(list.id).then((data) => setRows(data.rows));
      })
      .then(() => setFailed(false))
      .catch(() => setFailed(true));
  }, [allowed]);

  useEffect(() => { load(); }, [load]);
  useLiveRefresh(load, REFRESH_MS);

  if (!allowed || (failed && rows === null)) return null;
  const s = styles[variant];

  return (
    <section className={`${s.frame} space-y-3`}>
      <div className={`flex items-center justify-between border-b pb-2 ${s.border}`}>
        <h2 className={`flex items-center gap-2 text-sm font-semibold ${s.title}`}>
          Watchlist
          {listName !== 'Watchlist' && <span className={`text-xs font-normal ${s.muted}`}>· {listName}</span>}
        </h2>
        <Link to="/watchlist" className={`rounded p-1 ${s.muted} hover:bg-black/10 hover:text-current`} aria-label="Open watchlist" title="Open watchlist">
          <ChevronRight size={16} />
        </Link>
      </div>
      {rows === null ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[0, 1, 2, 3].map((key) => <div key={key} className={`h-36 animate-pulse rounded-lg ${s.surface}`} />)}
        </div>
      ) : rows.length === 0 ? (
        <div className={`flex flex-col items-center gap-2 py-8 text-sm ${s.muted}`}>
          <Star size={18} />
          <p>Your watchlist is empty.</p>
          <Link to="/watchlist" className={`font-medium ${s.symbol} hover:underline`}>Add companies</Link>
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {rows.slice(0, MAX_CARDS).map((row) => <WatchCard key={row.id} row={row} variant={variant} />)}
        </div>
      )}
      {rows && rows.length > MAX_CARDS && (
        <Link to="/watchlist" className={`block text-center text-xs ${s.symbol} hover:underline`}>
          View all {rows.length} companies
        </Link>
      )}
    </section>
  );
}
