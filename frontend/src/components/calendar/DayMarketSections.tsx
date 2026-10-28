import { useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import clsx from 'clsx';
import type { MarketDay, MarketDayBroker, MarketDayRow } from '../../api/marketCalendar';
import CompanyLogo from '../companies/CompanyLogo';
import { changeTone, formatCount, formatNprCompact, formatPct, formatPrice, formatTradeDate } from '../market/format';
import { PanelCard } from './PanelCard';

// The clicked session for the tracked companies (backend market_calendar/services/market_day.py):
// a summary card, then one tabbed card for gainers / losers / volume / trades / brokers.

type Tab = 'gainers' | 'losers' | 'volume' | 'trades' | 'brokers';
const TAB_LABEL: Record<Tab, string> = { gainers: 'Gainers', losers: 'Losers', volume: 'Volume', trades: 'Trades', brokers: 'Brokers' };

const num = (value: number | string | null | undefined) => (value === null || value === undefined || value === '' ? 0 : Math.abs(Number(value)));
const toneText = (value: number | string | null) => {
  const tone = changeTone(value);
  return tone === 'up' ? 'text-up' : tone === 'down' ? 'text-down' : 'text-text-secondary';
};

function Empty({ children }: { children: ReactNode }) {
  return <p className="px-3 py-6 text-center text-xs text-text-muted">{children}</p>;
}

/** A ranked row with a background bar sized against the list's largest value. */
function RankedRow({ rank, share, barClass, children }: { rank: number; share: number; barClass: string; children: ReactNode }) {
  return (
    <li className="relative flex items-center gap-2.5 border-t border-bg-border px-3 py-2 first:border-t-0">
      <span aria-hidden className={clsx('absolute inset-y-1 left-0 rounded-r', barClass)} style={{ width: `${Math.max(share, 0.04) * 100}%` }} />
      <span className="relative w-4 text-right font-mono text-[11px] text-text-muted">{rank}</span>
      <div className="relative flex min-w-0 flex-1 items-center gap-2.5">{children}</div>
    </li>
  );
}

function CompanyRows({ rows, metric, barClass, value }: {
  rows: MarketDayRow[];
  metric: (row: MarketDayRow) => number;
  barClass: string;
  value: (row: MarketDayRow) => ReactNode;
}) {
  const max = Math.max(...rows.map(metric), 0) || 1;
  return (
    <ol>
      {rows.map((row, i) => (
        <RankedRow key={row.symbol} rank={i + 1} share={metric(row) / max} barClass={barClass}>
          <CompanyLogo symbol={row.symbol} name={row.name} logoUrl={row.logo_url} size="sm" />
          <div className="min-w-0 flex-1">
            <Link to={`/companies/${row.symbol}`} className="text-sm font-semibold text-text-primary hover:text-accent-light">{row.symbol}</Link>
            <p className="truncate text-[11px] text-text-muted">{row.name}</p>
          </div>
          <div className="shrink-0 text-right font-mono text-xs">{value(row)}</div>
        </RankedRow>
      ))}
    </ol>
  );
}

function BrokerRows({ rows }: { rows: MarketDayBroker[] }) {
  const max = Math.max(...rows.map((row) => num(row.total_value)), 0) || 1;
  return (
    <ol>
      {rows.map((row, i) => (
        <RankedRow key={row.broker} rank={i + 1} share={num(row.total_value) / max} barClass="bg-accent/10">
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-accent/20 font-mono text-[11px] font-bold text-accent-light">
            {row.broker}
          </span>
          <div className="min-w-0 flex-1">
            <Link to={`/broker-analysis/${row.broker}`} className="block truncate text-sm font-semibold text-text-primary hover:text-accent-light">
              {row.name}
            </Link>
            <p className="font-mono text-[11px] text-text-muted">Buy {formatNprCompact(row.buy_value)} · Sell {formatNprCompact(row.sell_value)}</p>
          </div>
          <div className="shrink-0 text-right font-mono text-xs">
            <p className="text-text-primary">{formatNprCompact(row.total_value)}</p>
            <p className={toneText(row.net_value)}>Net {formatNprCompact(row.net_value)}</p>
          </div>
        </RankedRow>
      ))}
    </ol>
  );
}

const priceAndChange = (row: MarketDayRow) => (
  <>
    <p className="text-text-primary">{formatPrice(row.close)}</p>
    <p className={toneText(row.change_pct)}>{formatPct(row.change_pct)}</p>
  </>
);

function Stat({ label, value, className }: { label: string; value: ReactNode; className?: string }) {
  return (
    <div className="min-w-0">
      <p className="text-[11px] text-text-muted">{label}</p>
      <p className={clsx('truncate font-mono text-sm font-semibold', className ?? 'text-text-primary')}>{value}</p>
    </div>
  );
}

export default function DayMarketSections({ market }: { market: MarketDay }) {
  // Kept while stepping through days (the panel keeps this component mounted).
  const [tab, setTab] = useState<Tab>('gainers');

  if (!market.available) {
    return (
      <PanelCard title="Tracked companies">
        <Empty>No crawled prices for this day, so there are no gainers, losers or brokers to show.</Empty>
      </PanelCard>
    );
  }

  const { summary } = market;
  const ranked = summary.advanced + summary.declined + summary.unchanged;
  const width = (n: number) => `${ranked ? (n / ranked) * 100 : 0}%`;
  const tabs: Tab[] = ['gainers', 'losers', 'volume', 'trades', ...(market.brokers !== undefined ? ['brokers' as const] : [])];
  const active = tabs.includes(tab) ? tab : 'gainers';

  return (
    <>
      <PanelCard
        title="Tracked companies"
        aside={summary.previous_trade_date && <>vs {formatTradeDate(summary.previous_trade_date)}</>}
      >
        <div className="space-y-3 p-3">
          <div className="flex items-end justify-between gap-3 text-xs">
            <span className="text-up"><b className="font-mono text-lg">{summary.advanced}</b> up</span>
            <span className="text-text-secondary"><b className="font-mono text-lg">{summary.unchanged}</b> flat</span>
            <span className="text-down"><b className="font-mono text-lg">{summary.declined}</b> down</span>
          </div>
          <div className="flex h-2 gap-0.5 overflow-hidden rounded-full" aria-label={`${summary.advanced} up, ${summary.unchanged} unchanged, ${summary.declined} down`}>
            {summary.advanced > 0 && <span className="rounded-full bg-up" style={{ width: width(summary.advanced) }} />}
            {summary.unchanged > 0 && <span className="rounded-full bg-text-muted" style={{ width: width(summary.unchanged) }} />}
            {summary.declined > 0 && <span className="rounded-full bg-down" style={{ width: width(summary.declined) }} />}
          </div>
          <div className="grid grid-cols-3 gap-3 border-t border-bg-border pt-3">
            <Stat label="Turnover" value={formatNprCompact(summary.total_turnover)} />
            <Stat label="Volume" value={formatCount(summary.total_traded_shares)} />
            <Stat label="Trades" value={summary.transactions_reported ? formatCount(summary.total_transactions) : '—'} />
          </div>
          {summary.warning && <p className="text-[11px] text-yellow-400">{summary.warning}</p>}
        </div>
      </PanelCard>

      <PanelCard
        title={
          <div role="tablist" aria-label="Top lists" className="-mx-1 flex gap-1 overflow-x-auto">
            {tabs.map((key) => (
              <button
                key={key}
                type="button"
                role="tab"
                aria-selected={active === key}
                onClick={() => setTab(key)}
                className={clsx(
                  'whitespace-nowrap rounded-md px-2.5 py-1 text-xs font-medium normal-case tracking-normal transition',
                  active === key ? 'bg-accent text-white' : 'text-text-secondary hover:bg-bg-elevated hover:text-text-primary',
                )}
              >
                {TAB_LABEL[key]}
              </button>
            ))}
          </div>
        }
      >
        <div role="tabpanel">
          {active === 'gainers' && (market.gainers.length
            ? <CompanyRows rows={market.gainers} metric={(r) => num(r.change_pct)} barClass="bg-up/10" value={priceAndChange} />
            : <Empty>No tracked company gained.</Empty>)}
          {active === 'losers' && (market.losers.length
            ? <CompanyRows rows={market.losers} metric={(r) => num(r.change_pct)} barClass="bg-down/10" value={priceAndChange} />
            : <Empty>No tracked company lost.</Empty>)}
          {active === 'volume' && (
            <CompanyRows
              rows={market.top_volume}
              metric={(r) => num(r.volume)}
              barClass="bg-accent/10"
              value={(row) => (
                <>
                  <p className="text-text-primary">{formatCount(row.volume)}</p>
                  <p className="text-text-muted">{formatNprCompact(row.turnover)}</p>
                </>
              )}
            />
          )}
          {active === 'trades' && (market.top_transactions.length
            ? <CompanyRows rows={market.top_transactions} metric={(r) => num(r.transactions)} barClass="bg-accent/10" value={(row) => <p className="text-text-primary">{formatCount(row.transactions)}</p>} />
            : <Empty>Trade counts aren't available for this day yet. They come from a complete floorsheet or NEPSE's day summary.</Empty>)}
          {active === 'brokers' && (market.brokers
            ? <BrokerRows rows={market.brokers.rows} />
            : <Empty>No floorsheet stored for this day{market.floorsheet_from && <> (broker data starts {formatTradeDate(market.floorsheet_from)})</>}.</Empty>)}
        </div>
        {active === 'brokers' && market.brokers && (
          <p className="border-t border-bg-border px-3 py-2 text-[11px] text-text-muted">
            Ranked by buy + sell turnover · {formatCount(market.brokers.transaction_count)} trades, {market.brokers.broker_count} brokers
          </p>
        )}
      </PanelCard>
    </>
  );
}
