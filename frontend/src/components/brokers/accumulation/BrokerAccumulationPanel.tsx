import { useState } from 'react';
import { AlertTriangle, Info, Loader2, RefreshCw } from 'lucide-react';
import type { AccumulationRange, TopBroker } from '../../../api/brokerAccumulation';
import { useBrokerAccumulation } from '../../../hooks/useBrokerAccumulation';
import { formatCount, formatPct, formatPrice, formatTradeDate } from '../../market/format';
import BrokerBadge from '../BrokerBadge';
import BrokerAccumulationTable from './BrokerAccumulationTable';
import FlowOverlayChart from './FlowOverlayChart';
import RangeSelector from './RangeSelector';
import SignalBadge from './SignalBadge';
import TopBrokersChart from './TopBrokersChart';

// Broker accumulation / distribution for one stock: the signal, who is behind it, the daily
// flow against price and every broker's position.  All figures come from the API
// (apps/analysis/services/broker_accumulation.py); this only lays them out.

const tone = (value: number | null) => (value === null || value === 0 ? 'text-text-muted' : value > 0 ? 'text-up' : 'text-down');

function Stat({ label, value, className = 'text-text-primary', sub }: { label: string; value: string; className?: string; sub?: string }) {
  return (
    <div className="card-elevated">
      <p className="text-[10px] uppercase tracking-widest text-text-muted">{label}</p>
      <p className={`mt-1 font-mono text-lg font-semibold tabular-nums ${className}`}>{value}</p>
      {sub && <p className="text-[11px] text-text-muted">{sub}</p>}
    </div>
  );
}

