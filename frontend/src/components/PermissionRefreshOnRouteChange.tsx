import { useEffect, useRef } from 'react';
import { useLocation } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';

/**
 * Refreshes the user's permission list whenever the route changes.
 *
 * Throttled to at most once every 10 seconds to avoid hammering the API
 * when the user navigates quickly between pages.  The refresh still fires
 * immediately on the first navigation after login.
 */
export default function PermissionRefreshOnRouteChange() {
  const { refreshPermissions, user } = useAuth();
  const location = useLocation();
  const lastRefreshRef = useRef<number>(0);
  const THROTTLE_MS = 10_000; // 10 seconds

  useEffect(() => {
    if (!user) return;

    const now = Date.now();
    if (now - lastRefreshRef.current < THROTTLE_MS) return;

    lastRefreshRef.current = now;
    refreshPermissions();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);

  return null;
}
