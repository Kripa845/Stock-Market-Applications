import { useMemo } from "react";

type Role =
  | "admin"
  | "analyst"
  | "viewer";

export function usePermissions(
  role?: Role
) {
  return useMemo(() => {
    const admin =
      role === "admin";

    const analyst =
      role === "analyst" ||
      role === "admin";

    return {
      isAdmin: admin,
      isAnalyst: analyst,
      isViewer:
        role === "viewer",

      canManageCompanies:
        admin,

      canManageWatchlist:
        admin,

      canTriggerCrawl:
        admin,

      canMonitorCrawl:
        admin,

      canViewCrawlLogs:
        admin,

      canManageUsers:
        admin,

      canChangeRoles:
        admin,

      canViewAnalytics:
        true,

      canViewNews:
        true,

      canViewMarketData:
        true,
    };
  }, [role]);
}