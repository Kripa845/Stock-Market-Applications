import { ArrowRight, type LucideIcon } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import clsx from 'clsx';

interface StatCardProps {
  title: string;
  value: string | number;
  description?: string;
  icon?: LucideIcon;
  route?: string;
  iconColor?: string;
  badge?: string;
}

export default function StatCard({
  title,
  value,
  description,
  icon: Icon,
  route,
  iconColor = 'text-accent-light',
  badge,
}: StatCardProps) {
  const navigate = useNavigate();

  const handleClick = () => {
    if (route) navigate(route);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if ((e.key === 'Enter' || e.key === ' ') && route) {
      e.preventDefault();
      navigate(route);
    }
  };

  const isClickable = !!route;

  return (
    <div
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      className={clsx(
        'flex flex-col gap-3 p-4 rounded-xl border',
        'bg-bg-card border-bg-border',
        'transition-all duration-200',
        isClickable && 'cursor-pointer hover:border-accent/40 hover:bg-bg-elevated/50',
        isClickable && 'focus:outline-none focus:ring-2 focus:ring-accent/40 focus:ring-offset-1 focus:ring-offset-bg-primary',
      )}
      role={isClickable ? 'link' : undefined}
      aria-label={isClickable ? `${title} — go to ${route}` : undefined}
      tabIndex={isClickable ? 0 : undefined}
    >
      <div className="flex items-start justify-between">
        <p className="text-xs text-text-secondary font-medium uppercase tracking-wide">{title}</p>
        {Icon && (
          <span className={clsx('p-1.5 rounded-lg bg-bg-elevated', iconColor)}>
            <Icon size={14} />
          </span>
        )}
      </div>
      <div>
        <p className="text-2xl font-bold text-text-primary font-mono">{value}</p>
        {badge && (
          <span className="inline-flex items-center mt-1 px-2 py-0.5 rounded text-[10px] font-medium bg-accent-glow text-accent-light border border-accent-dim">
            {badge}
          </span>
        )}
      </div>
      {description && (
        <p className="text-xs text-text-muted">{description}</p>
      )}
      {isClickable && (
        <ArrowRight size={14} className="text-text-muted mt-auto" />
      )}
    </div>
  );
}
