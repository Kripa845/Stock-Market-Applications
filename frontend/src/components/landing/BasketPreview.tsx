import { useEffect, useState } from 'react';
import BasketChart from '../market/BasketChart';
import { formatTradeDate } from '../market/format';
import { marketApi, type PublicSnapshot } from '../../api/market';

// Landing "research" preview drawn from REAL data: the Tracked Basket levels from
// GET /api/market/public/snapshot/ (computed from crawled closing prices). It replaced an
// illustrative candlestick drawing, so nothing on the landing page is simulated.

export default function BasketPreview() {
  const [data, setData] = useState<PublicSnapshot | null>(null);
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');

  useEffect(() => {
    let cancelled = false;
    marketApi.publicSnapshot()
      .then((snapshot) => { if (!cancelled) { setData(snapshot); setState('ready'); } })
      .catch(() => { if (!cancelled) setState('error'); });
    return () => { cancelled = true; };
  }, []);

  const rows = data?.basket.rows ?? [];
  return (
    <div className="relative">
      <div className="absolute -inset-6 rounded-3xl bg-violet-600/25 blur-3xl" aria-hidden />
      <div className="relative overflow-hidden rounded-2xl border border-violet-400/25 bg-[#0e0b1a]/90 shadow-2xl">
        <div className="flex items-center gap-2 border-b border-white/10 px-4 py-3">
          <span className="h-2.5 w-2.5 rounded-full bg-red-400/70" /><span className="h-2.5 w-2.5 rounded-full bg-amber-300/70" />
          <span className="h-2.5 w-2.5 rounded-full bg-emerald-400/70" />
          <span className="ml-3 text-xs font-medium text-zinc-300">Tracked Basket</span>
          <span className="ml-auto rounded-md bg-violet-500/20 px-2 py-0.5 text-[10px] text-violet-200">
            {data?.as_of ? `Close of ${formatTradeDate(data.as_of)}` : 'Latest close'}
          </span>
        </div>
        <div className="px-4 pb-4 pt-3">
          {state === 'loading' && <div className="h-[190px] animate-pulse rounded-lg bg-white/[0.03]" aria-hidden />}
          {state === 'error' && (
            <p className="py-16 text-center text-xs text-zinc-400">Tracked prices are unavailable right now.</p>
          )}
          {state === 'ready' && rows.length < 2 && (
            <p className="py-16 text-center text-xs text-zinc-400">Not enough crawled sessions to draw the basket yet.</p>
          )}
          {state === 'ready' && rows.length >= 2 && (
            <>
              <BasketChart rows={rows} height={170} mutedClass="text-zinc-400" />
              <p className="mt-3 text-[11px] text-zinc-500">
                Our index of the {data?.summary.tracked_count ?? ''} tracked companies over the last {rows.length} sessions,
                computed from crawled ShareSansar closing prices. Base 1000. Not the NEPSE index.
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
