import clsx from 'clsx';

interface SkeletonProps { className?: string; }

export function Skeleton({ className }: SkeletonProps) {
  return <div className={clsx('skeleton', className)} />;
}

export function CardSkeleton() {
  return (
    <div className="card space-y-3">
      <Skeleton className="h-4 w-24" />
      <Skeleton className="h-8 w-32" />
      <Skeleton className="h-3 w-40" />
    </div>
  );
}

export function TableSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </div>
  );
}
