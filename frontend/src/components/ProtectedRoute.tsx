import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import type { Role } from "../types";

interface ProtectedRouteProps {
  children: ReactNode;
  roles?: Role[];
}

// Wraps a route: requires login, and optionally one of `roles`.
// Role checks here are a UX convenience only -- the backend must be the
// real enforcement point (see README: RBAC is not yet enforced
// server-side on most endpoints in this snapshot of the backend).
export default function ProtectedRoute({ children, roles }: ProtectedRouteProps) {
  const { user, initializing, hasRole } = useAuth();
  const location = useLocation();

  if (initializing) {
    return <div className="page-loading">Loading…</div>;
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (roles && roles.length > 0 && !hasRole(...roles)) {
    return (
      <div className="empty-state">
        <h2>Not authorized</h2>
        <p>Your role ({user.role}) doesn't have access to this page.</p>
      </div>
    );
  }

  return <>{children}</>;
}
