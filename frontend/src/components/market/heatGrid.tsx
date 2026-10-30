// Shared by the NEPSE day-by-day and month-by-month heat grids: sidebar controls, stat cards,
// index chips, legend, the Day / Month switch and tile drag-select.
import { useCallback, useEffect, useRef, useState } from 'react';
import { NavLink, useSearchParams } from 'react-router-dom';

import { heatClass } from './weekday';

export const DEFAULT_INDEX = 'NEPSE';

export function Segmented<T extends string | number>({ label, value, options, onChange }: {
  label: string; value: T; options: { value: T; label: string; className?: string }[]; onChange: (v: T) => void;
}) {
  return (
    <div role="group" aria-label={label} className="flex gap-1 rounded-xl border border-bg-border bg-bg-card p-1">
      {options.map((o) => (
        <button key={o.value} type="button" aria-pressed={o.value === value} onClick={() => onChange(o.value)}
          className={`flex-1 rounded-lg px-2 py-1.5 text-xs transition ${o.className ?? ''} ${
            o.value === value ? 'bg-accent/20 font-semibold text-accent' : 'text-text-secondary hover:text-text-primary'
          }`}>
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function MiniStat({ label, icon, iconClass, value, valueClass = 'text-text-primary', sub }: {
  label: string; icon: React.ReactNode; iconClass: string; value: string; valueClass?: string; sub: React.ReactNode;
}) {
  return (
    <div className="card !rounded-2xl !p-4">
      <div className="flex items-start justify-between gap-2">
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-text-secondary">{label}</p>
        <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ${iconClass}`}>{icon}</span>
      </div>
      <p className={`mt-1 font-mono text-2xl font-semibold ${valueClass}`}>{value}</p>
      <div className="mt-1 truncate text-xs text-text-secondary">{sub}</div>
    </div>
  );
}

export function IndexChips({ indices, index, onIndex }: {
  indices: { code: string; label: string }[] | undefined; index: string; onIndex: (code: string) => void;
}) {
  return (
    <div>
      <p className="mb-2 text-xs font-semibold uppercase tracking-[0.14em] text-text-muted">Indices</p>
      <div className="grid grid-cols-3 gap-1.5 sm:grid-cols-4 lg:grid-cols-2">
        {(indices ?? [{ code: DEFAULT_INDEX, label: 'NEPSE' }]).map((i) => (
          <button key={i.code} type="button" onClick={() => onIndex(i.code)} title={i.label} aria-pressed={i.code === index}
            className={`truncate rounded-lg border px-2 py-1.5 text-[11px] font-medium transition ${
              i.code === index
                ? 'border-accent/50 bg-accent/20 font-semibold text-accent'
                : 'border-bg-border bg-bg-card text-text-secondary hover:text-text-primary'
            }`}>
            {i.label}
          </button>
        ))}
      </div>
    </div>
  );
}

// heatClass steps as fractions of the scale, strongest fall first.
const LEGEND_STEPS = [-1, -0.6, -0.3, -0.1, 0, 0.1, 0.3, 0.6, 1];

export function HeatLegend({ scale = 1 }: { scale?: number }) {
  return (
    <div>
      <div className="flex gap-1">
        {LEGEND_STEPS.map((p) => <span key={p} className={`h-3 flex-1 rounded ${heatClass(p * scale, scale)}`} />)}
      </div>
      <div className="mt-1.5 flex justify-between font-mono text-[10px] text-text-muted">
        <span>−{scale}%</span><span>0</span><span>+{scale}%</span>
      </div>
    </div>
  );
}

/** The selected index lives in ?index= so the Day / Month switch keeps it. */
export function useIndexParam(): [string, (code: string) => void] {
  const [params, setParams] = useSearchParams();
  const index = params.get('index')?.toUpperCase() || DEFAULT_INDEX;
  const setIndex = useCallback((code: string) => {
    setParams((current) => {
      const next = new URLSearchParams(current);
      if (code === DEFAULT_INDEX) next.delete('index'); else next.set('index', code);
      return next;
    }, { replace: true });
  }, [setParams]);
  return [index, setIndex];
}

export function HeatViewTabs({ index }: { index: string }) {
  const query = index === DEFAULT_INDEX ? '' : `?index=${index}`;
  const tabs = [
    { to: '/market/day-by-day', label: 'Day by day' },
    { to: '/market/month-by-month', label: 'Month by month' },
  ];
  return (
    <nav aria-label="Grid view" className="flex gap-1 rounded-xl border border-bg-border bg-bg-card p-1">
      {tabs.map((t) => (
        <NavLink key={t.to} to={`${t.to}${query}`} end
          className={({ isActive }) => `flex-1 rounded-lg px-2 py-1.5 text-center text-xs transition ${
            isActive ? 'bg-accent/20 font-semibold text-accent' : 'text-text-secondary hover:text-text-primary'
          }`}>
          {t.label}
        </NavLink>
      ))}
    </nav>
  );
}

/**
 * Press, drag or shift-click across tiles carrying `data-sel` keys that sort in time order
 * (ISO dates, "2083-07").  Esc clears.  Returns the sorted [from, to] range.
 */
export function useDragSelect() {
  const [selection, setSelection] = useState<{ anchor: string; end: string } | null>(null);
  const dragging = useRef(false);

  const onDown = useCallback((e: React.PointerEvent, key: string) => {
    if (e.button !== 0) return;
    setSelection((current) => (e.shiftKey && current ? { ...current, end: key } : { anchor: key, end: key }));
    // Touch keeps its swipe for scrolling the grid; drag-select is for mouse and pen.
    dragging.current = e.pointerType !== 'touch';
  }, []);

  const onGridMove = useCallback((e: React.PointerEvent) => {
    if (!dragging.current) return;
    const key = (document.elementFromPoint(e.clientX, e.clientY) as HTMLElement | null)
      ?.closest<HTMLElement>('[data-sel]')?.dataset.sel;
    if (key) setSelection((current) => (current && current.end !== key ? { ...current, end: key } : current));
  }, []);

  useEffect(() => {
    const stop = () => { dragging.current = false; };
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') setSelection(null); };
    window.addEventListener('pointerup', stop);
    window.addEventListener('keydown', esc);
    return () => { window.removeEventListener('pointerup', stop); window.removeEventListener('keydown', esc); };
  }, []);

  const range = selection ? [selection.anchor, selection.end].sort() as [string, string] : null;
  return { range, onDown, onGridMove, dragging, clear: useCallback(() => setSelection(null), []) };
}
