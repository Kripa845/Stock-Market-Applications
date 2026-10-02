import { useEffect, useState } from 'react';
import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react';
import Sparkline from '../common/Sparkline';
import BasketChart from '../market/BasketChart';
import { changeTone, formatCount, formatNprCompact, formatPct, formatPrice, formatTradeDate } from '../market/format';
import { marketApi, type PublicMover, type PublicSnapshot } from '../../api/market';

// Public "Tracked companies" preview on the landing page (GET /api/market/public/snapshot/).
// It covers only the companies StockScope tracks -- never labelled as the NEPSE market.
// Every number comes from the API; loading, empty and error states are shown explicitly and
// nothing is ever filled in or kept from an earlier response.

const card = 'rounded-2xl border border-[color:var(--l-border)] bg-gradient-to-b from-[var(--l-card-from)] to-[var(--l-card-to)]';
const toneText = { up: 'text-emerald-500', down: 'text-rose-500', flat: 'text-[color:var(--l-muted)]' };
const toneChip = {
  up: 'bg-emerald-500/10 text-emerald-500',
  down: 'bg-rose-500/10 text-rose-500',
  flat: 'bg-[var(--l-surface)] text-[color:var(--l-muted)]',
};
const ToneIcon = { up: ArrowUpRight, down: ArrowDownRight, flat: Minus };

