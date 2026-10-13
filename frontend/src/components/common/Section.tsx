import type { ReactNode } from 'react';

// One page section: a consistent header (title, subtitle, optional controls on the right)
// above its cards. Pages stack sections with `space-y-8` so every gap is the same.

interface SectionHeaderProps {
  title: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
}

export function SectionHeader({ title, subtitle, action }: SectionHeaderProps) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-x-4 gap-y-2 border-b border-bg-border pb-2">
      <div className="min-w-0">
        <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-text-primary">{title}</h2>
        {subtitle && <p className="mt-0.5 text-xs text-text-muted">{subtitle}</p>}
      </div>
      {action && <div className="flex shrink-0 flex-wrap items-center gap-2">{action}</div>}
    </div>
  );
}

interface SectionProps extends SectionHeaderProps {
  id?: string;
  className?: string;
  children: ReactNode;
}

export default function Section({ id, className = '', children, ...header }: SectionProps) {
  return (
    <section id={id} className={`scroll-mt-4 space-y-4 ${className}`}>
      <SectionHeader {...header} />
      {children}
    </section>
  );
}
