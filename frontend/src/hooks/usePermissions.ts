import { useMemo } from "react";

type Role = "admin" | "analyst" | "viewer";

export interface UserPermissions {
  permissions: string[];
}

export function usePermissions(
  role?: Role,
  permissions?: string[]
) {
  const perms = useMemo(() => {
    if (role === "admin") {
      return null;
    }

    return permissions || [];
  }, [role, permissions]);

  const hasPermission = (key: string) => {
    if (role === "admin") {
      return true;
    }

    return perms ? perms.includes(key) : false;
  };

  const hasAnyPermission = (keys: string[]) => {
    if (role === "admin") {
      return true;
    }

    if (!perms) {
      return false;
    }

    return keys.some((key) => perms.includes(key));
  };

  const hasAllPermissions = (keys: string[]) => {
    if (role === "admin") {
      return true;
    }

    if (!perms) {
      return false;
    }

    return keys.every((key) => perms.includes(key));
  };

  return useMemo(
    () => {
      const can = (key: string) =>
        hasPermission(key);

      return {
        // Role checks
        isAdmin: role === "admin",

        isAnalyst:
          role === "analyst" ||
          role === "admin",

        isViewer: role === "viewer",

        // Generic helpers
        can,
        hasAnyPermission,
        hasAllPermission: hasAllPermissions,

        // Companies
        canViewCompanies: can("view_companies"),
        canCreateCompanies: can("create_companies"),
        canEditCompanies: can("edit_companies"),
        canDeleteCompanies: can("delete_companies"),
        canManageTrackedCompanies: can(
          "manage_tracked_companies"
        ),

        // Market Data
        canViewMarketData: can("view_market_data"),
        canViewPriceHistory: can(
          "view_price_history"
        ),
        canViewTradingVolume: can(
          "view_trading_volume"
        ),

        // News
        canViewNews: can("view_news"),
        canCategorizeNews: can("categorize_news"),
        canCorrectCategories: can(
          "correct_categories"
        ),

        // Watchlist
        canViewWatchlist: can("view_watchlist"),
        canAddWatchlist: can("add_watchlist"),
        canRemoveWatchlist: can("remove_watchlist"),

        // Crawler
        canViewCrawlRuns: can("view_crawl_runs"),
        canRunCrawler: can("run_crawler"),
        canViewCrawlLogs: can("view_crawl_logs"),
        canRetryFailedCrawl: can("retry_failed_crawl"),

        // Analysis
        canViewAnalysis: can("view_analysis"),

        // Reports
        canViewReports: can("view_reports"),
        canExportReports: can("export_reports"),

        // Users
        canViewUsers: can("view_users"),
        canCreateUsers: can("create_users"),
        canEditUsers: can("edit_users"),
        canDeleteUsers: can("delete_users"),
        canChangeUserRoles: can("change_user_roles"),
        canActivateUsers: can("activate_users"),

        // Roles & Permissions
        canViewRoles: can("view_roles"),
        canCreateRoles: can("create_roles"),
        canEditRoles: can("edit_roles"),
        canDeleteRoles: can("delete_roles"),
        canAssignRoles: can("assign_roles"),

        // Legacy aliases
        canManageCompanies: can("create_companies") ||
          can("edit_companies") ||
          can("delete_companies") ||
          can("manage_tracked_companies"),
        canManageWatchlist: can("add_watchlist") ||
          can("remove_watchlist"),
        canTriggerCrawl: can("run_crawler"),
        canMonitorCrawl: can("view_crawl_runs"),
        canManageUsers: can("create_users") ||
          can("edit_users") ||
          can("delete_users") ||
          can("change_user_roles") ||
          can("activate_users"),
        canChangeRoles: can("change_user_roles") ||
          can("edit_roles") ||
          can("assign_roles"),
        canViewRolesPermissions: can("view_roles"),
        canViewAnalytics: can("view_analysis"),
      };
    },
    [role, perms]
  );
}