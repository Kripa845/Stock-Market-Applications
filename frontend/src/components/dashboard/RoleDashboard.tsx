import { useCallback, useState } from 'react';
import { AlertCircle, Loader2, RefreshCw } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { useDashboardData, resolveDataPath } from '../../hooks/useDashboardData';
import PageHeader from '../common/PageHeader';
import { universalDashboardConfig } from './dashboardConfig';
import type { DashboardCardData, DashboardSectionData } from './dashboardConfig';
import DashboardCard from './DashboardCard';
import QuickActionCard from './QuickActionCard';

// ---------------------------------------------------------------------------
// Helper — resolve the best dashboard route prefix based on the user's role.
// Analysts and Viewers share the same pages but may have different URL
// prefixes registered in the router.  We centralise the mapping here so
// the dashboard config can use role-neutral paths like "/news" and the
// component appends the correct prefix.
// ---------------------------------------------------------------------------
function resolveDashboardRoute(route: string, role: string): string {
  // Admin has its own URL namespace for management pages
  if (role === 'admin') {
    const adminOnlyRoutes: Record<string, string> = {
      '/users': '/users',
      '/roles-permissions': '/roles-permissions',
      '/crawl': '/crawl',
    };
    if (adminOnlyRoutes[route]) return adminOnlyRoutes[route];
  }
  // All roles share these pages at the same path now (unified routing)
  return route;
}

interface RoleDashboardProps {
  role?: string | null;
}

export default function RoleDashboard({ role: _roleProp }: RoleDashboardProps) {
  const { user, hasPermission, hasAnyPermission, loading: authLoading } = useAuth();
  const [refreshKey, setRefreshKey] = useState(0);

  // Determine role from user object — not from the hardcoded prop
  const role = user?.role ?? _roleProp ?? null;

  const { stats, loading, error, refetch } = useDashboardData(role);

  const handleRefresh = useCallback(() => {
    setRefreshKey((k) => k + 1);
    refetch();
  }, [refetch]);

  const isLoading = authLoading || loading;

  const resolveValue = useCallback(
    (dataPath?: string): string | number => {
      if (!stats || !dataPath) return '—';
      const raw = resolveDataPath(stats as unknown as Record<string, unknown>, dataPath);
      if (raw === undefined || raw === null) return '—';
      if (typeof raw === 'number') return raw;
      if (typeof raw === 'string') return raw;
      return String(raw);
    },
    [stats],
  );

  // -------------------------------------------------------------------------
  // Permission-based card filter
  // -------------------------------------------------------------------------
  const canSeeCard = (card: DashboardCardData): boolean => {
    if (!card.requiredPermission) return true;
    return hasPermission(card.requiredPermission);
  };

  const canSeeSection = (section: DashboardSectionData): boolean => {
    if (!section.requiredAnyPermission || section.requiredAnyPermission.length === 0) {
      return true;
    }
    return hasAnyPermission(section.requiredAnyPermission);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="animate-spin text-accent" size={32} />
      </div>
    );
  }

  if (!user) {
    return null;
  }

  const config = universalDashboardConfig;

  // Build a display name for the dashboard header
  const roleName =
    user.effective_role ??
    (role ? role.charAt(0).toUpperCase() + role.slice(1) : 'My');

  return (
    <div key={refreshKey} className="space-y-6">
      {error && (
        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-sm text-down">
          {error}
          <button onClick={handleRefresh} className="underline ml-1">
            Retry
          </button>
        </div>
      )}

      <PageHeader
        title={`${roleName} Dashboard`}
        subtitle={config.subtitle}
        actions={
          <button
            onClick={handleRefresh}
            className="btn-ghost flex items-center gap-2"
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
        }
      />

      {/* Render only the sections + cards the user's permissions allow */}
      {config.sections.map((section) => {
        if (!canSeeSection(section)) return null;

        const visibleCards = section.cards.filter(canSeeCard);
        if (visibleCards.length === 0) return null;

        const statCards = visibleCards.filter((c) => c.type !== 'quick-action');
        const quickActions = visibleCards.filter((c) => c.type === 'quick-action');

        return (
          <div key={section.id} className="space-y-4">
            <div>
              <h2 className="text-base font-semibold text-text-primary">
                {section.title}
              </h2>
              {section.description && (
                <p className="text-sm text-text-secondary mt-0.5">
                  {section.description}
                </p>
              )}
            </div>

            {statCards.length > 0 && (
              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 xl:gap-4 gap-4">
                {statCards.map((card) => (
                  <DashboardCard
                    key={card.id}
                    card={{
                      ...card,
                      route: resolveDashboardRoute(card.route, role ?? ''),
                    }}
                    value={resolveValue(card.dataPath)}
                  />
                ))}
              </div>
            )}

            {quickActions.length > 0 && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {quickActions.map((card) => (
                  <QuickActionCard
                    key={card.id}
                    title={card.title}
                    description={card.description}
                    icon={card.icon}
                    route={resolveDashboardRoute(card.route, role ?? '')}
                  />
                ))}
              </div>
            )}
          </div>
        );
      })}

      {/* Empty state — user has no permissions at all */}
      {config.sections.every((s) => !canSeeSection(s)) && (
        <div className="card flex flex-col items-center gap-4 py-16 text-center">
          <AlertCircle size={48} className="text-text-muted" />
          <div>
            <p className="text-lg font-semibold text-text-primary">
              No content available
            </p>
            <p className="text-sm text-text-secondary mt-1 max-w-sm">
              Your account does not have any permissions assigned yet. Contact an
              administrator to configure your access.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
