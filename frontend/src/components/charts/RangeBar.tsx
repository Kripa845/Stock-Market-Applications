import clsx from 'clsx';
import {
  RANGE_IDS, RANGE_TITLES, formatDay, rangeAvailable, unavailableReason, type RangeId,
} from './chartRanges';

interface Props {
  dates: string[];                 // every trading date with a price, oldest first
  value: RangeId;
  onChange: (range: RangeId) => void;
  shownFrom: string | null;        // first date in view
  shownCount: number;              // trading sessions in view
}

export default function RangeBar({ dates, value, onChange, shownFrom, shownCount }: Props) {
  const last = dates[dates.length - 1];
  return (
    <div className="flex flex-wrap items-center gap-1 border-t border-border px-2 py-1">
      {RANGE_IDS.map((id) => {
        const available = rangeAvailable(dates, id);
        return (
          <button key={id} type="button" disabled={!available} onClick={() => onChange(id)}
            title={available ? RANGE_TITLES[id] : unavailableReason(dates, id)}
            className={clsx('rounded px-2.5 py-1 text-xs font-medium transition-all disabled:cursor-not-allowed disabled:opacity-35',
              value === id ? 'bg-accent text-white' : 'text-text-secondary enabled:hover:bg-bg-elevated enabled:hover:text-text-primary')}>
            {id}
          </button>
        );
      })}
      {dates.length > 0 && (
        <span className="ml-auto pl-2 text-[11px] tabular-nums text-text-secondary"
          title={`Crawled prices available from ${formatDay(dates[0])} to ${formatDay(last)} (${dates.length} trading sessions)`}>
          {shownFrom && shownCount > 0
            ? `${formatDay(shownFrom)}${shownFrom !== last ? ` – ${formatDay(last)}` : ''} · ${shownCount} session${shownCount === 1 ? '' : 's'}`
            : 'No sessions in range'}
          <span className="hidden sm:inline"> · data since {formatDay(dates[0])}</span>
        </span>
      )}
    </div>
  );
}
