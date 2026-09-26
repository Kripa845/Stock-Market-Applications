import { useMemo, useState } from 'react';
import type { NewsPriceCorrelation } from '../../api/analysis';

type Reaction = NewsPriceCorrelation['market_reaction'];

const money = (value: number | null | undefined) => value == null
  ? '—'
  : `Rs. ${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const quantity = (value: number | null | undefined) => value == null ? '—' : value.toLocaleString();
const percent = (value: number | null | undefined) => value == null
  ? '—'
  : `${value > 0 ? '+' : ''}${value.toFixed(2)}%`;
const dateLabel = (value: string | null | undefined) => value
  ? new Date(`${value}T00:00:00`).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
  : '—';

function CorrelationValue({ value, minimum }: { value: { coefficient: number | null; observations: number }; minimum: number }) {
  if (value.observations < minimum || value.coefficient === null) {
    return <span className="text-text-muted">Insufficient historical data</span>;
  }
  return <span className="font-mono font-semibold tabular-nums">{value.coefficient > 0 ? '+' : ''}{value.coefficient.toFixed(2)}</span>;
}

export default function NewsMarketReaction({ data }: { data: Reaction | null | undefined }) {
  const [selectedNewsDate, setSelectedNewsDate] = useState('');
  const selectedEvent = useMemo(() => {
    if (!data?.events.length) return null;
    return data.events.find(event => event.news_date === selectedNewsDate) ?? data.events[0];
  }, [data, selectedNewsDate]);

  if (!data) return null;

  const valuesFor = (field: 'close' | 'price_return_pct' | 'volume' | 'volume_change_pct') =>
    (selectedEvent?.sessions ?? []).map(session => session?.[field] ?? null);

  const reactionRows: Array<{ label: string; field: 'close' | 'price_return_pct' | 'volume' | 'volume_change_pct'; format: (value: number | null) => string }> = [
    { label: 'Closing Price', field: 'close', format: money },
    { label: 'Price Return', field: 'price_return_pct', format: percent },
    { label: 'Volume', field: 'volume', format: quantity },
    { label: 'Volume Change', field: 'volume_change_pct', format: percent },
  ];

  return (
    <section className="card space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-text-primary">News → Market Reaction</h3>
          <p className="mt-1 text-[10px] text-text-muted">Categorized news followed by the next two observed trading sessions.</p>
        </div>
        {data.events.length > 1 && (
          <label className="text-[10px] text-text-muted">
            News event
            <select
              className="input ml-2 py-1 text-xs"
              value={selectedEvent?.news_date ?? ''}
              onChange={event => setSelectedNewsDate(event.target.value)}
            >
              {data.events.map(event => <option key={event.news_date} value={event.news_date}>{dateLabel(event.news_date)}</option>)}
            </select>
          </label>
        )}
      </div>

      {selectedEvent ? (
        <>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
            <div className="bg-bg-elevated p-2"><p className="text-[9px] uppercase text-text-muted">News Date</p><p className="mt-1 text-xs font-mono">{dateLabel(selectedEvent.news_date)}</p></div>
            <div className="bg-bg-elevated p-2"><p className="text-[9px] uppercase text-text-muted">Articles</p><p className="mt-1 text-xs font-mono">{selectedEvent.article_count}</p></div>
            <div className="bg-bg-elevated p-2"><p className="text-[9px] uppercase text-text-muted">Positive / Neutral / Negative</p><p className="mt-1 text-xs font-mono"><span className="text-up">{selectedEvent.positive_count}</span> / {selectedEvent.neutral_count} / <span className="text-down">{selectedEvent.negative_count}</span></p></div>
            <div className="bg-bg-elevated p-2"><p className="text-[9px] uppercase text-text-muted">Sentiment</p><p className={`mt-1 text-xs font-mono ${selectedEvent.sentiment_score == null ? 'text-text-muted' : selectedEvent.sentiment_score > 0 ? 'text-up' : selectedEvent.sentiment_score < 0 ? 'text-down' : ''}`}>{selectedEvent.sentiment_score == null ? 'Unavailable' : `${selectedEvent.sentiment_score > 0 ? '+' : ''}${selectedEvent.sentiment_score.toFixed(2)}`}</p></div>
            <div className="bg-bg-elevated p-2"><p className="text-[9px] uppercase text-text-muted">News Day Session</p><p className="mt-1 text-xs font-mono">{dateLabel(selectedEvent.baseline_date)}</p></div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[540px] text-xs">
              <thead className="border-b border-bg-border text-text-muted">
                <tr><th className="py-2 text-left">Metric</th>{selectedEvent.sessions.map((session, index) => <th key={index} className="py-2 text-right">{session?.label ?? ['News Day', 'T+1', 'T+2'][index]}<span className="block text-[9px] font-normal">{dateLabel(session?.date)}</span></th>)}</tr>
              </thead>
              <tbody>{reactionRows.map(row => <tr key={row.label} className="border-b border-bg-border/60 last:border-0"><td className="py-2 text-text-secondary">{row.label}</td>{valuesFor(row.field).map((value, index) => <td key={index} className="py-2 text-right font-mono tabular-nums">{row.format(value)}</td>)}</tr>)}</tbody>
            </table>
          </div>
          <p className="text-[10px] text-text-muted">{data.baseline_note}</p>
        </>
      ) : (
        <p className="py-2 text-xs text-text-muted">No categorized company news in the analysis period.</p>
      )}

      <div className="border-t border-bg-border pt-3">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <h4 className="text-xs font-semibold text-text-primary">Historical News → Market Relationship</h4>
          <span className="text-[10px] text-text-muted">Observations: {data.observations}</span>
        </div>
        <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
          {([
            ['Sentiment → T+1 Return', data.correlations.sentiment_t1_return],
            ['Sentiment → T+2 Return', data.correlations.sentiment_t2_return],
            ['News Volume → T+1 Volume', data.correlations.news_volume_t1_change],
            ['News Volume → T+2 Volume', data.correlations.news_volume_t2_change],
          ] as const).map(([label, value]) => <div key={label} className="bg-bg-elevated p-2"><p className="text-[9px] text-text-muted">{label}</p><p className="mt-1 text-xs"><CorrelationValue value={value} minimum={data.minimum_observations} /></p><p className="mt-1 text-[9px] text-text-muted">n = {value.observations}</p></div>)}
        </div>
        <p className="mt-3 text-[10px] text-text-muted">{data.disclaimer}</p>
      </div>
    </section>
  );
}
