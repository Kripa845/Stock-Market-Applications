import type { OverallSignal, TechnicalAnalysis, TechnicalSignal } from '../../api/market';
import { formatPrice, formatTradeDate } from './format';

// Technical view of the Market Overview card: overall signal, buy/neutral/sell bar,
// indicator table and classic pivot points. Values come from /api/market/overview/technical/.

const SIGNAL_TONE: Record<TechnicalSignal, string> = {
  Buy: 'text-up',
  Sell: 'text-down',
  Neutral: 'text-sky-400',
};

const OVERALL_TONE: Record<OverallSignal, string> = {
  'Strong Buy': 'bg-up text-white',
  Buy: 'bg-up/15 text-up',
  Neutral: 'bg-sky-400/15 text-sky-400',
  Sell: 'bg-down/15 text-down',
  'Strong Sell': 'bg-down text-white',
};

const PIVOT_ORDER = ['s3', 's2', 's1', 'p', 'r1', 'r2', 'r3'] as const;

const fmt = (value: number | string | null | undefined) => (value == null ? '—' : formatPrice(value));

function detail(values: Record<string, number | null>) {
  const entries = Object.entries(values);
  if (!entries.length) return null;
  return entries.map(([key, value]) => `${key} ${fmt(value)}`).join(' · ');
}

export default function TechnicalSummaryView({ data }: { data: TechnicalAnalysis }) {
  const { summary } = data;
  const share = (count: number) => (summary.total ? `${(count / summary.total) * 100}%` : '0%');

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[11px] uppercase tracking-wide text-text-muted">Summary · {formatTradeDate(data.as_of)}</p>
          <p className="text-[11px] text-text-muted">{data.sessions_used} daily sessions</p>
        </div>
        <span className={`rounded-md px-3 py-1.5 text-sm font-semibold ${summary.signal ? OVERALL_TONE[summary.signal] : 'bg-bg-elevated text-text-muted'}`}>
          {summary.signal ?? 'Not enough history'}
        </span>
      </div>

      <div>
        <div className="flex h-2 overflow-hidden rounded-full bg-bg-elevated" role="img"
          aria-label={`${summary.buy} buy, ${summary.neutral} neutral, ${summary.sell} sell`}>
          <div className="bg-up" style={{ width: share(summary.buy) }} />
          <div className="bg-sky-400" style={{ width: share(summary.neutral) }} />
          <div className="bg-down" style={{ width: share(summary.sell) }} />
        </div>
        <div className="mt-1.5 flex justify-between text-[11px]">
          <span className="text-up">Buy {summary.buy}</span>
          <span className="text-sky-400">Neutral {summary.neutral}</span>
          <span className="text-down">Sell {summary.sell}</span>
        </div>
      </div>

      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-bg-border text-[10px] uppercase tracking-wide text-text-muted">
            <th className="py-2 text-left font-medium">Indicator</th>
            <th className="py-2 text-right font-medium">Value</th>
            <th className="py-2 text-right font-medium">Signal</th>
          </tr>
        </thead>
        <tbody>
          {data.indicators.map((item) => (
            <tr key={item.key} className="border-b border-bg-border last:border-0" title={detail(item.values) ?? undefined}>
              <td className="py-2 text-text-primary">{item.name}</td>
              <td className="py-2 text-right font-mono text-text-secondary">{fmt(item.value)}</td>
              <td className={`py-2 text-right font-semibold ${item.signal ? SIGNAL_TONE[item.signal] : 'text-text-muted'}`}>
                {item.signal ?? '—'}
                {!item.votes && item.signal && <span className="ml-1 text-[10px] font-normal text-text-muted">(volatility)</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      {data.pivots && (
        <div>
          <p className="mb-1.5 text-[11px] uppercase tracking-wide text-text-muted">
            Pivot points (classic) · from {formatTradeDate(data.pivots.based_on)}
          </p>
          <div className="grid grid-cols-7 overflow-hidden rounded-lg border border-bg-border text-center text-[11px]">
            {PIVOT_ORDER.map((key) => (
              <div key={key} className="border-r border-bg-border px-1 py-1.5 last:border-0">
                <p className={`font-semibold uppercase ${key === 'p' ? 'text-accent-light' : key.startsWith('r') ? 'text-down' : 'text-up'}`}>{key}</p>
                <p className="mt-0.5 font-mono text-text-primary">{fmt(data.pivots!.levels[key])}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      <p className="text-[10px] leading-relaxed text-text-muted">
        {data.adjusted_sessions.length > 0 && `Prices before ${data.adjusted_sessions.length} corporate-action session(s) are adjusted. `}
        {data.corporate_action_cutoff && `History starts ${formatTradeDate(data.corporate_action_cutoff)} (unexplained price jump). `}
        {data.disclaimer}
      </p>
    </div>
  );
}
