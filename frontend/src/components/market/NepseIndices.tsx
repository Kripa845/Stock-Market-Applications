import { useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { AlertTriangle, ArrowDown, ArrowUp, Calendar, Info, Minus, RotateCcw } from 'lucide-react';
import { getIndices, getSubIndices, type IndexRow, type IndexTable } from '../../api/marketIndices';
import { changeTone, formatCount, formatNprCompact, formatPct, formatPrice, formatTradeDate } from './format';

// NEPSE main indices and the 13 sub-indices (GET /api/market-indices/indices/ and sub-indices/)
// as one compact card with an Index / Sub Index switch, shown on the Market Overview page.
// These describe the WHOLE NEPSE market.  Values come from NEPSE's own index history; a value
// NEPSE did not publish (or a change with no previous session) is shown as "—", never as 0.

const toneText = { up: 'text-up', down: 'text-down', flat: 'text-text-muted' };
const toneChip = { up: 'bg-up/10 text-up', down: 'bg-down/10 text-down', flat: 'bg-bg-elevated text-text-muted' };
const ToneArrow = { up: ArrowUp, down: ArrowDown, flat: Minus };

const num = (value: number | string | null | undefined) => (value == null ? null : Number(value));

// "Banking SubIndex" -> "Banking", "NEPSE Index" -> "NEPSE" (sub-indices carry their sector name).
const shortName = (row: IndexRow) => row.sector || row.name.replace(/ Index$/, '');

function PctChip({ pct }: { pct: number | null }) {
  const tone = changeTone(pct);
  const Arrow = ToneArrow[tone];
  return (
    <span className={`inline-flex min-w-[68px] items-center justify-center gap-1 rounded-md px-1.5 py-0.5 font-mono text-[11px] ${toneChip[tone]}`}>
      {num(pct) !== null && <Arrow size={11} />}{formatPct(pct)}
    </span>
  );
}

// Small signed % under a value: turnover / volume / trades change vs the previous session.
function SubPct({ pct }: { pct: number | null }) {
  const n = num(pct);
  if (n === null) return null;
  return <span className={`block text-[10px] ${toneText[changeTone(n)]}`}>{n > 0 ? '+' : ''}{n.toFixed(2)}%</span>;
}

const SECTION_ID = 'nepse-indices';
const HEADERS = ['Index', 'Close', 'Ch', 'Ch %', 'High', 'Low', 'Turnover', 'Volume', 'Trans'];
const BOARDS = [['main', 'Index'], ['sub', 'Sub Index']] as const;
type Board = (typeof BOARDS)[number][0];

function IndexTableView({ rows }: { rows: IndexRow[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[760px] text-xs">
        <thead>
          <tr className="border-b border-bg-border text-[11px] font-semibold uppercase tracking-wide text-text-secondary">
            {HEADERS.map((label, i) => (
              <th key={label} className={`whitespace-nowrap py-2 font-semibold ${i === 0 ? 'pr-2 text-left' : i === 3 ? 'px-2 text-center' : 'px-2 text-right'}`}>
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const ch = num(row.ch);
            return (
              <tr key={row.code} className="border-b border-bg-border last:border-0 hover:bg-blue-500/10">
                <td className="max-w-[180px] truncate py-2 pr-2 font-medium text-accent-light" title={row.name}>{shortName(row)}</td>
                <td className="px-2 text-right font-mono font-semibold text-text-primary">{formatPrice(row.close)}</td>
                <td className={`px-2 text-right font-mono ${toneText[changeTone(ch)]}`}>
                  {ch === null ? '—' : `${ch > 0 ? '+' : ''}${ch.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`}
                </td>
                <td className="px-2 text-center"><PctChip pct={row.ch_pct} /></td>
                <td className="px-2 text-right font-mono text-text-secondary">{formatPrice(row.high)}</td>
                <td className="px-2 text-right font-mono text-text-secondary">{formatPrice(row.low)}</td>
                <td className="whitespace-nowrap px-2 py-1.5 text-right font-mono text-text-primary">
                  {formatNprCompact(row.turnover)}<SubPct pct={row.tu_ch_pct} />
                </td>
                <td className="whitespace-nowrap px-2 py-1.5 text-right font-mono text-text-primary">
                  {formatNprCompact(row.volume)}<SubPct pct={row.vol_ch_pct} />
                </td>
                <td className="whitespace-nowrap py-1.5 pl-2 text-right font-mono text-text-primary">
                  {formatCount(row.transactions)}<SubPct pct={row.trans_ch_pct} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function NepseIndices() {
  const [date, setDate] = useState('');            // '' = latest session
  const [board, setBoard] = useState<Board>('main');
  const [main, setMain] = useState<IndexTable | null>(null);
  const [sub, setSub] = useState<IndexTable | null>(null);
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const cardRef = useRef<HTMLDivElement>(null);
  const { hash } = useLocation();

  // Arriving from the Index / Sub Index summary cards (#nepse-indices): scroll here once the
  // board has loaded, so its height is known.
  useEffect(() => {
    if (hash === `#${SECTION_ID}` && state !== 'loading') {
      cardRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, [hash, state]);

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
  const rows = (board === 'main' ? main : sub)?.rows ?? [];

  return (
    <div id={SECTION_ID} ref={cardRef} className="card scroll-mt-4 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <div className="inline-flex gap-1 rounded-lg bg-bg-elevated p-0.5 text-xs font-semibold">
            {BOARDS.map(([key, label]) => (
              <button key={key} onClick={() => setBoard(key)}
                className={`rounded-md px-3 py-1 ${board === key ? 'bg-accent/15 text-accent-light' : 'text-text-secondary hover:text-text-primary'}`}>
                {label}
              </button>
            ))}
          </div>
          {asOf && (
            <p className="mt-1 text-[11px] text-text-muted">
              Session {formatTradeDate(asOf)}{previous ? <> vs {formatTradeDate(previous)}</> : null} · small % = change vs previous session
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 rounded-lg border border-bg-border bg-bg-elevated px-2.5 py-1.5 text-xs text-text-secondary">
            <Calendar size={13} />
            <input type="date" value={date} max={new Date().toISOString().slice(0, 10)}
              onChange={(e) => setDate(e.target.value)}
              className="bg-transparent text-text-primary outline-none [color-scheme:dark]" aria-label="Select date" />
          </label>
          <button onClick={() => setDate('')} disabled={!date}
            className="btn-ghost flex items-center gap-1.5 px-2.5 py-1.5 text-xs disabled:opacity-40">
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

      {state === 'loading' && <p className="py-8 text-center text-sm text-text-muted">Loading NEPSE indices…</p>}
      {state === 'error' && (
        <p className="flex items-center justify-center gap-2 py-8 text-sm text-down">
          <AlertTriangle size={14} /> Could not load the NEPSE indices. No older data is shown.
        </p>
      )}
      {state === 'ready' && !rows.length && (
        <p className="py-6 text-center text-sm text-text-muted">
          No index values stored {date ? 'on or before this date' : 'yet'}. They are fetched from NEPSE after each session
          closes (or run <span className="font-mono">python manage.py sync_market_indices --since YYYY-MM-DD</span>).
        </p>
      )}
      {state === 'ready' && !!rows.length && <IndexTableView rows={rows} />}
    </div>
  );
}
