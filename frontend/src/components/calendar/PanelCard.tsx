import type { ReactNode } from 'react';

/** A titled card inside the calendar's day panel. */
export function PanelCard({ title, aside, children }: { title: ReactNode; aside?: ReactNode; children: ReactNode }) {
  // bg-bg-primary/50 specifically: the light theme overrides that class (index.css).
  return (
    <section className="overflow-hidden rounded-lg border border-bg-border bg-bg-primary/50">
      <header className="flex items-center justify-between gap-3 border-b border-bg-border px-3 py-2">
        <h3 className="min-w-0 text-[11px] font-semibold uppercase tracking-wide text-text-muted">{title}</h3>
        {aside && <span className="shrink-0 text-[11px] text-text-muted">{aside}</span>}
      </header>
      {children}
    </section>
  );
}
