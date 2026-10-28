import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { X } from 'lucide-react';
import clsx from 'clsx';
import { useCalendarDay } from '../../hooks/useMarketCalendar';
import CompanyLogo from '../companies/CompanyLogo';
import { Skeleton } from '../common/LoadingSkeleton';
import { changeTone, formatCount, formatNprCompact, formatPct, formatPrice, formatTradeDate } from '../market/format';
import { EVENT_CHIP, EVENT_LABEL, STATUS_BADGE, STATUS_LABEL } from './calendarStyles';

// Right-hand panel for one calendar day (full screen on phones).  Esc, the backdrop or × close it.

interface DayDetailPanelProps {
  date: string;
  onClose: () => void;
}

const longAdDate = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });

function Figure({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[11px] text-text-muted">{label}</dt>
      <dd className="font-mono text-sm text-text-primary">{value}</dd>
    </div>
  );
}

export default function DayDetailPanel({ date, onClose }: DayDetailPanelProps) {
  const { data: day, isLoading, isError } = useCalendarDay(date);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  const index = day?.index;
  const tone = index ? changeTone(index.change_pct ?? index.change) : 'flat';
  const toneClass = tone === 'up' ? 'text-up' : tone === 'down' ? 'text-down' : 'text-text-secondary';

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/40" onClick={onClose} aria-hidden />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label={`Market details for ${date}`}
        className="fixed inset-y-0 right-0 z-50 flex w-full flex-col overflow-y-auto border-l border-bg-border bg-bg-card sm:w-[400px]"
      >
        <header className="flex items-start justify-between gap-3 border-b border-bg-border p-4">
          <div className="min-w-0">
            <h2 className="font-devanagari text-xl font-semibold text-text-primary">
              {day ? `${day.bs.label_np}, ${day.bs.weekday_np}` : '…'}
            </h2>
            <p className="text-xs text-text-muted">{longAdDate(date)}</p>
          </div>
          <button type="button" className="btn-ghost p-1.5" onClick={onClose} aria-label="Close">
            <X size={18} />
          </button>
        </header>

        <div className="space-y-6 p-4">
          {isLoading && <div className="space-y-3"><Skeleton className="h-6 w-40" /><Skeleton className="h-24 w-full" /></div>}
          {isError && <p className="text-sm text-down">Could not load this day.</p>}

          {day && (
            <>
              <section className="flex flex-wrap items-center gap-2">
                <span className={clsx('rounded px-2 py-0.5 text-xs font-medium', STATUS_BADGE[day.status])}>{STATUS_LABEL[day.status]}</span>
                {day.is_today && <span className="rounded bg-accent px-2 py-0.5 text-xs font-semibold text-white">Today</span>}
                {day.holiday && <span className="rounded bg-down/15 px-2 py-0.5 text-xs font-medium text-down">{day.holiday}</span>}
              </section>

              <section className="space-y-3">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-text-muted">{day.index_code} index</h3>
                {index ? (
                  <>
                    <div className="flex items-baseline gap-3">
                      <span className="font-mono text-2xl font-semibold text-text-primary">{formatPrice(index.close)}</span>
                      <span className={clsx('font-mono text-sm', toneClass)}>
                        {index.change === null ? '—' : `${Number(index.change) > 0 ? '+' : ''}${formatPrice(index.change)}`}
                        {' '}({formatPct(index.change_pct)})
                      </span>
                    </div>
                    <dl className="grid grid-cols-2 gap-x-4 gap-y-2">
                      <Figure label="Open" value={formatPrice(index.open)} />
                      <Figure label="High" value={formatPrice(index.high)} />
                      <Figure label="Low" value={formatPrice(index.low)} />
                      <Figure label="Turnover (NPR)" value={formatNprCompact(index.turnover)} />
                      <Figure label="Volume" value={formatCount(index.volume)} />
                      <Figure label="Transactions" value={formatCount(index.transactions)} />
                    </dl>
                    <p className="text-[11px] text-text-muted">
                      {index.previous_date ? `Change vs ${formatTradeDate(index.previous_date)}` : 'No earlier session stored'}
                      {index.source === 'sharesansar' && ' · from ShareSansar (NEPSE feed unavailable)'}
                    </p>
                  </>
                ) : (
                  <p className="text-sm text-text-muted">
                    {day.status === 'future' ? 'Upcoming day.' : day.status === 'pending' ? 'Shown after the session closes.' : 'No index figures for this day.'}
                  </p>
                )}
              </section>

              <section className="space-y-3">
                <h3 className="text-xs font-semibold uppercase tracking-wide text-text-muted">Events</h3>
                {day.events.length === 0 ? (
                  <p className="text-sm text-text-muted">No events.</p>
                ) : (
                  <ul className="space-y-2">
                    {day.events.map((event) => (
                      <li key={event.label} className="flex items-start gap-3 rounded-md border border-bg-border p-2">
                        <CompanyLogo symbol={event.symbol || '?'} name={event.company_name} logoUrl={event.logo_url} size="sm" />
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            {event.category === 'dividend' ? (
                              <Link to={`/companies/${event.symbol}`} className="text-sm font-semibold text-text-primary hover:text-accent-light">
                                {event.symbol}
                              </Link>
                            ) : (
                              <span className="text-sm font-semibold text-text-primary">{event.symbol || '—'}</span>
                            )}
                            <span className={clsx('rounded px-1.5 text-[11px] font-medium', EVENT_CHIP[event.type])}>{EVENT_LABEL[event.type]}</span>
                          </div>
                          <p className="truncate text-xs text-text-muted">{event.company_name}</p>
                          {event.category === 'dividend' ? (
                            <p className="font-mono text-xs text-text-secondary">
                              FY {event.fiscal_year || '—'} · Bonus {formatPct(event.bonus_pct).replace('+', '')} · Cash {formatPct(event.cash_pct).replace('+', '')}
                            </p>
                          ) : (
                            <div className="space-y-0.5 text-xs text-text-secondary">
                              <p>
                                {event.issue_type_label} · <span className="font-mono">{formatCount(event.units)}</span> units
                                {event.price && <> @ <span className="font-mono">{formatPrice(event.price)}</span></>}
                                {event.ratio && <> · ratio {event.ratio}</>}
                              </p>
                              <p>
                                Opens {formatTradeDate(event.open_date)} · closes {formatTradeDate(event.close_date)}
                                {event.final_date && event.final_date !== event.close_date && <> (latest {formatTradeDate(event.final_date)})</>}
                              </p>
                              {event.issue_manager && <p className="text-text-muted">Issue manager: {event.issue_manager}</p>}
                            </div>
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
                <p className="text-[11px] text-text-muted">Dividend events: tracked companies you can access. Public issues: whole market.</p>
              </section>
            </>
          )}
        </div>
      </aside>
    </>
  );
}
