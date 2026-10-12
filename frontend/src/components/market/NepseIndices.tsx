import { useEffect, useState } from 'react';
import { AlertTriangle, ArrowDown, ArrowUp, Calendar, Info, Minus, RotateCcw } from 'lucide-react';
import { getIndices, getSubIndices, type IndexRow, type IndexTable } from '../../api/marketIndices';
import { changeTone, formatCount, formatNprCompact, formatPct, formatPrice, formatTradeDate } from './format';

// NEPSE main indices and the 13 sub-indices (GET /api/market-indices/indices/ and sub-indices/),
// laid out like a market-wide index board.  These describe the WHOLE NEPSE market, unlike the
// rest of the Tracked Companies page.  Values come from NEPSE's own index history; a value NEPSE
// did not publish (or a change with no previous session) is shown as "—", never as 0.

const toneText = { up: 'text-up', down: 'text-down', flat: 'text-text-muted' };
const toneChip = { up: 'bg-up/10 text-up', down: 'bg-down/10 text-down', flat: 'bg-bg-elevated text-text-muted' };
const ToneArrow = { up: ArrowUp, down: ArrowDown, flat: Minus };

const num = (value: number | string | null | undefined) => (value == null ? null : Number(value));

function signed(value: number | null, format: (n: number) => string) {
  const n = num(value);
  if (n === null) return '—';
  return `${n > 0 ? '+' : n < 0 ? '-' : ''}${format(Math.abs(n))}`;
}

const price = (n: number) => formatPrice(n);
const compact = (n: number) => formatNprCompact(n);
const count = (n: number) => formatCount(n);

function PctChip({ pct }: { pct: number | null }) {
  const tone = changeTone(pct);
  const Arrow = ToneArrow[tone];
  return (
    <span className={`inline-flex min-w-[72px] items-center justify-center gap-1 rounded-md px-1.5 py-0.5 font-mono text-[11px] ${toneChip[tone]}`}>
      {num(pct) !== null && <Arrow size={11} />}{formatPct(pct)}
    </span>
  );
}

function Delta({ value, format }: { value: number | null; format: (n: number) => string }) {
  return <span className={`font-mono ${toneText[changeTone(value)]}`}>{signed(value, format)}</span>;
}

const HEADERS = [
  'Symbol', 'Open', 'High', 'Low', 'Close', 'Ch', 'Ch %', 'Turnover', 'Tu. Ch', 'Tu. Ch %',
  'Vol.', 'Vol. Ch', 'Vol. Ch %', 'Trans', 'Trans. Ch', 'Trans. Ch %',
];

