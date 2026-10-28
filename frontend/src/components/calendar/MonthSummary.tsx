import type { ReactNode } from 'react';
import clsx from 'clsx';
import type { CalendarMonth, CalendarMonthDay } from '../../api/marketCalendar';
import { changeTone, formatPct, formatPrice } from '../market/format';

// The month's NEPSE sessions at a glance, from the stored rows the grid already has:
// change = last close vs the close before the month's first session (close - change).

const adLabel = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });

const toneText = (value: number | string | null) => {
  const tone = changeTone(value);
  return tone === 'up' ? 'text-up' : tone === 'down' ? 'text-down' : 'text-text-secondary';
};

function Tile({ label, children, onClick }: { label: string; children: ReactNode; onClick?: () => void }) {
  const Tag = onClick ? 'button' : 'div';
  return (
    <Tag
      {...(onClick ? { type: 'button' as const, onClick } : {})}
      className={clsx(
        'min-w-0 rounded-md border border-bg-border bg-bg-card px-3 py-2 text-left',
        onClick && 'transition hover:border-accent-light',
      )}
    >
      <p className="text-[11px] text-text-muted">{label}</p>
      {children}
    </Tag>
  );
}

function DayTile({ label, day, onSelect }: { label: string; day: CalendarMonthDay; onSelect: (date: string) => void }) {
  return (
    <Tile label={label} onClick={() => onSelect(day.date)}>
      <p className={clsx('font-mono text-sm font-semibold', toneText(day.index!.change_pct))}>{formatPct(day.index!.change_pct)}</p>
      <p className="truncate text-[11px] text-text-muted">
        <span className="font-devanagari">{day.bs_day_np}</span> · {adLabel(day.date)}
      </p>
    </Tile>
  );
}

export default function MonthSummary({ month, onSelect }: { month: CalendarMonth; onSelect: (date: string) => void }) {
  const traded = month.days.filter((day) => day.index);
  if (traded.length === 0) return null;

  const first = traded[0].index!;
  const last = traded[traded.length - 1].index!;
  const base = first.change === null ? null : Number(first.close) - Number(first.change);
  const change = base === null ? null : Number(last.close) - base;
  const changePct = base ? (change! / base) * 100 : null;
  const withPct = traded.filter((day) => day.index!.change_pct !== null);
  const up = withPct.filter((day) => Number(day.index!.change_pct) > 0).length;
  const down = withPct.filter((day) => Number(day.index!.change_pct) < 0).length;
  const byPct = [...withPct].sort((a, b) => Number(b.index!.change_pct) - Number(a.index!.change_pct));
  const best = byPct[0];
  const worst = byPct[byPct.length - 1];
  const ongoing = month.today >= month.ad_start && month.today <= month.ad_end;

  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      <Tile label={`NEPSE ${ongoing ? 'month to date' : 'this month'}`}>
        <p className="font-mono text-sm font-semibold text-text-primary">{formatPrice(last.close)}</p>
        <p className={clsx('font-mono text-[11px]', toneText(change))}>
          {change === null ? 'No earlier close stored' : `${change > 0 ? '+' : ''}${formatPrice(change)} (${formatPct(changePct)})`}
        </p>
      </Tile>
      <Tile label="Sessions">
        <p className="font-mono text-sm font-semibold text-text-primary">{traded.length}</p>
        <p className="text-[11px]"><span className="text-up">{up} up</span> · <span className="text-down">{down} down</span></p>
      </Tile>
      {best && Number(best.index!.change_pct) > 0 ? <DayTile label="Best day" day={best} onSelect={onSelect} /> : <Tile label="Best day"><p className="text-sm text-text-muted">—</p></Tile>}
      {worst && Number(worst.index!.change_pct) < 0 ? <DayTile label="Worst day" day={worst} onSelect={onSelect} /> : <Tile label="Worst day"><p className="text-sm text-text-muted">—</p></Tile>}
    </div>
  );
}
