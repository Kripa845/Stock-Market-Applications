import clsx from 'clsx';
import type { LucideIcon } from 'lucide-react';

interface SummaryCardProps {
  title: string;
  value: string | number;
  change?: string;
  changePositive?: boolean;
  icon: LucideIcon;
  iconColor?: string;
  sparkline?: number[];
  sub?: string;
}

export default function SummaryCard({
  title, value, change, changePositive, icon: Icon, iconColor = 'text-accent-light', sub,
}: SummaryCardProps) {
  return (
    <div className="card flex flex-col gap-3 hover:border-accent/30 transition-colors">
      <div className="flex items-start justify-between">
        <p className="text-xs text-text-secondary font-medium uppercase tracking-wide">{title}</p>
        <span className={clsx('p-1.5 rounded-lg bg-bg-elevated', iconColor)}>
          <Icon size={14} />
        </span>
      </div>
      <div>
        <p className="text-2xl font-bold text-text-primary font-mono">{value}</p>
        {(change || sub) && (
          <p className={clsx('text-xs mt-1', change && changePositive !== undefined
            ? changePositive ? 'text-up' : 'text-down'
            : 'text-text-muted')}>
            {change ?? sub}
          </p>
        )}
      </div>
    </div>
  );
}
