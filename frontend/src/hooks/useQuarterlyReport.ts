import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { quarterlyReportApi, type QuarterlyReportQuery, type SectorCode } from '../api/quarterlyReports';

// Quarterly report table and its period selectors.  The previous table stays on screen while
// another sector / period loads.

export function useQuarterlyReport(query: QuarterlyReportQuery) {
  return useQuery({
    queryKey: ['quarterly-report', query.sector, query.fiscal_year ?? null, query.quarter ?? null],
    queryFn: () => quarterlyReportApi.report(query),
    placeholderData: keepPreviousData,
  });
}

export function useQuarterlyReportPeriods(sector: SectorCode) {
  return useQuery({
    queryKey: ['quarterly-report-periods', sector],
    queryFn: () => quarterlyReportApi.periods(sector),
    staleTime: 10 * 60_000,
  });
}
