import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ChevronDown, ChevronsUpDown, ChevronUp } from 'lucide-react';
import clsx from 'clsx';
import CompanyLogo from '../companies/CompanyLogo';
import { formatPrice, formatTradeDate } from './format';
import type { QuarterlyReportRow } from '../../api/quarterlyReports';

// Sortable table for Market -> Quarterly Report.  Values arrive calculated (null = not
// meaningful); this component only sorts and formats.  n/m rows always sort to the bottom.

type SortKey =
  | 'symbol' | 'ltp' | 'eps' | 'bv' | 'pe' | 'pb' | 'dpps' | 'dpps_yield' | 'avg_dpps' | 'avg_yield' | 'yoy';

interface Column {
  key: Exclude<SortKey, 'symbol'>;
  label: string;
  title?: string;
  kind: 'price' | 'pct' | 'ratio';
}

const NM = 'n/m';

function columns(avgWindow: number): Column[] {
  return [
    { key: 'ltp', label: 'LTP', title: 'Latest crawled close', kind: 'price' },
    { key: 'eps', label: 'EPS', title: 'Annualized earnings per share', kind: 'price' },
    { key: 'bv', label: 'BV', title: 'Book value (net worth) per share', kind: 'price' },
    { key: 'pe', label: 'PE', title: 'LTP ÷ EPS; n/m when EPS ≤ 0', kind: 'ratio' },
    { key: 'pb', label: 'PB', title: 'LTP ÷ BV; n/m when BV ≤ 0', kind: 'ratio' },
    { key: 'dpps', label: 'DPPS', title: 'Distributable profit per share', kind: 'price' },
    { key: 'dpps_yield', label: 'DPPS Yield', title: 'DPPS ÷ LTP', kind: 'pct' },
    { key: 'avg_dpps', label: `${avgWindow}Y Avg`, title: `Average yearly DPPS over the last ${avgWindow} fiscal years on file`, kind: 'price' },
    { key: 'avg_yield', label: `${avgWindow}Y Avg Yield`, title: `${avgWindow}Y average DPPS ÷ LTP`, kind: 'pct' },
    { key: 'yoy', label: 'YoY', title: 'EPS vs the same quarter last year; n/m when last year is missing or ≤ 0', kind: 'pct' },
  ];
}

function format(value: number | null, kind: Column['kind']) {
  if (value === null) return <span className="text-text-muted">{NM}</span>;
  if (kind === 'pct') return `${value.toFixed(2)}%`;
  if (kind === 'ratio') return value.toFixed(2);
  return formatPrice(value);
}

interface Props {
  rows: QuarterlyReportRow[];
  avgWindow: number;
  dimmed?: boolean;
}

export default function QuarterlyReportTable({ rows, avgWindow, dimmed }: Props) {
  const [sort, setSort] = useState<{ key: SortKey; desc: boolean }>({ key: 'symbol', desc: false });
  const cols = useMemo(() => columns(avgWindow), [avgWindow]);

  const sorted = useMemo(() => {
    const factor = sort.desc ? -1 : 1;
    return [...rows].sort((a, b) => {
      if (sort.key === 'symbol') return a.symbol.localeCompare(b.symbol) * factor;
      const left = a[sort.key];
      const right = b[sort.key];
      if (left === null && right === null) return a.symbol.localeCompare(b.symbol);
      if (left === null) return 1;
      if (right === null) return -1;
      return (left - right) * factor;
    });
  }, [rows, sort]);

  // Text starts ascending, numbers descending; the next click flips the direction.
  const toggle = (key: SortKey) =>
    setSort((current) => (current.key === key ? { key, desc: !current.desc } : { key, desc: key !== 'symbol' }));

  const header = (key: SortKey, label: string, title: string | undefined, align: string) => {
    const active = sort.key === key;
    const Icon = !active ? ChevronsUpDown : sort.desc ? ChevronDown : ChevronUp;
    return (
      <th key={key} title={title} aria-sort={active ? (sort.desc ? 'descending' : 'ascending') : 'none'}
        className={`sticky top-0 z-10 whitespace-nowrap bg-bg-card px-2 py-2.5 font-semibold first:pl-4 last:pr-4 ${align}`}>
        <button type="button" onClick={() => toggle(key)}
          className={`inline-flex items-center gap-0.5 uppercase hover:text-text-primary ${active ? 'text-text-primary' : ''}`}>
          {label}<Icon size={11} className={active ? '' : 'opacity-50'} />
        </button>
      </th>
    );
  };

  return (
    <div className={clsx('max-h-[70vh] overflow-auto transition-opacity', dimmed && 'opacity-60')}>
      <table className="w-full min-w-[1080px] text-xs tabular-nums">
        <thead>
          <tr className="border-b border-bg-border text-[11px] uppercase text-text-secondary">
            {header('symbol', 'Company', undefined, 'text-left')}
            {cols.map((column) => header(column.key, column.label, column.title, 'text-right'))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => (
            <tr key={row.symbol} className="border-b border-bg-border last:border-0 hover:bg-blue-500/10">
              <td className="py-2.5 pl-4 pr-2">
                <Link to={`/companies/${row.symbol}`} className="group flex min-w-0 items-center gap-2.5">
                  <CompanyLogo symbol={row.symbol} name={row.name} logoUrl={row.logo_url} size="sm" />
                  <span className="min-w-0">
                    <span className="block font-semibold text-text-primary group-hover:underline">{row.symbol}</span>
                    <span className="block max-w-[220px] truncate text-[11px] text-text-muted" title={row.name}>{row.name}</span>
                  </span>
                </Link>
              </td>
              {cols.map((column) => {
                const value = row[column.key];
                const cell = format(value, column.kind);
                if (column.key === 'ltp') {
                  return (
                    <td key={column.key} className="px-2 text-right font-mono"
                      title={row.price_date ? `Close of ${formatTradeDate(row.price_date)}` : undefined}>{cell}</td>
                  );
                }
                if (column.key === 'avg_dpps') {
                  const partial = value !== null && row.avg_years_used < avgWindow;
                  return (
                    <td key={column.key} className="px-2 text-right font-mono">
                      {cell}
                      {partial && <span className="ml-1 text-[10px] text-text-muted" title={`Only ${row.avg_years_used} years on file`}>({row.avg_years_used}y)</span>}
                    </td>
                  );
                }
                if (column.key === 'yoy') {
                  return (
                    <td key={column.key}
                      className={clsx('px-2 pr-4 text-right font-mono font-semibold', value !== null && value > 0 && 'text-up', value !== null && value < 0 && 'text-down')}
                      title={row.previous_eps !== null ? `Same quarter last year: EPS ${formatPrice(row.previous_eps)}` : undefined}>
                      {value !== null && value > 0 ? '+' : ''}{cell}
                    </td>
                  );
                }
                return <td key={column.key} className="px-2 text-right font-mono">{cell}</td>;
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
