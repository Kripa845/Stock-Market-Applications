import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { useAuth } from "../contexts/AuthContext";

/**
 * Refreshes user permissions whenever the route changes.
 *
 * This ensures that when an admin updates role permissions,
 * the changes take effect on the next navigation.
 */
export default function PermissionRefreshOnRouteChange() {
  const { refreshPermissions, user } = useAuth();
  const location = useLocation();

  useEffect(() => {
    if (user) {
      refreshPermissions();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);

  return null;
}