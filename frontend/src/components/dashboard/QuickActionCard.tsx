import { useNavigate } from 'react-router-dom';
import { ArrowRight, type LucideIcon } from 'lucide-react';
import clsx from 'clsx';

interface QuickActionCardProps {
  title: string;
  description?: string;
  icon?: LucideIcon;
  route: string;
  iconColor?: string;
  allowedRoles?: string[];
}

export default function QuickActionCard({
  title,
  description,
  icon: Icon,
  route,
  iconColor = 'text-accent-light',
}: QuickActionCardProps) {
  const navigate = useNavigate();

  const handleClick = () => navigate(route);
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      navigate(route);
    }
  };

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
      aria-label={`${title} — go to ${route}`}
      tabIndex={0}
    >
      <div className="flex items-center gap-3">
        {Icon && (
          <span className={clsx('flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-accent/10', iconColor)}>
            <Icon size={18} />
          </span>
        )}
        <div>
          <p className="text-sm font-semibold text-text-primary">{title}</p>
          {description && (
            <p className="text-xs text-text-muted">{description}</p>
          )}
        </div>
      </div>
      <ArrowRight size={16} className="text-text-muted shrink-0" />
    </button>
  );
}
