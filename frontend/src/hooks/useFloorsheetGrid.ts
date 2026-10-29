import { useCallback, useEffect, useRef, useState } from 'react';
import { floorsheetGridApi, type BucketMinutes, type FloorsheetGrid } from '../api/floorsheetGrid';
import { useLiveRefresh } from './useLiveRefresh';

const LIVE_REFRESH_MS = 60_000;

// One session's grid.  A response for an older date / bucket size is dropped so fast
// switching can't show stale cells; a live session reloads every minute.

export function useFloorsheetGrid(date: string, minutes: BucketMinutes) {
  const [data, setData] = useState<FloorsheetGrid | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const latest = useRef(0);

  const load = useCallback(() => {
    const id = ++latest.current;
    setLoading(true);
    setError('');
    floorsheetGridApi.get({ date, minutes })
      .then((grid) => { if (id === latest.current) setData(grid); })
      .catch((err: unknown) => {
        if (id !== latest.current) return;
        const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
        setError(detail ?? 'Unable to load the floor sheet summary.');
      })
      .finally(() => { if (id === latest.current) setLoading(false); });
  }, [date, minutes]);

  useEffect(() => { load(); }, [load]);

  const live = data?.status === 'live';
  const refreshLive = useCallback(() => { if (live) load(); }, [live, load]);
  useLiveRefresh(refreshLive, LIVE_REFRESH_MS);

  return { data, loading, error, reload: load };
}
