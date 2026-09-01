import type { ReactNode } from "react";
import { useAuth } from "../context/AuthContext";
import type { Role } from "../types";

interface RoleGateProps {
  roles: Role[];
  children: ReactNode;
}

// Inline conditional render for role-restricted UI, e.g.
// <RoleGate roles={["admin", "analyst"]}><button>Correct tag</button></RoleGate>
export default function RoleGate({ roles, children }: RoleGateProps) {
  const { hasRole } = useAuth();
  if (!hasRole(...roles)) return null;
  return <>{children}</>;
}
