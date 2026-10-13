import { useEffect, useState } from 'react';
import { AlertTriangle, ArrowDown, ArrowUp, Minus } from 'lucide-react';
import { getIndices, getSubIndices, type IndexRow, type IndexTable } from '../../api/marketIndices';
import { changeTone, formatPct, formatPrice, formatTradeDate } from './format';

// Compact Indices / Sub Indices cards for the Market Overview page (latest NEPSE session).

const toneText = { up: 'text-up', down: 'text-down', flat: 'text-text-muted' };
const toneChip = { up: 'bg-up/10 text-up', down: 'bg-down/10 text-down', flat: 'bg-bg-elevated text-text-muted' };
const ToneArrow = { up: ArrowUp, down: ArrowDown, flat: Minus };

// "Banking SubIndex" -> "Banking", "NEPSE Index" -> "NEPSE" (sub-indices carry their sector name).
const shortName = (row: IndexRow) => row.sector || row.name.replace(/ Index$/, '');

function IndexCard({ title, label, table }: { title: string; label: string; table: IndexTable | null }) {
  return (
    <div className="card h-full">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="rounded-md bg-accent/10 px-3 py-1.5 text-sm font-semibold text-accent-light">{title}</h3>
      </div>
      {!table?.rows.length ? (
        <p className="py-6 text-center text-xs text-text-muted">No index values stored yet.</p>
      ) : (
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-bg-border text-xs font-semibold uppercase tracking-wide text-text-secondary">
              <th className="py-2 text-left font-semibold">{label}</th>
              <th className="py-2 text-right font-semibold">Ch</th>
              <th className="py-2 text-center font-semibold">Ch %</th>
              <th className="py-2 text-right font-semibold">Current</th>
            </tr>
          </thead>
          <tbody>
            {table.rows.map((row) => {
              const tone = changeTone(row.ch_pct);
              const Arrow = ToneArrow[tone];
              const ch = row.ch == null ? null : Number(row.ch);
              return (
                <tr key={row.code} className="border-b border-bg-border hover:bg-blue-500/10">
                  <td className="max-w-[170px] truncate py-2.5 font-medium text-accent-light" title={row.name}>{shortName(row)}</td>
                  <td className={`py-2.5 text-right font-mono ${toneText[tone]}`}>
                    {ch === null ? '—' : `${ch > 0 ? '+' : ''}${ch.toLocaleString('en-IN', { maximumFractionDigits: 2 })}`}
                  </td>
                  <td className="py-2.5 text-center">
                    <span className={`inline-flex min-w-[72px] items-center justify-center gap-1 rounded-md px-2 py-0.5 font-mono text-xs ${toneChip[tone]}`}>
                      {row.ch_pct != null && <Arrow size={11} />}{formatPct(row.ch_pct)}
                    </span>
                  </td>
                  <td className="py-2.5 text-right font-mono font-semibold text-text-primary">{formatPrice(row.close)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default function IndexSummaryCards() {
  const [main, setMain] = useState<IndexTable | null>(null);
  const [sub, setSub] = useState<IndexTable | null>(null);
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');

  useEffect(() => {
    let cancelled = false;
    Promise.all([getIndices(), getSubIndices()])
      .then(([mainData, subData]) => {
        if (cancelled) return;
        setMain(mainData);
        setSub(subData);
        setState('ready');
      })
      .catch(() => { if (!cancelled) setState('error'); });
    return () => { cancelled = true; };
  }, []);

  if (state === 'loading') return <div className="card py-8 text-center text-sm text-text-muted">Loading NEPSE indices…</div>;
  if (state === 'error') {
    return (
      <div className="card flex items-center justify-center gap-2 py-8 text-sm text-down">
        <AlertTriangle size={14} /> Could not load the NEPSE indices.
      </div>
    );
  }
  const asOf = main?.as_of ?? sub?.as_of ?? null;
  return (
    <section className="flex h-full flex-col gap-2">
      <p className="text-xs text-text-muted">
        NEPSE indices · whole market{asOf ? ` · session ${formatTradeDate(asOf)}` : ''} · source: NEPSE
      </p>
      <div className="grid flex-1 items-stretch gap-4 lg:grid-cols-2">
        <IndexCard title="Indices" label="Index" table={main} />
        <IndexCard title="Sub Indices" label="Sub index" table={sub} />
      </div>
    </section>
  );
}