function IndexBoard({ title, rows }: { title: string; rows: IndexRow[] }) {
  return (
    <div className="card overflow-x-auto p-0">
      <div className="px-4 pt-4">
        <h3 className="inline-block rounded-md bg-accent/10 px-3 py-1.5 text-sm font-semibold text-accent-light">{title}</h3>
      </div>
      <table className="mt-3 w-full min-w-[1280px] text-xs">
        <thead>
          <tr className="border-b border-bg-border text-[11px] font-semibold uppercase tracking-wide text-text-secondary">
            {HEADERS.map((label, i) => (
              <th key={label} className={`whitespace-nowrap px-2 py-2 font-semibold ${i === 0 ? 'pl-4 text-left' : i === HEADERS.length - 1 ? 'pr-4 text-right' : 'text-right'}`}>
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.code} className="border-b border-bg-border hover:bg-bg-elevated/50">
              <td className="py-2.5 pl-4 pr-2">
                <div className="flex items-center gap-2.5">
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-accent/15 text-xs font-bold text-accent-light">
                    {row.code.charAt(0)}
                  </span>
                  <span className="min-w-0">
                    <span className="block font-semibold text-accent-light">{row.code.replace(/_/g, '')}</span>
                    <span className="block truncate text-[11px] text-text-muted">{row.name}</span>
                  </span>
                </div>
              </td>
              <td className="px-2 text-right font-mono text-text-secondary">{formatPrice(row.open)}</td>
              <td className="px-2 text-right font-mono text-text-secondary">{formatPrice(row.high)}</td>
              <td className="px-2 text-right font-mono text-text-secondary">{formatPrice(row.low)}</td>
              <td className="px-2 text-right font-mono font-semibold text-text-primary">{formatPrice(row.close)}</td>
              <td className="px-2 text-right"><Delta value={row.ch} format={price} /></td>
              <td className="px-2 text-right"><PctChip pct={row.ch_pct} /></td>
              <td className="whitespace-nowrap px-2 text-right font-mono text-text-primary">
                {formatNprCompact(row.turnover)}
                {num(row.turnover_share_pct) !== null && (
                  <span className="ml-1 text-[10px] text-text-muted">({Number(row.turnover_share_pct).toFixed(2)}%)</span>
                )}
              </td>
              <td className="whitespace-nowrap px-2 text-right"><Delta value={row.tu_ch} format={compact} /></td>
              <td className="px-2 text-right"><PctChip pct={row.tu_ch_pct} /></td>
              <td className="whitespace-nowrap px-2 text-right font-mono text-text-primary">{formatNprCompact(row.volume)}</td>
              <td className="whitespace-nowrap px-2 text-right"><Delta value={row.vol_ch} format={compact} /></td>
              <td className="px-2 text-right"><PctChip pct={row.vol_ch_pct} /></td>
              <td className="px-2 text-right font-mono text-text-primary">{formatCount(row.transactions)}</td>
              <td className="px-2 text-right"><Delta value={row.trans_ch} format={count} /></td>
              <td className="py-2.5 pl-2 pr-4 text-right"><PctChip pct={row.trans_ch_pct} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function NepseIndices() {
  const [date, setDate] = useState('');            // '' = latest session
  const [main, setMain] = useState<IndexTable | null>(null);
  const [sub, setSub] = useState<IndexTable | null>(null);
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');

  useEffect(() => {
    let cancelled = false;
    setState('loading');
    setMain(null);
    setSub(null);                                    // never show another date's numbers while loading
    Promise.all([getIndices(date || undefined), getSubIndices(date || undefined)])
      .then(([mainData, subData]) => {
        if (cancelled) return;
        setMain(mainData);
        setSub(subData);
        setState('ready');
      })
      .catch(() => { if (!cancelled) setState('error'); });
    return () => { cancelled = true; };
  }, [date]);

  const asOf = main?.as_of ?? sub?.as_of ?? null;
  const previous = main?.rows[0]?.previous_date ?? sub?.rows[0]?.previous_date ?? null;
  const marketOpen = main?.market_open || sub?.market_open;
  const empty = state === 'ready' && !main?.rows.length && !sub?.rows.length;

  return (
    <section className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-text-primary">NEPSE indices</h2>
          <p className="text-xs text-text-muted">
            Whole NEPSE market, not only the tracked companies
            {asOf ? <> · session {formatTradeDate(asOf)}{previous ? <> vs {formatTradeDate(previous)}</> : null}</> : null}
            {' '}· source: NEPSE
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <label className="flex items-center gap-2 rounded-lg border border-bg-border bg-bg-elevated px-2.5 py-1.5 text-text-secondary">
            <Calendar size={13} />
            <input type="date" value={date} max={new Date().toISOString().slice(0, 10)}
              onChange={(e) => setDate(e.target.value)}
              className="bg-transparent text-text-primary outline-none [color-scheme:dark]" aria-label="Select date" />
          </label>
          <button onClick={() => setDate('')} disabled={!date}
            className="btn-ghost flex items-center gap-1.5 px-2.5 py-1.5 disabled:opacity-40">
            <RotateCcw size={13} />Reset
          </button>
        </div>
      </div>

      {marketOpen && (
        <p className="flex items-start gap-1.5 rounded-md border border-yellow-400/30 bg-yellow-400/10 px-3 py-2 text-xs text-yellow-400">
          <Info size={13} className="mt-px shrink-0" />
          The market is open: volume, turnover and transaction changes are not final until the session closes.
        </p>
      )}
      {date && asOf && asOf !== date && (
        <p className="flex items-center gap-1.5 text-xs text-text-muted">
          <Info size={12} />No session on {formatTradeDate(date)}; showing the previous session, {formatTradeDate(asOf)}.
        </p>
      )}

      {state === 'loading' && <div className="card py-10 text-center text-sm text-text-muted">Loading NEPSE indices…</div>}
      {state === 'error' && (
        <div className="card flex items-center justify-center gap-2 py-10 text-sm text-down">
          <AlertTriangle size={14} /> Could not load the NEPSE indices. No older data is shown.
        </div>
      )}
      {empty && (
        <div className="card py-8 text-center text-sm text-text-muted">
          No index values stored {date ? 'on or before this date' : 'yet'}. They are fetched from NEPSE after each session
          closes (or run <span className="font-mono">python manage.py sync_market_indices --since YYYY-MM-DD</span>).
        </div>
      )}
      {state === 'ready' && !!main?.rows.length && <IndexBoard title="Index" rows={main.rows} />}
      {state === 'ready' && !!sub?.rows.length && <IndexBoard title="Sub Index" rows={sub.rows} />}
    </section>
  );
}
