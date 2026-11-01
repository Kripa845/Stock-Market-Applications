import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { compareApi, MIN_SYMBOLS } from '../api/compare';

// Stock comparison, its picker list and the coverage report.  The previous comparison stays
// on screen while a new symbol set loads; nothing is fetched until two symbols are chosen.

export function useCompare(symbols: string[], date?: string) {
  return useQuery({
    queryKey: ['compare', symbols.join(','), date ?? null],
    queryFn: () => compareApi.compare(symbols, date),
    enabled: symbols.length >= MIN_SYMBOLS,
    placeholderData: keepPreviousData,
    retry: false,
  });
}

export function useCompareCompanies() {
  return useQuery({
    queryKey: ['compare-companies'],
    queryFn: compareApi.companies,
    staleTime: 30 * 60_000,
  });
}

export function useCompareCoverage(enabled: boolean) {
  return useQuery({
    queryKey: ['compare-coverage'],
    queryFn: compareApi.coverage,
    enabled,
    staleTime: 10 * 60_000,
  });
}
