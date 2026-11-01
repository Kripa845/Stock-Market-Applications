import clsx from 'clsx';
import { ChevronDown, Info } from 'lucide-react';

import type { CompareProfile } from '../../api/compare';
import MetricCell from './MetricCell';
import { comparable, type RowDef, type SectionDef } from './rows';
import { Tip, ui } from './ui';

/** The symbol holding the single best value in a row, or null (fewer than 2 values, or a tie). */
export function bestSymbol(row: RowDef, profiles: CompareProfile[]): string | null {
  const values = profiles
    .map((p) => ({ symbol: p.symbol, n: comparable(row, p) }))
    .filter((v): v is { symbol: string; n: number } => v.n !== null);
  if (values.length < 2) return null;
  values.sort((a, b) => (row.better === 'higher' ? b.n - a.n : a.n - b.n));
  return values[0].n === values[1].n ? null : values[0].symbol;
}

export default function SectionRow({ section, rows, profiles, collapsed, onToggle, highlight }: {
  section: SectionDef; rows: RowDef[]; profiles: CompareProfile[];
  collapsed: boolean; onToggle: () => void; highlight: boolean;
}) {
  const bodyId = `compare-section-${section.id}`;
  return (
    <tbody id={bodyId}>
      <tr className={ui.band}>
        <th scope="rowgroup" colSpan={profiles.length + 1} className="p-0 text-left">
          <button type="button" onClick={onToggle} aria-expanded={!collapsed} aria-controls={bodyId}
            className={clsx('sticky left-0 flex items-center gap-2 px-4 py-2 text-xs font-bold uppercase tracking-wide text-[#9fe3dc]', ui.focus)}>
            <ChevronDown size={14} aria-hidden="true" className={clsx('transition-transform', collapsed && '-rotate-90')} />
            {section.title}
            <span className={clsx('font-normal normal-case tracking-normal', ui.muted)}>{rows.length} rows</span>
          </button>
        </th>
      </tr>
      {!collapsed && rows.map((row) => {
        const best = highlight && row.better ? bestSymbol(row, profiles) : null;
        return (
          <tr key={row.id} className="border-t border-white/[0.05] align-top hover:bg-white/[0.02]">
            <th scope="row"
              className="sticky left-0 z-10 w-44 min-w-[11rem] bg-[#1a1d24] px-4 py-2.5 text-left text-xs font-semibold text-[#c7cdd6]">
              <span className="inline-flex items-center gap-1.5">
                {row.label}
                {row.tooltip && (
                  <Tip content={row.tooltip} label={`About ${row.label}`}>
                    <Info size={12} aria-hidden="true" className={ui.muted} />
                  </Tip>
                )}
              </span>
              {row.better && <span className={clsx('block text-[10px] font-normal', ui.muted)}>{row.better === 'higher' ? 'Higher is better' : 'Lower is better'}</span>}
            </th>
            {profiles.map((p) => (
              <td key={p.symbol} className="px-4 py-2.5 text-right text-sm">
                <MetricCell row={row} profile={p} best={best === p.symbol} />
              </td>
            ))}
          </tr>
        );
      })}
    </tbody>
  );
}
