// Dashboard strip: the NEPSE index's current week day by day, next to the 6-week weekday averages.
// Same data as the Weekday Summary page (/market/weekdays), which the Heatmap link opens.
import { Link } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';

import { formatPct, formatPrice, formatTradeDate } from '../market/format';
import { WEEKDAY_NAMES, gapLabel, heatClass, toneText } from '../market/weekday';
import { useWeekdaySummary } from '../../hooks/useMarketCalendar';

const BAR_H = 26;

export default function WeekToDateCard() {
  const { data, isLoading, error } = useWeekdaySummary(6);

  if (error) return null;
  if (isLoading || !data) return <div className="skeleton h-[180px] rounded-2xl" />;

  const week = data.week_rows[0];
  if (!week) return null;
  const maxAvg = Math.max(0.01, ...data.columns.map((c) => Math.abs(c.average_pct ?? 0)));

  return (
    <section className="card flex flex-col gap-6 !rounded-2xl !p-6 lg:flex-row lg:items-center lg:gap-8 lg:!p-8">
      <div className="shrink-0 lg:w-[230px]">
        <p className="text-xs font-semibold uppercase tracking-[0.14em] text-text-secondary">
          NEPSE · {week.partial ? 'Week to date' : 'Last week'}
        </p>
        <p className={`mt-2 font-mono text-4xl font-semibold ${toneText(week.change_pct)}`}>{formatPct(week.change_pct)}</p>
        <p className="mt-2 text-sm text-text-secondary">
          {week.up_days} of {week.sessions} sessions up · week of {week.label}
        </p>
      </div>

      <div className="grid flex-1 grid-cols-5 gap-2 sm:gap-3">
        {week.days.map((day) => {
          const isToday = day.date === data.today;
          const pct = day.change_pct;
          return (
            <div key={day.date}
              title={`${WEEKDAY_NAMES[day.weekday]}, ${formatTradeDate(day.date)}${pct != null ? ` · close ${formatPrice(day.close)}` : ''}`}
              className={`flex h-24 flex-col items-center justify-center gap-1 rounded-xl px-1 ${heatClass(pct)} ${
                isToday && pct != null ? 'ring-2 ring-accent' : ''
              }`}>
              <span className={`text-[11px] font-semibold uppercase tracking-wider ${isToday ? 'text-accent' : ''}`}>
                {isToday ? 'Today' : day.weekday}
              </span>
              <span className={`text-center ${pct == null ? 'text-xs sm:text-sm' : 'font-mono text-sm font-semibold sm:text-lg'}`}>
                {pct == null ? gapLabel(day, data.today) : formatPct(pct)}
              </span>
            </div>
          );
        })}
      </div>

      <div className="shrink-0 border-t border-bg-border pt-5 lg:w-[400px] lg:border-l lg:border-t-0 lg:pl-8 lg:pt-0">
        <div className="flex items-center justify-between">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-text-secondary">{data.weeks}-week weekday avg</p>
          <Link to="/market/weekdays" className="flex items-center gap-1 text-sm font-semibold text-accent hover:underline">
            Heatmap <ArrowRight size={14} />
          </Link>
        </div>
        <div className="mt-3 grid grid-cols-5 gap-2">
          {data.columns.map((column) => {
            const pct = column.average_pct;
            const h = pct == null ? 0 : Math.max(3, (Math.abs(pct) / maxAvg) * BAR_H);
            return (
              <div key={column.weekday} className="flex flex-col items-center"
                title={`${WEEKDAY_NAMES[column.weekday]}: ${column.up} of ${column.sessions} up`}>
                <span className={`font-mono text-xs font-semibold ${toneText(pct)}`}>{formatPct(pct)}</span>
                <div className="relative mt-2 w-full" style={{ height: BAR_H * 2 }}>
                  <div className="absolute inset-x-0 border-t border-bg-border" style={{ top: BAR_H }} />
                  {pct != null && pct !== 0 && (
                    <div className={`absolute left-1/2 w-1/2 -translate-x-1/2 ${pct > 0 ? 'rounded-t bg-up' : 'rounded-b bg-down'}`}
                      style={pct > 0 ? { top: BAR_H - h, height: h } : { top: BAR_H, height: h }} />
                  )}
                </div>
                <span className="mt-1 text-[11px] font-semibold uppercase tracking-wider text-text-secondary">{column.weekday}</span>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
