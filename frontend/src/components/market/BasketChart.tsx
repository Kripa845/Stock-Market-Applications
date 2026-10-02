import type { BasketRow } from '../../api/market';
import { formatTradeDate } from './format';

// "Tracked Basket" levels (base 1000): the turnover-weighted and equal-weighted
// variants over the tracked companies. Not the NEPSE index.

const SERIES = [
  { key: 'level', label: 'Turnover-weighted', color: '#8b5cf6' },
  { key: 'equal_weight_level', label: 'Equal-weighted', color: '#06b6d4' },
] as const;

export default function BasketChart({ rows, height = 150, mutedClass = 'text-text-muted' }: {
  rows: BasketRow[];
  height?: number;
  /** Tailwind text colour class for legend / axis text (the landing page passes its own). */
  mutedClass?: string;
}) {
  const points = rows.filter((row) => row.level !== null || row.equal_weight_level !== null);
  if (points.length < 2) {
    return <p className={`py-6 text-center text-xs ${mutedClass}`}>Not enough sessions to draw the basket yet.</p>;
  }

  // A variant with no values yet (e.g. equal-weight before the snapshots are rebuilt) is left out.
  const series = SERIES.filter((s) => points.some((row) => row[s.key] !== null));
  const values = points.flatMap((row) => series.map((s) => row[s.key])).filter((v): v is number => v !== null).map(Number);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const x = (i: number) => (i / (points.length - 1)) * 100;
  const y = (v: number) => 4 + ((max - v) / range) * 32;

  const pathFor = (key: (typeof SERIES)[number]['key']) => {
    let d = '';
    let pen = false;
    points.forEach((row, i) => {
      const v = row[key];
      if (v === null) { pen = false; return; }
      d += `${pen ? 'L' : 'M'}${x(i).toFixed(2)},${y(Number(v)).toFixed(2)} `;
      pen = true;
    });
    return d.trim();
  };

  const last = points[points.length - 1];
  return (
    <div>
      <div className={`mb-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[11px] ${mutedClass}`}>
        {series.map((s) => (
          <span key={s.key} className="inline-flex items-center gap-1.5">
            <span className="h-0.5 w-4 rounded" style={{ background: s.color }} />
            {s.label}
            <span className="font-mono font-semibold" style={{ color: s.color }}>
              {last[s.key] === null ? '—' : Number(last[s.key]).toFixed(2)}
            </span>
          </span>
        ))}
      </div>
      <svg viewBox="0 0 100 40" preserveAspectRatio="none" className="block w-full" style={{ height }} role="img"
        aria-label="Tracked Basket levels, turnover-weighted and equal-weighted">
        <line x1="0" x2="100" y1={y(1000)} y2={y(1000)} stroke="currentColor" strokeOpacity="0.15" strokeDasharray="1 1"
          vectorEffect="non-scaling-stroke" className={mutedClass} />
        {series.map((s) => (
          <path key={s.key} d={pathFor(s.key)} fill="none" stroke={s.color} strokeWidth="2" strokeLinejoin="round"
            vectorEffect="non-scaling-stroke" />
        ))}
      </svg>
      <div className={`mt-1 flex justify-between text-[10px] ${mutedClass}`}>
        <span>{formatTradeDate(points[0].date)}</span>
        <span>Base 1000</span>
        <span>{formatTradeDate(last.date)}</span>
      </div>
    </div>
  );
}
