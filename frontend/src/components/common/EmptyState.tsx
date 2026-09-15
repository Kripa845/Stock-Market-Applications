import { Inbox } from 'lucide-react';

interface EmptyStateProps {
  title?: string;
  description?: string;
  icon?: React.ReactNode;
}

export default function EmptyState({
  title = 'No data available',
  description = 'There is nothing to display here yet.',
  icon,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center gap-3">
      <div className="text-text-muted">
        {icon ?? <Inbox size={36} />}
      </div>
      <p className="text-sm font-medium text-text-secondary">{title}</p>
      <p className="text-xs text-text-muted max-w-xs">{description}</p>
    </div>
  );
}
