import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { compareApi, MIN_SYMBOLS } from '../api/compare';

// Stock comparison and its picker.  The previous comparison stays on screen while a new
// symbol set loads; nothing is fetched until at least two symbols are chosen.

export function useCompare(symbols: string[]) {
  return useQuery({
    queryKey: ['compare', symbols.join(',')],
    queryFn: () => compareApi.compare(symbols),
    enabled: symbols.length >= MIN_SYMBOLS,
    placeholderData: keepPreviousData,
    retry: false,
  });
}

export function useCompareCompanies() {
  return useQuery({
    queryKey: ['compare-companies'],
    queryFn: compareApi.companies,
    staleTime: 10 * 60_000,
  });
}
