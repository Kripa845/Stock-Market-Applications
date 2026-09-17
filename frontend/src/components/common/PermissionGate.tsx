import type { ReactNode } from 'react';
import { useAuth } from '../../contexts/AuthContext';

interface PermissionGateProps {
  permission?: string;
  permissions?: string[];
  mode?: 'any' | 'all';
  fallback?: ReactNode;
  children: ReactNode;
}

export default function PermissionGate({
  permission,
  permissions,
  mode = 'any',
  fallback = null,
  children,
}: PermissionGateProps) {
  const { hasAnyPermission, hasAllPermissions } = useAuth();

  const keys = permission ? [permission] : (permissions ?? []);

  if (keys.length === 0) {
    return <>{children}</>;
  }

  const allowed =
    mode === 'all' ? hasAllPermissions(keys) : hasAnyPermission(keys);

  return allowed ? <>{children}</> : <>{fallback}</>;
}

export function Can(props: PermissionGateProps) {
  return <PermissionGate {...props} />;
}
