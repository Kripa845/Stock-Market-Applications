import clsx from 'clsx';
import { AlertTriangle, ArrowDown, ArrowUp, Minus } from 'lucide-react';

import type { CompareProfile } from '../../api/compare';
import { formatPct, formatThousands } from '../market/format';
import SectionRow from './SectionRow';
import { isMissing, toNumber, type RowDef, type SectionDef } from './rows';
import { Shimmer, Tip, ui } from './ui';

export interface VisibleSection { section: SectionDef; rows: RowDef[] }

/** Sections with the rows to show; a row empty for every company is dropped when hideEmpty. */
export function visibleSections(sections: SectionDef[], profiles: CompareProfile[], hideEmpty: boolean): VisibleSection[] {
  return sections
    .map((section) => ({
      section,
      rows: hideEmpty ? section.rows.filter((row) => profiles.some((p) => !isMissing(row, p))) : section.rows,
    }))
    .filter((s) => s.rows.length > 0);
}

function ColumnHeader({ profile }: { profile: CompareProfile }) {
  if (profile.error) {
    return (
      <div className="space-y-1">
        <p className="text-sm font-bold text-white">{profile.symbol}</p>
        <p className="truncate text-xs font-normal text-[#b4bcc8]" title={profile.name}>{profile.name}</p>
        <Tip content={profile.detail ?? 'This company could not be computed.'}>
          <span className="inline-flex items-center gap-1 text-xs font-semibold text-down">
            <AlertTriangle size={12} aria-hidden="true" />Could not compute
          </span>
        </Tip>
      </div>
    );
  }
  const change = toNumber(profile.general.change_pct);
  const Icon = change === null || change === 0 ? Minus : change > 0 ? ArrowUp : ArrowDown;
  return (
    <div className="space-y-1">
      <p className="text-sm font-bold text-white">{profile.symbol}</p>
      <p className="truncate text-xs font-normal text-[#b4bcc8]" title={profile.name}>{profile.name}</p>
      <p className={clsx('text-[11px] font-normal', ui.muted)}>{profile.sector}</p>
      <p className="flex items-baseline justify-end gap-2 font-mono text-sm tabular-nums">
        <span className="text-white">{formatThousands(profile.general.ltp)}</span>
        <span className={clsx('inline-flex items-center gap-0.5 text-xs',
          change === null || change === 0 ? ui.muted : change > 0 ? 'text-up' : 'text-down')}>
          <Icon size={12} aria-hidden="true" />{formatPct(profile.general.change_pct)}
        </span>
      </p>
    </div>
  );
}

export function CompareTableSkeleton({ columns }: { columns: number }) {
  return (
    <div className={clsx(ui.card, 'overflow-hidden')} aria-busy="true" aria-label="Loading comparison">
      <div className="flex gap-4 border-b border-white/[0.08] p-4">
        <Shimmer className="h-16 w-40" />
        {Array.from({ length: columns }, (_, i) => <Shimmer key={i} className="h-16 flex-1" />)}
      </div>
      {Array.from({ length: 9 }, (_, r) => (
        <div key={r} className="flex gap-4 border-b border-white/[0.04] px-4 py-3">
          <Shimmer className="h-4 w-40" />
          {Array.from({ length: columns }, (_, i) => <Shimmer key={i} className="h-4 flex-1" />)}
        </div>
      ))}
    </div>
  );
}

export default function CompareTable({ profiles, sections, collapsed, onToggle, highlight }: {
  profiles: CompareProfile[]; sections: VisibleSection[];
  collapsed: Set<string>; onToggle: (id: string) => void; highlight: boolean;
}) {
  return (
    <div className={clsx(ui.card, 'max-h-[78vh] overflow-auto')}>
      <table className="w-full min-w-[720px] border-separate border-spacing-0">
        <caption className="sr-only">Comparison of {profiles.map((p) => p.symbol).join(', ')}</caption>
        <thead>
          <tr>
            <th scope="col" className="sticky left-0 top-0 z-30 border-b border-white/[0.08] bg-[#1a1d24] px-4 py-3 text-left align-bottom text-xs font-semibold text-[#8b93a1]">
              Metric
            </th>
            {profiles.map((p) => (
              <th key={p.symbol} scope="col"
                className="sticky top-0 z-20 min-w-[13rem] border-b border-white/[0.08] bg-[#1a1d24] px-4 py-3 text-right align-bottom">
                <ColumnHeader profile={p} />
              </th>
            ))}
          </tr>
        </thead>
        {sections.map(({ section, rows }) => (
          <SectionRow key={section.id} section={section} rows={rows} profiles={profiles}
            collapsed={collapsed.has(section.id)} onToggle={() => onToggle(section.id)} highlight={highlight} />
        ))}
      </table>
    </div>
  );
}
