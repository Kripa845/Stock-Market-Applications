import { useId, useRef, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import clsx from 'clsx';

// Stock Comparison look: the dark #151515 / #1a1d24 palette with the teal selection
// shared with the News source filter (components/news/SourceFilter.tsx).
export const ui = {
  page: 'bg-[#151515] font-mulish text-[#e5e7eb]',
  card: 'rounded-xl border border-white/[0.08] bg-[#1a1d24]',
  input: 'rounded-lg border border-white/[0.08] bg-[#151515] text-sm text-[#e5e7eb] placeholder:text-[#8b93a1]',
  chip: 'border-white/[0.08] bg-[#1a1d24] text-[#d1d5db] hover:border-white/20 hover:bg-[#22262f]',
  selected: 'border-[#1f6f6b] bg-[#0f3b3b] text-white',
  band: 'bg-[#0f3b3b]/45',
  muted: 'text-[#8b93a1]',
  focus: 'focus:outline-none focus-visible:ring-2 focus-visible:ring-[#2dd4bf] focus-visible:ring-offset-2 focus-visible:ring-offset-[#151515]',
};

const TIP_WIDTH = 288;

/**
 * Hover / keyboard-focus tooltip.  Rendered in a portal with fixed positioning so the
 * table's scroll container never clips it.
 */
export function Tip({ content, children, className, label }: {
  content: ReactNode; children: ReactNode; className?: string; label?: string;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const id = useId();
  const [pos, setPos] = useState<{ x: number; y: number; above: boolean } | null>(null);

  const show = () => {
    const rect = ref.current?.getBoundingClientRect();
    if (!rect) return;
    const above = rect.top > 140;
    const half = TIP_WIDTH / 2 + 8;
    const x = Math.min(Math.max(rect.left + rect.width / 2, half), window.innerWidth - half);
    setPos({ x, y: above ? rect.top - 6 : rect.bottom + 6, above });
  };

  return (
    <span ref={ref} tabIndex={0} aria-label={label} aria-describedby={pos ? id : undefined}
      onMouseEnter={show} onMouseLeave={() => setPos(null)} onFocus={show} onBlur={() => setPos(null)}
      className={clsx('rounded', ui.focus, className)}>
      {children}
      {pos && createPortal(
        <span role="tooltip" id={id}
          style={{ left: pos.x, top: pos.y, maxWidth: TIP_WIDTH, transform: `translate(-50%, ${pos.above ? '-100%' : '0'})` }}
          className="pointer-events-none fixed z-[100] rounded-lg border border-white/[0.12] bg-[#0d0f13] px-3 py-2 text-left font-mulish text-xs leading-relaxed text-[#e5e7eb] shadow-xl">
          {content}
        </span>,
        document.body,
      )}
    </span>
  );
}

/** Shimmering placeholder block. */
export function Shimmer({ className }: { className?: string }) {
  return <span aria-hidden="true" className={clsx('block animate-pulse rounded bg-white/[0.06]', className)} />;
}
