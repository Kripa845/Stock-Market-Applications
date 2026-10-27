import { useMemo, useState, type ReactNode } from 'react';
import { ACC_DIST_PERIODS, type AccDistPeriod, type AccDistRow, type AccDistSide } from '../../../api/accDist';
import AccDistTable, { type RankOrder } from './AccDistTable';

const FLOAT_OPTIONS = [
  { label: 'All', min: null },
  { label: '≥ 0.01 %', min: 0.01 },
  { label: '≥ 0.05 %', min: 0.05 },
  { label: '≥ 0.10 %', min: 0.1 },
  { label: '≥ 0.50 %', min: 0.5 },
  { label: '≥ 1.00 %', min: 1 },
] as const;

const fieldClass = 'input py-2 text-[13px]';

/** Input with its label sitting on the top border. */
function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="relative block min-w-0">
      <span className="pointer-events-none absolute -top-2 left-2.5 z-[1] bg-bg-card px-1 text-[10px] font-medium text-text-secondary">
        {label}
      </span>
      {children}
    </label>
  );
}

interface AccDistPanelProps {
  side: AccDistSide;
  period: AccDistPeriod;
  onPeriodChange: (period: AccDistPeriod) => void;
  /** All rows for the period; undefined until the first load finishes. */
  rows: AccDistRow[] | undefined;
  loading: boolean;
  error: string;
  onRetry: () => void;
  watchlist: Set<string>;
}

export default function AccDistPanel({ side, period, onPeriodChange, rows, loading, error, onRetry, watchlist }: AccDistPanelProps) {
  const acc = side === 'accumulation';
  const brokerLabel = acc ? 'Buyer' : 'Seller';

  const [symbol, setSymbol] = useState('');
  const [sector, setSector] = useState('');
  const [floatIndex, setFloatIndex] = useState(0);
  const [broker, setBroker] = useState('');
  const [watchOnly, setWatchOnly] = useState(false);
  const [rankOrder, setRankOrder] = useState<RankOrder>('asc');

  const all = useMemo(() => rows ?? [], [rows]);
  const sectors = useMemo(() => [...new Set(all.map((row) => row.sector))].sort(), [all]);
  const brokers = useMemo(
    () => [...new Set(all.map((row) => row.broker))].sort((a, b) => a.localeCompare(b, undefined, { numeric: true })),
    [all],
  );

  const visible = useMemo(() => {
    const query = symbol.trim().toUpperCase();
    const floatMin = FLOAT_OPTIONS[floatIndex].min;
    const filtered = all.filter((row) =>
      (!query || row.symbol.includes(query))
      && (!sector || row.sector === sector)
      // Compare against the value as displayed, so "0.01 %" passes "≥ 0.01 %".
      && (floatMin === null || (row.float_qty_pct !== null && Math.round(Math.abs(row.float_qty_pct) * 100) / 100 >= floatMin))
      && (!broker || row.broker === broker)
      && (!watchOnly || watchlist.has(row.symbol)));
    return [...filtered].sort((a, b) => (rankOrder === 'asc' ? a.rank - b.rank : b.rank - a.rank));
  }, [all, symbol, sector, floatIndex, broker, watchOnly, watchlist, rankOrder]);

  const emptyMessage = all.length === 0 ? 'No data for this period' : 'No stocks match these filters';

  return (
    <section className="flex min-w-0 flex-col gap-4">
      <h2 className={`text-sm font-semibold ${acc ? 'text-up' : 'text-down'}`}>
        {acc ? 'Accumulation' : 'Distribution'}
      </h2>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <div className="max-w-full overflow-x-auto">
          <div className="flex rounded-lg border border-bg-border bg-bg-secondary p-0.5" role="group" aria-label="Period">
            {ACC_DIST_PERIODS.map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => onPeriodChange(value)}
                aria-pressed={value === period}
                className={`rounded-md px-2.5 py-1 text-xs tracking-wider transition-colors ${
                  value === period ? 'bg-accent font-semibold text-white shadow-sm' : 'text-text-muted hover:text-text-primary'
                }`}
              >
                {value}
              </button>
            ))}
          </div>
        </div>
        <label className="flex cursor-pointer items-center gap-2 text-xs text-text-secondary">
          <input
            type="checkbox"
            checked={watchOnly}
            onChange={(event) => setWatchOnly(event.target.checked)}
            className="h-4 w-4 accent-accent"
          />
          Watchlist
        </label>
      </div>

      <div className="grid grid-cols-2 gap-3 pt-1 sm:grid-cols-4">
        <Field label="Symbol">
          <input
            value={symbol}
            onChange={(event) => setSymbol(event.target.value)}
            placeholder="Symbol"
            className={`${fieldClass} uppercase placeholder:normal-case`}
          />
        </Field>
        <Field label="Sector">
          <select value={sector} onChange={(event) => setSector(event.target.value)} className={fieldClass}>
            <option value="">All Sectors</option>
            {sectors.map((value) => <option key={value} value={value}>{value}</option>)}
          </select>
        </Field>
        <Field label="Float Qnty %">
          <select value={floatIndex} onChange={(event) => setFloatIndex(Number(event.target.value))} className={fieldClass}>
            {FLOAT_OPTIONS.map((option, index) => <option key={option.label} value={index}>{option.label}</option>)}
          </select>
        </Field>
        <Field label={brokerLabel}>
          <select value={broker} onChange={(event) => setBroker(event.target.value)} className={fieldClass}>
            <option value="">All {brokerLabel}s</option>
            {brokers.map((value) => <option key={value} value={value}>Broker {value}</option>)}
          </select>
        </Field>
      </div>

      {error ? (
        <div className="flex h-48 flex-col items-center justify-center gap-3 rounded-lg border border-bg-border text-sm">
          <p className="text-down">{error}</p>
          <button type="button" onClick={onRetry} className="btn-ghost">Retry</button>
        </div>
      ) : (
        <AccDistTable
          side={side}
          rows={visible}
          loading={loading}
          emptyMessage={emptyMessage}
          rankOrder={rankOrder}
          onToggleRank={() => setRankOrder((value) => (value === 'asc' ? 'desc' : 'asc'))}
        />
      )}
    </section>
  );
}
