import clsx from 'clsx';

interface BadgeProps {
  children: React.ReactNode;
  variant?: 'purple' | 'green' | 'red' | 'yellow' | 'gray' | 'blue';
  size?: 'sm' | 'xs';
  className?: string;
}

const VARIANTS = {
  purple: 'bg-accent-glow text-accent-light border border-accent-dim',
  green:  'bg-green-500/10 text-up border border-green-500/20',
  red:    'bg-red-500/10 text-down border border-red-500/20',
  yellow: 'bg-yellow-500/10 text-yellow-400 border border-yellow-500/20',
  gray:   'bg-bg-elevated text-text-secondary border border-bg-border',
  blue:   'bg-blue-500/10 text-blue-400 border border-blue-500/20',
};

export default function Badge({ children, variant = 'gray', size = 'sm', className }: BadgeProps) {
  return (
    <span className={clsx(
      'inline-flex items-center font-medium rounded',
      size === 'sm' ? 'px-2 py-0.5 text-xs' : 'px-1.5 py-0.5 text-[10px]',
      VARIANTS[variant],
      className
    )}>
      {children}
    </span>
  );
}
