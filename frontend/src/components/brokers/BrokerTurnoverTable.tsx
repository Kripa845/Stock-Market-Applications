import { Link } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';
import type { TopBrokerRow } from '../../api/analysis';
import { formatCount, formatNprArab } from '../market/format';
import BrokerBadge from './BrokerBadge';
import { RankBadge } from './TopBrokers';

/** Green (buy) vs red (sell) split of one broker's turnover. */
export function BuySellBar({ buy, sell }: { buy: number; sell: number }) {
  const total = buy + sell;
  const buyPct = total > 0 ? (buy / total) * 100 : 50;
  return (
    <div title={`Buy ${buyPct.toFixed(0)}% · Sell ${(100 - buyPct).toFixed(0)}%`}>
      <div className="flex h-1.5 overflow-hidden rounded-full bg-bg-border">
        <div className="bg-up" style={{ width: `${buyPct}%` }} />
        <div className="flex-1 bg-down" />
      </div>
      <p className="mt-0.5 flex justify-between text-[10px] text-text-muted">
        <span>B {buyPct.toFixed(0)}%</span>
        <span>S {(100 - buyPct).toFixed(0)}%</span>
      </p>
    </div>
  );
}

const th = 'px-2 py-2 font-medium';

/** Tiny overlapping logo for the top-stocks button (logo, or the symbol's first letter). */
function StockDot({ symbol, logoUrl }: { symbol: string; logoUrl: string | null }) {
  return logoUrl ? (
    <img src={logoUrl} alt="" className="h-6 w-6 shrink-0 rounded-full bg-white object-contain p-0.5 ring-2 ring-bg-card" />
  ) : (
    <span aria-hidden="true" className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent/25 text-[9px] font-bold text-accent-light ring-2 ring-bg-card">
      {symbol.charAt(0)}
    </span>
  );
}

/** One button per broker that opens its top-stocks page: top 3 logos + symbols, and how many there are. */
function TopStocksButton({ row, to }: { row: TopBrokerRow; to: string }) {
  const stocks = row.top_stocks ?? [];
  if (stocks.length === 0) return <span className="text-text-muted">—</span>;
  const preview = stocks.slice(0, 3);
  const more = stocks.length - preview.length;
  return (
    <Link
      to={to}
      title={`${row.name}: top ${stocks.length} of ${row.stock_count} stocks traded`}
      className="group/top inline-flex w-full max-w-[240px] items-center gap-2.5 rounded-lg border border-bg-border px-2.5 py-1.5 transition-colors hover:border-accent/60 hover:bg-accent/10"
    >
      <span className="flex shrink-0 -space-x-2">
        {preview.map((stock) => <StockDot key={stock.symbol} symbol={stock.symbol} logoUrl={stock.logo_url} />)}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block text-[11px] font-semibold text-text-primary group-hover/top:text-accent-light">
          Top {stocks.length} stock{stocks.length > 1 ? 's' : ''}
        </span>
        <span className="block truncate font-mono text-[10px] text-text-muted">
          {preview.map((stock) => stock.symbol).join(' · ')}{more > 0 ? ` +${more}` : ''}
        </span>
      </span>
      <ChevronRight size={14} className="shrink-0 text-text-muted transition-transform group-hover/top:translate-x-0.5 group-hover/top:text-accent-light" />
    </Link>
  );
}

/**
 * `ranks` keeps each broker's overall rank when `rows` is a filtered subset.
 * `day` opens each broker's Broker Explorer detail page on that same day.
 */
export default function BrokerTurnoverTable({ rows, ranks, day }: { rows: TopBrokerRow[]; ranks?: Map<string, number>; day?: string }) {
  const range = day ? `?start_date=${day}&end_date=${day}` : '';
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[960px] text-xs">
        <thead className="border-b border-bg-border text-text-muted">
          <tr>
            <th className={`${th} text-left`}>#</th>
            <th className={`${th} text-left`}>Broker</th>
            <th className={`${th} text-right text-up`}>Buy Amt</th>
            <th className={`${th} text-right text-up`}>Buy Vol</th>
            <th className={`${th} text-right text-down`}>Sell Amt</th>
            <th className={`${th} text-right text-down`}>Sell Vol</th>
            <th className={`${th} w-40 text-right`}>Turnover</th>
            <th className={`${th} text-left`}>Top Stocks</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => {
            const detailLink = `/broker-analysis/${encodeURIComponent(row.broker)}${range}`;
            const stocksLink = `/top-brokers/${encodeURIComponent(row.broker)}${day ? `?date=${day}` : ''}`;
            return (
            <tr key={row.broker} className="table-row">
              <td className="px-2 py-2"><RankBadge rank={ranks?.get(row.broker) ?? index + 1} /></td>
              <td className="max-w-[220px] px-2 py-2">
                <Link to={detailLink} title="Open in Broker Explorer" className="flex min-w-0 hover:text-accent-light">
                  <BrokerBadge brokerCode={row.broker_code} name={row.name} shortName={row.short_name} logoUrl={row.logo_url} />
                </Link>
              </td>
              <td className="px-2 py-2 text-right font-mono tabular-nums text-up">{formatNprArab(row.buy_value)}</td>
              <td className="px-2 py-2 text-right font-mono tabular-nums">{formatCount(row.buy_quantity)}</td>
              <td className="px-2 py-2 text-right font-mono tabular-nums text-down">{formatNprArab(row.sell_value)}</td>
              <td className="px-2 py-2 text-right font-mono tabular-nums">{formatCount(row.sell_quantity)}</td>
              <td className="px-2 py-2">
                <p className="text-right font-mono font-semibold tabular-nums text-text-primary">{formatNprArab(row.total_value)}</p>
                <BuySellBar buy={Number(row.buy_value)} sell={Number(row.sell_value)} />
              </td>
              <td className="px-2 py-2"><TopStocksButton row={row} to={stocksLink} /></td>
            </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