function TopList({ title, brokers, side }: { title: string; brokers: TopBroker[]; side: 'buy' | 'sell' }) {
  return (
    <div className="card space-y-2">
      <p className={`text-xs font-semibold ${side === 'buy' ? 'text-up' : 'text-down'}`}>{title}</p>
      {brokers.length === 0 ? (
        <p className="py-3 text-center text-xs text-text-muted">None in this range.</p>
      ) : (
        <ul className="divide-y divide-bg-border">
          {brokers.map((broker) => {
            const average = side === 'buy' ? broker.avg_buy : broker.avg_sell;
            const vsClose = side === 'buy' ? broker.close_vs_avg_buy_pct : broker.close_vs_avg_sell_pct;
            const streak = broker.streak.direction === (side === 'buy' ? 'buying' : 'selling') ? broker.streak.days : 0;
            return (
              <li key={broker.broker} className="flex items-center justify-between gap-3 py-2">
                <BrokerBadge brokerCode={broker.broker} name={broker.name} shortName={broker.short_name} logoUrl={broker.logo_url} />
                <div className="text-right text-xs leading-tight">
                  <p className={`font-mono font-semibold tabular-nums ${tone(broker.net_qty)}`}>
                    {broker.net_qty > 0 ? '+' : ''}{formatCount(broker.net_qty)}
                  </p>
                  <p className="text-text-muted">
                    avg {side} <span className="font-mono text-text-secondary">{formatPrice(average)}</span>
                    {vsClose !== null && <span className={`ml-1 font-mono ${tone(vsClose)}`}>({formatPct(vsClose)} vs close)</span>}
                  </p>
                  {streak > 1 && <p className="text-text-muted">{streak} sessions {side === 'buy' ? 'buying' : 'selling'} in a row</p>}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

export default function BrokerAccumulationPanel({ symbol }: { symbol: string }) {
  const [range, setRange] = useState<AccumulationRange>({ window: '1w' });
  const [excludeSelfTrades, setExcludeSelfTrades] = useState(false);
  const { data, loading, error, reload } = useBrokerAccumulation({ symbol, range, excludeSelfTrades });
  const signal = data?.signal;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          {signal && <SignalBadge signal={signal.signal} ratio={signal.ratio} />}
          {signal?.window.start_date && (
            <span className="text-xs text-text-muted">
              {formatTradeDate(signal.window.start_date)} → {formatTradeDate(signal.window.end_date)}
              {' · '}{signal.window.sessions} session{signal.window.sessions === 1 ? '' : 's'}
            </span>
          )}
          {loading && data && <Loader2 size={14} className="animate-spin text-text-muted" />}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <label className="flex cursor-pointer items-center gap-1.5 text-xs text-text-secondary" title="Drop trades where the buyer and seller broker are the same (possible wash trades)">
            <input type="checkbox" checked={excludeSelfTrades} onChange={(event) => setExcludeSelfTrades(event.target.checked)} className="accent-accent" />
            Exclude self-trades
          </label>
          <RangeSelector value={range} onChange={setRange} />
        </div>
      </div>

      {error ? (
        <div className="card flex flex-col items-center gap-3 py-10 text-center">
          <AlertTriangle size={24} className="text-down" />
          <p className="text-sm text-text-secondary">{error}</p>
          <button type="button" onClick={reload} className="btn-ghost flex items-center gap-1.5 text-xs"><RefreshCw size={12} />Retry</button>
        </div>
      ) : !data ? (
        <div className="flex items-center justify-center py-12"><Loader2 className="animate-spin text-accent" size={24} /></div>
      ) : data.signal.signal === 'no_data' ? (
        <div className="card py-10 text-center text-sm text-text-muted">No floorsheet trades for {symbol} in this range.</div>
      ) : (
        <div className={`space-y-4 transition-opacity ${loading ? 'opacity-60' : ''}`}>
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
            <Stat label="Top-5 net buying" value={`+${formatCount(data.signal.top5_buy_net)}`} className="text-up" />
            <Stat label="Top-5 net selling" value={formatCount(data.signal.top5_sell_net)} className="text-down" />
            <Stat
              label="Latest close"
              value={data.signal.latest_close === null ? '—' : `Rs. ${formatPrice(data.signal.latest_close)}`}
              sub={data.signal.latest_close_date ? formatTradeDate(data.signal.latest_close_date) : undefined}
            />
            <Stat
              label="Volume in range"
              value={formatCount(data.signal.total_qty)}
              sub={`${data.signal.broker_count} brokers · ${formatCount(data.signal.trade_count)} trades`}
            />
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <div className="card">
              <p className="mb-2 text-sm font-semibold text-text-primary">Top accumulators vs distributors</p>
              <TopBrokersChart accumulators={data.signal.accumulators} distributors={data.signal.distributors} />
            </div>
            <div className="card">
              <p className="mb-2 text-sm font-semibold text-text-primary">Daily top-5 net flow vs price</p>
              <FlowOverlayChart points={data.flow.points} />
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <TopList title="Top accumulators (net buying)" brokers={data.signal.accumulators} side="buy" />
            <TopList title="Top distributors (net selling)" brokers={data.signal.distributors} side="sell" />
          </div>

          <div className="card p-0">
            <p className="px-4 pt-4 text-sm font-semibold text-text-primary">All brokers</p>
            <BrokerAccumulationTable rows={data.summary.results} />
          </div>

          {data.flow.warnings.length > 0 && (
            <div className="flex items-start gap-2 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-500">
              <AlertTriangle size={13} className="mt-px shrink-0" />
              <span>Bought and sold quantities differ on {data.flow.warnings.length} session(s), usually trades with a missing broker code: {data.flow.warnings.join('; ')}</span>
            </div>
          )}
          {!excludeSelfTrades && data.signal.self_trade_qty > 0 && (
            <p className="text-[11px] text-text-muted">
              Includes {formatCount(data.signal.self_trade_qty)} shares traded between a broker and itself.
            </p>
          )}
        </div>
      )}

      <div className="flex items-start gap-1.5 rounded-lg border border-bg-border px-3 py-2 text-[11px] text-text-muted">
        <Info size={11} className="mt-0.5 shrink-0" />
        <span>
          Broker data is informational, not financial advice. Signal = top-5 net buying ÷ top-5 net selling
          {signal && ` (above ${signal.thresholds.accumulation}× accumulation, below ${signal.thresholds.distribution}× distribution)`}.
          Windows count floorsheet sessions.
        </span>
      </div>
    </div>
  );
}
