import { useMemo, useState } from 'react';
import {
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from 'recharts';
import type { NewsSentimentDailyPoint, NewsSentimentForwardResponse, PricePoint } from '../../api/analysis';

interface NewsSentimentScatterProps {
  data: NewsSentimentForwardResponse | null;
  priceData: PricePoint[];
  loading?: boolean;
  error?: string;
}

type TimelinePoint = NewsSentimentDailyPoint & { date: string; publication_date: string };
type ForwardPoint = NewsSentimentDailyPoint & {
  forward_value_pct: number;
  headline: string;
  publication_date: string;
  outcome_date: string | null;
  metric_label: string;
};
type MovementMetric = 'price' | 'volume';

const categoryColor = (category: string) => category === 'Positive'
  ? 'var(--trading-up)'
  : category === 'Negative' ? 'var(--trading-down)' : 'var(--trading-muted)';

const markerColor = (items: NewsSentimentDailyPoint['news_items']) => {
  const positive = items.filter(item => item.category === 'Positive').length;
  const negative = items.filter(item => item.category === 'Negative').length;
  if (positive > negative) return 'var(--trading-up)';
  if (negative > positive) return 'var(--trading-down)';
  return 'var(--trading-muted)';
};

const formatPercent = (value: number | null) => value === null ? '—' : `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;

function ChartTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload?: TimelinePoint | ForwardPoint }> }) {
  const point = payload?.[0]?.payload;
  if (!active || !point) return null;
  const isTimeline = !('forward_value_pct' in point);
  return (
    <div className="max-w-sm rounded-sm border border-bg-border bg-bg-elevated px-3 py-2 text-xs shadow-lg">
      <p className="mb-1 font-mono text-text-muted">{point.publication_date}</p>
      <p>Sentiment: <span className="font-mono">{point.avg_sentiment === null ? 'Unscored' : point.avg_sentiment.toFixed(3)}</span></p>
      {isTimeline ? (
        <div className="mt-1 space-y-1">
          {(point as TimelinePoint).news_items.map((item, index) => (
            <p key={`${index}-${item.headline}`} className="text-text-secondary">
              <span className="text-text-primary">{item.category}</span>
              {item.sentiment_score !== null ? ` (${item.sentiment_score.toFixed(3)})` : ''}
              {item.headline ? ` · ${item.headline}` : ''}
            </p>
          ))}
        </div>
      ) : (
        <>
          <p>{(point as ForwardPoint).metric_label}: <span className="font-mono">{formatPercent((point as ForwardPoint).forward_value_pct)}</span></p>
          {(point as ForwardPoint).outcome_date && <p className="text-text-muted">Movement date: {(point as ForwardPoint).outcome_date}</p>}
          <p className="mt-1 text-text-secondary">{(point as ForwardPoint).headline}</p>
        </>
      )}
    </div>
  );
}

export function CorrelationSummaryTable({ summary }: { summary: NewsSentimentForwardResponse['correlation_summary'] }) {
  const rows = [
    ['Sentiment vs return (T+1)', summary.sentiment_return_t1],
    ['Sentiment vs return (T+2)', summary.sentiment_return_t2],
    ['Sentiment vs volume change (T+1)', summary.sentiment_volume_change_t1],
    ['Sentiment vs volume change (T+2)', summary.sentiment_volume_change_t2],
  ] as const;

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[440px] text-xs">
        <thead><tr className="border-b border-bg-border text-left text-text-muted"><th className="py-2 pr-3 font-medium">Relationship</th><th className="py-2 text-right font-medium">Pearson r</th><th className="py-2 text-right font-medium">Days</th></tr></thead>
        <tbody>{rows.map(([label, metric]) => (
          <tr key={label} className="border-b border-bg-border/60 last:border-0">
            <td className="py-2 pr-3 text-text-secondary">{label}</td>
            <td className="py-2 text-right font-mono tabular-nums">{metric.coefficient === null ? '—' : metric.coefficient.toFixed(3)}</td>
            <td className="py-2 text-right font-mono tabular-nums text-text-muted">{metric.observations}</td>
          </tr>
        ))}</tbody>
      </table>
    </div>
  );
}

export function NewsSentimentScatter({ data, priceData, loading = false, error }: NewsSentimentScatterProps) {
  const [lag, setLag] = useState<'t1' | 't2'>('t1');
  const [metric, setMetric] = useState<MovementMetric>('price');
  const priceDates = useMemo(() => priceData.map(point => point.date), [priceData]);
  const timelinePoints = useMemo(() => {
    if (!data) return [];
    return data.daily_data.flatMap(row => {
      if (row.avg_sentiment === null) return [];
      const plotDate = priceDates.includes(row.date) ? row.date : priceDates.find(date => date > row.date);
      return plotDate ? [{ ...row, date: plotDate, publication_date: row.date }] : [];
    });
  }, [data, priceDates]);
  const points = useMemo(() => {
    if (!data) return [];
    return data.daily_data.flatMap((row: NewsSentimentDailyPoint) => {
      const forwardValue = metric === 'price'
        ? (lag === 't1' ? row.return_t1_pct : row.return_t2_pct)
        : (lag === 't1' ? row.volume_change_t1_pct : row.volume_change_t2_pct);
      if (row.avg_sentiment === null || forwardValue === null) return [];
      return [{
        ...row,
        forward_value_pct: forwardValue,
        headline: row.news_items[0]?.headline ?? '',
        publication_date: row.date,
        outcome_date: lag === 't1' ? row.t1_date : row.t2_date,
        metric_label: metric === 'price' ? 'Forward price return' : 'Forward volume change',
      }];
    });
  }, [data, lag, metric]);
  const trendLine = useMemo(() => {
    if (points.length < 2) return [];
    const xs = points.map(point => point.avg_sentiment as number);
    const ys = points.map(point => point.forward_value_pct);
    const xMean = xs.reduce((sum, value) => sum + value, 0) / xs.length;
    const yMean = ys.reduce((sum, value) => sum + value, 0) / ys.length;
    const denominator = xs.reduce((sum, x) => sum + (x - xMean) ** 2, 0);
    if (denominator === 0) return [];
    const slope = xs.reduce((sum, x, index) => sum + (x - xMean) * (ys[index] - yMean), 0) / denominator;
    const xMin = Math.min(...xs);
    const xMax = Math.max(...xs);
    return [xMin, xMax].map(avg_sentiment => ({ avg_sentiment, forward_value_pct: yMean + slope * (avg_sentiment - xMean) }));
  }, [points]);

  return (
    <section className="card space-y-4" aria-label="News sentiment and forward market movement">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-text-primary">News Sentiment vs Forward Price / Volume Movement</h3>
          <p className="mt-1 text-xs text-text-muted">Uses crawled categorized news and crawled daily OHLCV. Exploratory comparison only; this is not a validated trading signal.</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <div className="flex rounded-md bg-bg-elevated p-0.5" role="group" aria-label="Forward trading session">
            {(['t1', 't2'] as const).map(option => (
              <button key={option} type="button" onClick={() => setLag(option)} className={`rounded px-3 py-1 text-xs ${lag === option ? 'bg-accent text-white' : 'text-text-secondary'}`}>
                {option === 't1' ? 'T+1' : 'T+2'}
              </button>
            ))}
          </div>
          <div className="flex rounded-md bg-bg-elevated p-0.5" role="group" aria-label="Forward movement measure">
            {(['price', 'volume'] as const).map(option => (
              <button key={option} type="button" onClick={() => setMetric(option)} className={`rounded px-3 py-1 text-xs ${metric === option ? 'bg-accent text-white' : 'text-text-secondary'}`}>
                {option === 'price' ? 'Price Return %' : 'Volume Change %'}
              </button>
            ))}
          </div>
        </div>
      </div>

      {loading ? <p className="py-8 text-center text-xs text-text-muted">Loading news and market comparison…</p>
        : error ? <p className="py-8 text-center text-xs text-down">{error}</p>
          : !data || data.daily_data.length === 0 ? <p className="py-8 text-center text-xs text-text-muted">No categorized news in this date range.</p>
            : (
              <>
                <div>
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                    <h4 className="text-xs font-semibold text-text-primary">Sentiment Overlay Timeline</h4>
                    <div className="flex gap-3 text-[10px] text-text-muted">
                      <span className="text-up">● Positive</span><span className="text-down">● Negative</span><span>● Neutral</span>
                    </div>
                  </div>
                  <p className="mb-2 text-[10px] text-text-muted">News published on non-trading dates is placed on the next trading session; the tooltip retains its publication date.</p>
                  {timelinePoints.length === 0 ? <p className="py-8 text-center text-xs text-text-muted">No scored news dates align with the visible price range.</p> : (
                    <ResponsiveContainer width="100%" height={210}>
                      <ComposedChart data={priceData} syncId="company-ohlcv" syncMethod="value" margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                        <CartesianGrid stroke="var(--trading-grid)" strokeOpacity={0.5} vertical={false} />
                        <XAxis dataKey="date" tick={{ fontSize: 9, fill: 'var(--trading-muted)' }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
                        <YAxis yAxisId="sentiment" orientation="right" domain={[-1, 1]} ticks={[-1, 0, 1]} tick={{ fontSize: 9, fill: 'var(--trading-muted)' }} tickLine={false} axisLine={false} width={42} />
                        <ZAxis dataKey="article_count" range={[48, 180]} />
                        <Tooltip content={<ChartTooltip />} cursor={{ stroke: 'var(--trading-muted)', strokeDasharray: '3 3' }} />
                        <ReferenceLine yAxisId="sentiment" y={0} stroke="var(--trading-muted)" strokeDasharray="4 3" />
                        <Line data={timelinePoints} dataKey="avg_sentiment" yAxisId="sentiment" type="monotone" stroke="var(--trading-accent)" strokeWidth={1.5} dot={false} isAnimationActive={false} />
                        <Scatter data={timelinePoints} dataKey="avg_sentiment" yAxisId="sentiment" zAxisId={0} name="Daily sentiment">
                          {timelinePoints.map((point, index) => <Cell key={`${point.publication_date}-${index}`} fill={markerColor(point.news_items)} />)}
                        </Scatter>
                      </ComposedChart>
                    </ResponsiveContainer>
                  )}
                </div>

                <div>
                  <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                    <h4 className="text-xs font-semibold text-text-primary">Forward {metric === 'price' ? 'Price Return' : 'Volume Change'} Scatter Plot</h4>
                    <span className="text-[10px] text-text-muted">Correlation ({lag.toUpperCase()}): {(metric === 'price'
                      ? (lag === 't1' ? data.correlation_summary.sentiment_return_t1 : data.correlation_summary.sentiment_return_t2)
                      : (lag === 't1' ? data.correlation_summary.sentiment_volume_change_t1 : data.correlation_summary.sentiment_volume_change_t2)
                    ).coefficient?.toFixed(3) ?? '—'}</span>
                  </div>
                  {points.length === 0 ? <p className="py-8 text-center text-xs text-text-muted">No paired sentiment and forward price data in this range.</p> : (
                    <ResponsiveContainer width="100%" height={260}>
                      <ComposedChart data={points} margin={{ top: 8, right: 12, bottom: 18, left: 8 }}>
                        <CartesianGrid stroke="var(--trading-grid)" strokeOpacity={0.55} />
                        <XAxis type="number" dataKey="avg_sentiment" domain={[-1, 1]} tick={{ fontSize: 10, fill: 'var(--trading-muted)' }} tickLine={false} axisLine={false} label={{ value: 'Daily news sentiment', position: 'insideBottom', offset: -12, fill: 'var(--trading-muted)', fontSize: 10 }} />
                        <YAxis type="number" dataKey="forward_value_pct" name={`Forward ${metric === 'price' ? 'price return' : 'volume change'} ${lag.toUpperCase()}`} tick={{ fontSize: 10, fill: 'var(--trading-muted)' }} tickLine={false} axisLine={false} width={64} tickFormatter={(value: number) => `${value}%`} />
                        <ReferenceLine x={0} stroke="var(--trading-muted)" strokeDasharray="4 3" />
                        <Tooltip content={<ChartTooltip />} cursor={{ strokeDasharray: '3 3' }} />
                        {trendLine.length === 2 && <Line data={trendLine} dataKey="forward_value_pct" type="linear" stroke="var(--trading-accent)" strokeWidth={2} dot={false} isAnimationActive={false} />}
                        <Scatter data={points} dataKey="forward_value_pct" name={`Forward ${metric} ${lag.toUpperCase()}`}>
                          {points.map((point, index) => <Cell key={`${point.date}-${index}`} fill={markerColor(point.news_items)} />)}
                        </Scatter>
                      </ComposedChart>
                    </ResponsiveContainer>
                  )}
                </div>

                <div className="grid grid-cols-3 gap-2 text-center text-[10px]">
                  <div className="bg-bg-elevated p-2 text-text-muted">News dates <span className="block pt-1 font-mono text-text-primary">{data.daily_data.length}</span></div>
                  <div className="bg-bg-elevated p-2 text-text-muted">Scored days <span className="block pt-1 font-mono text-text-primary">{data.correlation_summary.observations}</span></div>
                  <div className="bg-bg-elevated p-2 text-text-muted">Paired {lag.toUpperCase()} {metric} moves <span className="block pt-1 font-mono text-text-primary">{points.length}</span></div>
                </div>

                <div className="max-h-80 overflow-auto">
                  <table className="w-full min-w-[760px] text-xs">
                    <thead className="sticky top-0 bg-bg-card"><tr className="border-b border-bg-border text-left text-text-muted">
                      <th className="py-2 pr-3 font-medium">Date</th><th className="py-2 pr-3 font-medium">Headline</th><th className="py-2 pr-3 font-medium">Category</th><th className="py-2 pr-3 text-right font-medium">Sentiment</th><th className="py-2 pr-3 text-right font-medium">Return T+1</th><th className="py-2 text-right font-medium">Return T+2</th>
                    </tr></thead>
                    <tbody>{data.daily_data.flatMap(day => day.news_items.map((item, index) => (
                      <tr key={`${day.date}-${index}`} className="border-b border-bg-border/60 last:border-0">
                        <td className="py-2 pr-3 font-mono text-text-muted">{day.date}</td>
                        <td className="max-w-sm truncate py-2 pr-3 text-text-primary" title={item.headline}>{item.headline || '—'}</td>
                        <td className="py-2 pr-3" style={{ color: categoryColor(item.category) }}>{item.category}</td>
                        <td className="py-2 pr-3 text-right font-mono">{item.sentiment_score === null ? '—' : item.sentiment_score.toFixed(3)}</td>
                        <td className="py-2 pr-3 text-right font-mono">{formatPercent(day.return_t1_pct)}</td>
                        <td className="py-2 text-right font-mono">{formatPercent(day.return_t2_pct)}</td>
                      </tr>
                    )))}</tbody>
                  </table>
                </div>
                <CorrelationSummaryTable summary={data.correlation_summary} />
                <p className="border-t border-bg-border pt-3 text-xs text-text-muted">{data.disclaimer}</p>
              </>
            )}
    </section>
  );
}
