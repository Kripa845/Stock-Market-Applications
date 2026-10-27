import { Navigate, NavLink, useParams, useSearchParams } from 'react-router-dom';
import { AlertTriangle, Info } from 'lucide-react';
import clsx from 'clsx';
import PageHeader from '../components/common/PageHeader';
import QuarterlyReportTable from '../components/market/QuarterlyReportTable';
import { Filter, selectClass } from '../components/market/TopListControls';
import { useQuarterlyReport, useQuarterlyReportPeriods } from '../hooks/useQuarterlyReport';
import { SECTOR_CODES, SECTOR_LABELS, shortFiscalYear, type Quarter, type SectorCode } from '../api/quarterlyReports';

// Latest Report (/market/quarterly-report/:sector?fiscal_year=2082/2083&quarter=4).
// The sector comes from the route; no fiscal year / quarter means the latest one filed.

const isSector = (value: string): value is SectorCode => (SECTOR_CODES as readonly string[]).includes(value);
const toQuarter = (value: string | null): Quarter | undefined =>
  value === '1' || value === '2' || value === '3' || value === '4' ? (Number(value) as Quarter) : undefined;

export default function QuarterlyReportPage() {
  const { sector: slug = '' } = useParams();
  const code = slug.toUpperCase();
  if (!isSector(code)) return <Navigate to="/market/quarterly-report/banking" replace />;
  return <QuarterlyReport sector={code} />;
}

function QuarterlyReport({ sector }: { sector: SectorCode }) {
  const [params, setParams] = useSearchParams();
  const fiscalYear = params.get('fiscal_year') || undefined;
  const quarter = toQuarter(params.get('quarter'));

  const periods = useQuarterlyReportPeriods(sector);
  const report = useQuarterlyReport({ sector, fiscal_year: fiscalYear, quarter });
  const meta = report.data?.meta;
  const rows = report.data?.results ?? [];

  const selectedYear = fiscalYear ?? meta?.fiscal_year ?? '';
  const yearPeriods = periods.data?.periods ?? [];
  const quarters = yearPeriods.find((p) => p.fiscal_year === selectedYear)?.quarters ?? [];

  const update = (changes: Record<string, string | null>) => {
    const next = new URLSearchParams(params);
    Object.entries(changes).forEach(([key, value]) => (value ? next.set(key, value) : next.delete(key)));
    setParams(next, { replace: true });
  };

  const title = `${meta?.sector_name ?? SECTOR_LABELS[sector]} — Latest Quarterly Report`;

  return (
    <div className="space-y-4">
      <PageHeader title={title} subtitle="Latest quarterly filings of your tracked companies, valued at the latest close" />

      <nav aria-label="Sector" className="-mx-1 flex gap-1 overflow-x-auto px-1 pb-1">
        {SECTOR_CODES.map((code) => (
          <NavLink key={code} to={`/market/quarterly-report/${code.toLowerCase()}`}
            className={({ isActive }) => clsx(
              'whitespace-nowrap rounded-md px-3 py-1.5 text-xs font-semibold transition-colors',
              isActive ? 'bg-accent text-white' : 'bg-bg-card text-text-secondary hover:text-text-primary',
            )}>
            {SECTOR_LABELS[code]}
          </NavLink>
        ))}
      </nav>

      <div className="card space-y-3 !p-0">
        <div className="flex flex-wrap items-center justify-between gap-3 px-4 pt-4">
          <p className="text-xs text-text-secondary">
            {meta?.fiscal_year && meta.quarter ? (
              <>
                <span className="font-mono font-semibold text-text-primary">Q{meta.quarter} {shortFiscalYear(meta.fiscal_year)}</span>
                {' · '}{meta.reported_count} of {meta.total_companies} tracked companies have reported so far.
                {' '}Figures come from each company's own filing; the season is ongoing, so this list grows as more report.
              </>
            ) : report.isPending ? 'Loading…' : 'No filings crawled for this sector yet'}
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <Filter label="Fiscal Year">
              <select value={selectedYear} disabled={yearPeriods.length === 0}
                onChange={(e) => update({ fiscal_year: e.target.value, quarter: null })}
                className={`${selectClass} min-w-[110px]`}>
                {yearPeriods.length === 0 && <option value="">—</option>}
                {yearPeriods.map((p) => <option key={p.fiscal_year} value={p.fiscal_year}>{shortFiscalYear(p.fiscal_year)}</option>)}
              </select>
            </Filter>
            <Filter label="Quarter">
              <select value={quarter ?? meta?.quarter ?? ''} disabled={quarters.length === 0}
                onChange={(e) => update({ fiscal_year: selectedYear || null, quarter: e.target.value })}
                className={`${selectClass} min-w-[80px]`}>
                {quarters.length === 0 && <option value="">—</option>}
                {quarters.map((q) => <option key={q} value={q}>Q{q}</option>)}
              </select>
            </Filter>
          </div>
        </div>

        {report.isError ? (
          <div className="flex items-center justify-center gap-2 py-12 text-sm text-down">
            <AlertTriangle size={14} /> Could not load the quarterly report.
            <button onClick={() => void report.refetch()} className="underline">Retry</button>
          </div>
        ) : report.isPending ? (
          <p className="py-12 text-center text-sm text-text-muted">Loading quarterly report…</p>
        ) : rows.length === 0 ? (
          <p className="px-4 py-12 text-center text-sm text-text-muted">
            {meta?.fiscal_year
              ? 'No tracked company in this sector has filed this quarter yet.'
              : 'No quarterly reports for this sector yet: they are crawled daily, or run `manage.py crawl_quarterly_reports`.'}
          </p>
        ) : (
          <QuarterlyReportTable rows={rows} avgWindow={meta?.avg_window ?? 3} dimmed={report.isPlaceholderData} />
        )}

        <p className="flex items-start gap-1.5 px-4 pb-4 text-[11px] text-text-muted">
          <Info size={12} className="mt-px shrink-0" />
          <span>
            n/m = not meaningful. Filed figures (from nepsetrading.com) are often unaudited and may be revised.
            {' '}LTP, PE, PB and yields use the latest crawled close.
            {meta && ` The ${meta.avg_window}Y average needs at least ${meta.avg_min_years} years; a tag like (2y) marks a shorter history.`}
            {' '}Informational only, not financial advice.
          </span>
        </p>
      </div>
    </div>
  );
}
