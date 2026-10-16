import clsx from 'clsx';
import { CalendarDays } from 'lucide-react';
import {
  RANGE_IDS, RANGE_TITLES, formatDay, rangeAvailable, unavailableReason, type RangeId,
} from './chartRanges';

/** Price-axis scale: klinecharts' built-in y-axes. */
export type AxisMode = 'normal' | 'percentage' | 'logarithm';

const AXIS_MODES: { id: AxisMode; label: string; title: string }[] = [
  { id: 'percentage', label: '%', title: 'Percentage axis: change from the first bar in view' },
  { id: 'logarithm', label: 'Log', title: 'Logarithmic axis' },
  { id: 'normal', label: 'Auto', title: 'Linear axis, fitted to the bars in view' },
];

interface Props {
  dates: string[];                 // every trading date with a price, oldest first
  value: RangeId;
  onChange: (range: RangeId) => void;
  shownFrom: string | null;        // first date in view
  shownCount: number;              // trading sessions in view
  axisMode?: AxisMode;
  onAxisMode?: (mode: AxisMode) => void;
}

export default function RangeBar({ dates, value, onChange, shownFrom, shownCount, axisMode, onAxisMode }: Props) {
  const last = dates[dates.length - 1];
  return (
    <div className="flex min-h-[52px] flex-wrap items-center gap-x-4 gap-y-2 border-t border-bg-border px-3 py-2">
      <div className="flex items-center rounded-lg bg-bg-elevated p-1" role="group" aria-label="Date range">
        {RANGE_IDS.map((id) => {
          const available = rangeAvailable(dates, id);
          return (
            <button key={id} type="button" disabled={!available} onClick={() => onChange(id)}
              title={available ? RANGE_TITLES[id] : unavailableReason(dates, id)}
              aria-pressed={value === id}
              className={clsx(
                'h-7 rounded-md px-2.5 font-mono text-xs font-medium uppercase transition-colors disabled:cursor-not-allowed disabled:opacity-35',
                value === id ? 'bg-bg-card text-accent-light shadow-sm' : 'text-text-secondary enabled:hover:text-text-primary',
              )}>
              {id}
            </button>
          );
        })}
      </div>

      {shownFrom && shownCount > 0 && (
        <span className="flex items-center gap-2 font-mono text-xs tabular-nums text-text-primary">
          <CalendarDays size={14} className="text-text-muted" />
          {formatDay(shownFrom)}{shownFrom !== last ? ` – ${formatDay(last)}` : ''}
        </span>
      )}

      <div className="ml-auto flex items-center gap-4">
        {dates.length > 0 && (
          <span className="hidden text-xs tabular-nums text-text-muted lg:inline"
            title={`Crawled prices available from ${formatDay(dates[0])} to ${formatDay(last)} (${dates.length} trading sessions)`}>
            {shownCount > 0 ? `${shownCount} session${shownCount === 1 ? '' : 's'}` : 'No sessions in range'}
            {' · '}data since {formatDay(dates[0])}
          </span>
        )}
        {axisMode && onAxisMode && (
          <div className="flex items-center gap-0.5" role="group" aria-label="Price axis">
            {AXIS_MODES.map((mode) => (
              <button key={mode.id} type="button" onClick={() => onAxisMode(mode.id)} title={mode.title}
                aria-pressed={axisMode === mode.id}
                className={clsx(
                  'h-7 rounded-md px-2.5 font-mono text-xs font-medium transition-colors',
                  axisMode === mode.id ? 'bg-accent/15 text-accent-light' : 'text-text-secondary hover:bg-blue-500/10 hover:text-text-primary',
                )}>
                {mode.label}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
