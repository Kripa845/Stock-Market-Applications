import { Link } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';
import type { TopBrokerRow } from '../../api/analysis';
import CompanyLogo from '../companies/CompanyLogo';
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
            <th className={`${th} text-left`}>Top Stock</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => {
            const listed = row.top_stocks?.length ?? 0;
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
              <td className="px-2 py-2">
                {row.top_stock ? (
                  <Link to={`/companies/${row.top_stock.symbol}`} className="flex items-center gap-2 hover:text-accent-light">
                    <CompanyLogo symbol={row.top_stock.symbol} logoUrl={row.top_stock.logo_url} size="sm" />
                    <span className="min-w-0">
                      <span className="block font-semibold text-text-primary">{row.top_stock.symbol}</span>
                      <span className="block whitespace-nowrap font-mono text-[10px] text-text-muted">
                        <span className="text-up">B {formatNprArab(row.top_stock.buy_amount)}</span>
                        {' · '}
                        <span className="text-down">S {formatNprArab(row.top_stock.sell_amount)}</span>
                        {' · '}T {formatNprArab(row.top_stock.turnover)}
                      </span>
                    </span>
                  </Link>
                ) : <span className="text-text-muted">—</span>}
                {listed > 1 && (
                  <Link
                    to={stocksLink}
                    title={`${row.name}: top ${listed} of ${row.stock_count} stocks`}
                    className="mt-1 inline-flex items-center gap-0.5 rounded px-1 py-0.5 text-[10px] font-medium text-accent-light hover:bg-blue-500/10"
                  >
                    Top {listed} stocks <ChevronRight size={11} />
                  </Link>
                )}
              </td>
            </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
