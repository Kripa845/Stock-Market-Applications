import { Link } from 'react-router-dom';
import { ChevronDown, ChevronUp } from 'lucide-react';
import type { AccDistRow, AccDistSide } from '../../../api/accDist';
import { formatNepaliUnits, formatPrice } from '../../market/format';

export type RankOrder = 'asc' | 'desc';

interface AccDistTableProps {
  side: AccDistSide;
  rows: AccDistRow[];
  loading: boolean;
  emptyMessage: string;
  rankOrder: RankOrder;
  onToggleRank: () => void;
}

const SKELETON_ROWS = 12;

/** Float %, with a * when it is of listed rather than public shares. */
function FloatPill({ row, tone }: { row: AccDistRow; tone: string }) {
  if (row.float_qty_pct === null) return <span className="text-text-muted">—</span>;
  const listed = row.float_basis === 'listed';
  return (
    <span
      className={`inline-block rounded-full bg-bg-elevated px-2.5 py-0.5 font-mono text-[12px] font-medium tabular-nums ${tone}`}
      title={listed ? 'Of listed shares: public (free-float) share count not available for this stock' : 'Of public (free-float) shares'}
    >
      {Math.abs(row.float_qty_pct).toFixed(2)} %{listed && '*'}
    </span>
  );
}
const SKELETON_WIDTHS = [56, 64, 32, 56, 56, 56, 24];
const th = 'whitespace-nowrap px-3 py-2.5 font-medium';

export default function AccDistTable({ side, rows, loading, emptyMessage, rankOrder, onToggleRank }: AccDistTableProps) {
  const acc = side === 'accumulation';
  const tone = acc ? 'text-up' : 'text-down';
  const RankIcon = rankOrder === 'asc' ? ChevronUp : ChevronDown;

  return (
    <div className="max-h-[640px] overflow-auto rounded-lg border border-bg-border">
      <table className="w-full min-w-[580px] text-[13px]">
        <thead className="sticky top-0 z-10 bg-bg-card">
          <tr className="border-b border-bg-border text-[11px] uppercase tracking-wider text-text-secondary">
            <th className={`${th} text-left`}>Symbol</th>
            <th className={`${th} text-right`}>Tot Qnt</th>
            <th className={`${th} text-center`}>{acc ? 'Buyer' : 'Seller'}</th>
            <th className={`${th} text-center`}>Float Qnty %</th>
            <th className={`${th} text-right`}>Tot Amt</th>
            <th className={`${th} text-right`}>Avg Rate</th>
            <th className={`${th} text-right`} aria-sort={rankOrder === 'asc' ? 'ascending' : 'descending'}>
              <button
                type="button"
                onClick={onToggleRank}
                className="inline-flex items-center gap-0.5 uppercase tracking-wider text-accent-light hover:text-text-primary"
                title="Toggle rank order"
              >
                Rank<RankIcon size={11} />
              </button>
            </th>
          </tr>
        </thead>

        <tbody>
          {loading ? (
            Array.from({ length: SKELETON_ROWS }, (_, index) => (
              <tr key={index} className="h-12 border-b border-bg-border/60">
                {SKELETON_WIDTHS.map((width, cell) => (
                  <td key={cell} className="px-3">
                    <div
                      className={`h-3 animate-pulse rounded bg-bg-elevated ${cell === 0 ? '' : 'ml-auto'}`}
                      style={{ width }}
                    />
                  </td>
                ))}
              </tr>
            ))
          ) : rows.length === 0 ? (
            <tr>
              <td colSpan={7} className="h-48 text-center text-sm text-text-muted">{emptyMessage}</td>
            </tr>
          ) : (
            rows.map((row) => (
              <tr key={`${row.symbol}:${row.broker}`} className="table-row h-12">
                <td className="px-3 text-left font-semibold text-text-primary">
                  <Link to={`/companies/${row.symbol}`} className="hover:text-accent-light" title={row.sector}>{row.symbol}</Link>
                </td>
                <td className={`px-3 text-right font-mono tabular-nums ${tone}`}>{formatNepaliUnits(row.net_qty)}</td>
                <td className="px-3 text-center font-semibold text-text-primary">{row.broker}</td>
                <td className="px-3 text-center">
                  <FloatPill row={row} tone={tone} />
                </td>
                <td className={`px-3 text-right font-mono font-semibold tabular-nums ${tone}`}>{formatNepaliUnits(row.net_amount)}</td>
                <td className="px-3 text-right font-mono tabular-nums text-text-secondary">{formatPrice(row.avg_rate)}</td>
                <td className="px-3 text-right font-mono tabular-nums text-text-muted">{row.rank}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
