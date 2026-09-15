import { useEffect } from 'react';

export function useLiveRefresh(refresh: () => void, intervalMs = 5000) {
  useEffect(() => {
    const timer = window.setInterval(refresh, intervalMs);
    return () => window.clearInterval(timer);
  }, [refresh, intervalMs]);
}