function Breadth({ summary }: { summary: PublicSnapshot['summary'] }) {
  const parts = [
    { label: 'Advanced', value: summary.advanced, bar: 'bg-emerald-500', text: 'text-emerald-500' },
    { label: 'Declined', value: summary.declined, bar: 'bg-rose-500', text: 'text-rose-500' },
    { label: 'Unchanged', value: summary.unchanged, bar: 'bg-[color:var(--l-faint)]', text: 'text-[color:var(--l-muted)]' },
  ];
  const total = summary.tracked_count || 1;
  return (
    <div>
      <div className="flex h-2 overflow-hidden rounded-full bg-[var(--l-surface)]">
        {parts.map((p) => p.value > 0 && <div key={p.label} className={p.bar} style={{ width: `${(p.value / total) * 100}%` }} />)}
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2 text-center">
        {parts.map((p) => (
          <div key={p.label}>
            <div className={`text-xl font-semibold ${p.text}`}>{p.value}</div>
            <div className="text-[11px] text-[color:var(--l-faint)]">{p.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function MoverList({ title, rows, tone }: { title: string; rows: PublicMover[]; tone: 'up' | 'down' }) {
  return (
    <div className={`${card} p-4 sm:p-5`}>
      <h3 className={`mb-2 px-1 text-sm font-semibold ${toneText[tone]}`}>{title}</h3>
      {rows.length === 0 ? (
        <p className="px-1 py-6 text-center text-xs text-[color:var(--l-faint)]">
          No tracked company {tone === 'up' ? 'rose' : 'fell'} in this session.
        </p>
      ) : (
        <ul className="divide-y divide-[color:var(--l-border)]">
          {rows.map((row) => {
            const rowTone = changeTone(row.change_pct);
            const Icon = ToneIcon[rowTone];
            return (
              <li key={row.symbol} className="flex items-center gap-3 px-1 py-2.5">
                <div className="min-w-0 flex-1">
                  <div className="font-mono text-sm font-semibold text-[color:var(--l-text)]">{row.symbol}</div>
                  <div className="truncate text-xs text-[color:var(--l-faint)]">{row.name}</div>
                </div>
                <div className="hidden shrink-0 sm:block">
                  <Sparkline data={(row.sparkline ?? []).map((p) => Number(p.close))} width={80} height={26} positive={tone === 'up'} />
                </div>
                <div className="w-28 shrink-0 text-right">
                  <div className="font-mono text-sm text-[color:var(--l-text)]">{formatPrice(row.close)}</div>
                  <span className={`mt-0.5 inline-flex items-center gap-0.5 rounded-md px-1.5 py-0.5 font-mono text-[11px] font-medium ${toneChip[rowTone]}`}>
                    <Icon size={11} />{formatPct(row.change_pct)}
                  </span>
                  {row.adjusted && (
                    <div className="mt-0.5 text-[10px] text-sky-500" title="ShareSansar's % change against the exchange's adjusted previous close (e.g. after a bonus issue).">
                      adjusted
                    </div>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

export default function LandingTracked({ heading }: { heading: React.ReactNode }) {
  const [data, setData] = useState<PublicSnapshot | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    marketApi.publicSnapshot()
      .then((snapshot) => { if (!cancelled) setData(snapshot); })
      .catch(() => { if (!cancelled) setFailed(true); });
    return () => { cancelled = true; };
  }, []);

  const notice = (text: string) => (
    <p className={`${card} mx-auto mt-10 max-w-xl p-6 text-center text-sm text-[color:var(--l-muted)]`}>{text}</p>
  );

  return (
    <section id="tracked" className="scroll-mt-20 px-4 py-20 sm:px-6">
      {heading}
      {failed ? notice('Tracked company prices are unavailable right now. Please try again later.') : !data ? (
        <div className="mx-auto mt-12 grid max-w-6xl gap-4 lg:grid-cols-3" aria-hidden>
          <div className={`${card} h-[420px] animate-pulse lg:col-span-2`} />
          <div className={`${card} h-[420px] animate-pulse`} />
        </div>
      ) : !data.as_of ? notice('No crawled closing prices are stored yet for the tracked companies.') : (
        <>
          <p className="mx-auto mt-4 max-w-2xl text-center text-xs text-[color:var(--l-faint)]">
            Covers only the {data.summary.tracked_count} companies StockScope tracks, not the whole NEPSE market.
            Closing prices for {formatTradeDate(data.as_of)}, crawled from ShareSansar.
          </p>
          <div className="mx-auto mt-10 grid max-w-6xl gap-4 lg:grid-cols-3">
            {/* Top tracked gainers and losers for the latest session */}
            <div className="grid gap-4 sm:grid-cols-2 lg:col-span-2 lg:self-start">
              <MoverList title="Tracked gainers" rows={data.gainers} tone="up" />
              <MoverList title="Tracked losers" rows={data.losers} tone="down" />
            </div>

            <div className="flex flex-col gap-4">
              <div className={`${card} p-5`}>
                <h3 className="text-sm font-semibold text-[color:var(--l-text)]">Today across tracked companies</h3>
                <div className="mt-4"><Breadth summary={data.summary} /></div>
                <dl className="mt-5 grid grid-cols-2 gap-3 border-t border-[color:var(--l-border)] pt-4 text-sm">
                  <div>
                    <dt className="text-[11px] text-[color:var(--l-faint)]">Turnover</dt>
                    <dd className="font-mono font-semibold text-[color:var(--l-text)]">Rs {formatNprCompact(data.summary.total_turnover)}</dd>
                  </div>
                  <div>
                    <dt className="text-[11px] text-[color:var(--l-faint)]">Shares traded</dt>
                    <dd className="font-mono font-semibold text-[color:var(--l-text)]">{formatCount(data.summary.total_traded_shares)}</dd>
                  </div>
                  <div>
                    <dt className="text-[11px] text-[color:var(--l-faint)]">Upper circuit</dt>
                    <dd className={`font-mono font-semibold ${toneText.up}`}>{data.summary.positive_circuit}</dd>
                  </div>
                  <div>
                    <dt className="text-[11px] text-[color:var(--l-faint)]">Lower circuit</dt>
                    <dd className={`font-mono font-semibold ${toneText.down}`}>{data.summary.negative_circuit}</dd>
                  </div>
                </dl>
              </div>
              <div className={`${card} flex-1 p-5`}>
                <h3 className="text-sm font-semibold text-[color:var(--l-text)]">{data.basket.label}</h3>
                <p className="mb-3 text-[11px] text-[color:var(--l-faint)]">Our index of the tracked companies, base 1000. Not the NEPSE index.</p>
                <BasketChart rows={data.basket.rows} height={110} mutedClass="text-[color:var(--l-faint)]" />
              </div>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
