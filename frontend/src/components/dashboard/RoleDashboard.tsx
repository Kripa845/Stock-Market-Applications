import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { AlertCircle, Loader2, RefreshCw } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';
import { useDashboardData, resolveDataPath } from '../../hooks/useDashboardData';
import PageHeader from '../common/PageHeader';
import { dashboardConfigs } from './dashboardConfig';
import type { DashboardConfig } from './dashboardConfig';
import DashboardCard from './DashboardCard';
import QuickActionCard from './QuickActionCard';

function normalizeRole(role?: string | null): string | null {
  if (!role) return null;
  const normalized = role.toLowerCase().trim();
  if (['admin', 'analyst', 'viewer'].includes(normalized)) {
    return normalized;
  }
  return null;
}

interface RoleDashboardProps {
  role?: string | null;
}

export default function RoleDashboard({ role: roleProp }: RoleDashboardProps) {
  const { user, loading: authLoading } = useAuth();
  const navigate = useNavigate();
  const [refreshKey, setRefreshKey] = useState(0);

  const role = normalizeRole(roleProp ?? user?.role ?? user?.effective_role ?? null);

  const { stats, loading, error, refetch } = useDashboardData(role);

  useEffect(() => {
    if (!authLoading && !role) {
      navigate('/viewer');
    }
  }, [authLoading, role, navigate]);

  const config: DashboardConfig | undefined = role ? dashboardConfigs[role] : undefined;

  const handleRefresh = useCallback(() => {
    setRefreshKey((k) => k + 1);
    refetch();
  }, [refetch]);

  const isLoading = authLoading || loading;

  const resolveValue = useCallback((dataPath?: string): string | number => {
    if (!stats || !dataPath) return '—';
    const raw = resolveDataPath(stats as Record<string, any>, dataPath);
    if (raw === undefined || raw === null) return '—';
    if (typeof raw === 'number') return raw;
    if (typeof raw === 'string') return raw;
    return String(raw);
  }, [stats]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="animate-spin text-accent" size={32} />
      </div>
    );
  }

  if (!role || !config) {
    return (
      <div className="space-y-6">
        <PageHeader
          title="Access Denied"
          subtitle="Your role is not recognized. Please contact an administrator."
        />
        <div className="card flex flex-col items-center gap-4 py-16">
          <AlertCircle size={48} className="text-down" />
          <div className="text-center">
            <p className="text-lg font-semibold text-text-primary">Unknown Role</p>
            <p className="text-sm text-text-secondary mt-1">
              Your account role could not be determined. Please contact an administrator.
            </p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div key={refreshKey} className="space-y-6">
      {error && (
        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-sm text-down">
          {error}
          <button onClick={handleRefresh} className="underline ml-1">Retry</button>
        </div>
      )}

      <PageHeader
        title={config.title}
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

      {config.sections.map((section) => {
        const statCards = section.cards.filter((c) => c.type !== 'quick-action');
        const quickActions = section.cards.filter((c) => c.type === 'quick-action');

        if (statCards.length === 0 && quickActions.length === 0) return null;

        return (
          <div key={section.id} className="space-y-4">
            <div>
              <h2 className="text-base font-semibold text-text-primary">{section.title}</h2>
              {section.description && (
                <p className="text-sm text-text-secondary mt-0.5">{section.description}</p>
              )}
            </div>

            {statCards.length > 0 && (
              <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 xl:gap-4 gap-4">
                {statCards.map((card) => (
                  <DashboardCard
                    key={card.id}
                    card={card}
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
                    route={card.route}
                  />
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
