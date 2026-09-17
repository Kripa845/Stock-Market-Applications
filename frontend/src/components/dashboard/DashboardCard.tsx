import { useNavigate } from 'react-router-dom';
import { ArrowRight } from 'lucide-react';
import clsx from 'clsx';
import type { DashboardCardData } from './dashboardConfig';
import { useAuth } from '../../contexts/AuthContext';

interface DashboardCardProps {
  card: DashboardCardData;
  value?: string | number;
}

export default function DashboardCard({ card, value }: DashboardCardProps) {
  const navigate = useNavigate();
  const { user } = useAuth();
  const role = user?.role?.toLowerCase();

  if (card.allowedRoles && card.allowedRoles.length > 0 && !card.allowedRoles.includes(role ?? '')) {
    return null;
  }

  const handleClick = () => {
    navigate(card.route);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      navigate(card.route);
    }
  };

  const isQuickAction = card.type === 'quick-action';

  const displayValue = value ?? '—';

  if (isQuickAction) {
    return (
      <button
        onClick={handleClick}
        onKeyDown={handleKeyDown}
        className={clsx(
          'flex w-full items-center justify-between',
          'p-4 rounded-xl border',
          'bg-bg-card border-bg-border',
          'hover:border-accent/40 hover:bg-bg-elevated/50',
          'transition-all duration-200',
          'cursor-pointer text-left',
          'focus:outline-none focus:ring-2 focus:ring-accent/40 focus:ring-offset-1 focus:ring-offset-bg-primary',
        )}
        role="link"
        aria-label={`${card.title} — go to ${card.route}`}
        tabIndex={0}
      >
        <div className="flex items-center gap-3">
          {card.icon && (
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-accent/10 text-accent-light">
              <card.icon size={18} />
            </span>
          )}
          <div>
            <p className="text-sm font-semibold text-text-primary">{card.title}</p>
            {card.description && (
              <p className="text-xs text-text-muted">{card.description}</p>
            )}
          </div>
        </div>
        <ArrowRight size={16} className="text-text-muted shrink-0" />
      </button>
    );
  }

  return (
    <div
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      className={clsx(
        'flex flex-col gap-3 p-4 rounded-xl border',
        'bg-bg-card border-bg-border',
        'transition-all duration-200',
        'cursor-pointer hover:border-accent/40 hover:bg-bg-elevated/50',
        'focus:outline-none focus:ring-2 focus:ring-accent/40 focus:ring-offset-1 focus:ring-offset-bg-primary',
      )}
      role="link"
      aria-label={`${card.title} — go to ${card.route}`}
      tabIndex={0}
    >
      <div className="flex items-start justify-between">
        <p className="text-xs text-text-secondary font-medium uppercase tracking-wide">{card.title}</p>
        {card.icon && (
          <span className={clsx('p-1.5 rounded-lg bg-bg-elevated', card.iconColor ?? 'text-accent-light')}>
            <card.icon size={14} />
          </span>
        )}
      </div>
      <div>
        <p className="text-2xl font-bold text-text-primary font-mono">{displayValue}</p>
        {card.badge && (
          <span className="inline-flex items-center mt-1 px-2 py-0.5 rounded text-[10px] font-medium bg-accent-glow text-accent-light border border-accent-dim">
            {card.badge}
          </span>
        )}
      </div>
      {card.description && (
        <p className="text-xs text-text-muted">{card.description}</p>
      )}
      <ArrowRight size={14} className="text-text-muted mt-auto" />
    </div>
  );
}
