import { useEffect, useMemo, useRef, useState } from 'react';
import clsx from 'clsx';
import {
  Check, ChevronDown, ChevronRight, Eye, EyeOff, Info, Layers, Plus, Search, SlidersHorizontal, Trash2, X,
} from 'lucide-react';
import type {
  IndicatorDef, IndicatorParamDef, IndicatorParams, IndicatorRegistry,
} from '../../api/marketIntelligence';
import { outputColor } from './registryIndicators';

export interface ActiveIndicator {
  uid: string;
  id: string;
  params: IndicatorParams;
  hidden?: boolean;
}

interface Builtin { name: string; label: string; on: boolean }

interface Props {
  registry: IndicatorRegistry | null;
  registryError: string;
  active: ActiveIndicator[];
  errors: Record<string, string>;
  builtins: Builtin[];
  dailyOnly: boolean;
  onAdd: (def: IndicatorDef) => void;
  onRemove: (uid: string) => void;
  onParams: (uid: string, params: IndicatorParams) => void;
  onToggleHidden: (uid: string) => void;
  onBuiltin: (name: string, on: boolean) => void;
  onClose: () => void;
}

// Marks the toolbar button, so clicking it is not treated as an outside click.
export const PICKER_TOGGLE_ATTR = 'data-indicator-toggle';

function Switch({ on, onChange, label }: { on: boolean; onChange: (on: boolean) => void; label: string }) {
  return (
    <button type="button" role="switch" aria-checked={on} aria-label={label} onClick={() => onChange(!on)}
      className={clsx('relative h-4 w-7 shrink-0 rounded-full transition-colors', on ? 'bg-accent' : 'bg-slate-400/60')}>
      <span className={clsx('absolute top-0.5 h-3 w-3 rounded-full bg-white shadow transition-all', on ? 'left-3.5' : 'left-0.5')} />
    </button>
  );
}

function ParamInput({ def, value, onCommit }: { def: IndicatorParamDef; value: number | string; onCommit: (v: number | string) => void }) {
  const [draft, setDraft] = useState(String(value));
  const [invalid, setInvalid] = useState(false);
  const field = 'w-full rounded-md border bg-bg-elevated px-2 py-1 text-xs tabular-nums text-text-primary outline-none transition focus:border-accent';

  if (def.kind === 'choice') {
    return (
      <select value={String(value)} onChange={(e) => onCommit(e.target.value)} className={clsx(field, 'border-border')}>
        {def.choices.map((c) => <option key={c} value={c}>{c}</option>)}
      </select>
    );
  }
  const commit = () => {
    const n = Number(draft);
    const ok = draft.trim() !== '' && Number.isFinite(n) && n >= def.min && n <= def.max
      && (def.kind === 'float' || Number.isInteger(n));
    setInvalid(!ok);
    if (ok && n !== value) onCommit(n);
  };
  return (
    <input value={draft} inputMode="decimal" onChange={(e) => { setDraft(e.target.value); setInvalid(false); }}
      onBlur={commit} onKeyDown={(e) => { if (e.key === 'Enter') commit(); }}
      title={`${def.min}–${def.max}${def.kind === 'int' ? ', whole number' : ''}`}
      aria-invalid={invalid}
      className={clsx(field, invalid ? 'border-red-500' : 'border-border')} />
  );
}

function ActiveCard({ def, item, error, onRemove, onParams, onToggleHidden }: {
  def: IndicatorDef; item: ActiveIndicator; error?: string;
  onRemove: () => void; onParams: (p: IndicatorParams) => void; onToggleHidden: () => void;
}) {
  const [open, setOpen] = useState(false);
  const summary = def.params.map((p) => item.params[p.name] ?? p.default).join(', ');
  return (
    <div className={clsx('rounded-lg border bg-bg-card transition', error ? 'border-red-500/60' : 'border-border',
      item.hidden && 'opacity-50')}>
      <div className="flex items-center gap-2 px-2.5 py-2">
        <span className="flex shrink-0 -space-x-1" aria-hidden>
          {def.outputs.slice(0, 3).map((o, i) => (
            <span key={o.key} className="h-2.5 w-2.5 rounded-full ring-1 ring-black/10" style={{ background: outputColor(o.kind, i) }} />
          ))}
        </span>
        <button type="button" onClick={() => def.params.length && setOpen((v) => !v)}
          className="min-w-0 flex-1 text-left" aria-expanded={open}>
          <span className="block truncate text-xs font-medium text-text-primary">{def.name}</span>
          {summary && <span className="block truncate text-[11px] tabular-nums text-text-secondary">{summary}</span>}
        </button>
        {def.params.length > 0 && (
          <button type="button" onClick={() => setOpen((v) => !v)} title="Settings" aria-label={`${def.name} settings`}
            className={clsx('rounded p-1 transition hover:bg-bg-elevated', open ? 'text-accent' : 'text-text-secondary hover:text-text-primary')}>
            <SlidersHorizontal size={13} />
          </button>
        )}
        <button type="button" onClick={onToggleHidden} title={item.hidden ? 'Show' : 'Hide'}
          aria-label={`${item.hidden ? 'Show' : 'Hide'} ${def.name}`}
          className="rounded p-1 text-text-secondary transition hover:bg-bg-elevated hover:text-text-primary">
          {item.hidden ? <EyeOff size={13} /> : <Eye size={13} />}
        </button>
        <button type="button" onClick={onRemove} title="Remove" aria-label={`Remove ${def.name}`}
          className="rounded p-1 text-text-secondary transition hover:bg-red-500/10 hover:text-red-500">
          <Trash2 size={13} />
        </button>
      </div>
      {open && (
        <div className="grid grid-cols-2 gap-x-3 gap-y-2 border-t border-border px-2.5 py-2">
          {def.params.map((p) => (
            <label key={p.name} className="flex flex-col gap-1 text-[11px] text-text-secondary">
              {p.label}
              <ParamInput key={`${item.uid}-${p.name}-${item.params[p.name]}`} def={p}
                value={item.params[p.name] ?? p.default}
                onCommit={(v) => onParams({ ...item.params, [p.name]: v })} />
            </label>
          ))}
        </div>
      )}
      {(error || (open && def.notes)) && (
        <p className={clsx('px-2.5 pb-2 text-[11px]', error ? 'text-red-500' : 'text-text-secondary')}>{error || def.notes}</p>
      )}
    </div>
  );
}

export default function IndicatorPicker(props: Props) {
  const { registry, active } = props;
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('All');
  const [showMissing, setShowMissing] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(props.onClose);
  onCloseRef.current = props.onClose;

  const byId = useMemo(() => new Map((registry?.indicators ?? []).map((d) => [d.id, d])), [registry]);
  const addedCount = useMemo(() => {
    const counts = new Map<string, number>();
    active.forEach((a) => counts.set(a.id, (counts.get(a.id) ?? 0) + 1));
    return counts;
  }, [active]);
  const categories = useMemo(() => {
    const counts = new Map<string, number>();
    (registry?.indicators ?? []).forEach((d) => counts.set(d.category, (counts.get(d.category) ?? 0) + 1));
    return [...counts.entries()];
  }, [registry]);
  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (registry?.indicators ?? []).filter((d) =>
      (category === 'All' || d.category === category)
      && (!q || `${d.name} ${d.id} ${d.category}`.toLowerCase().includes(q)));
  }, [registry, query, category]);
  const grouped = useMemo(() => {
    const out = new Map<string, IndicatorDef[]>();
    matches.forEach((d) => out.set(d.category, [...(out.get(d.category) ?? []), d]));
    return [...out.entries()];
  }, [matches]);

  // Close on Escape or a click outside (the toolbar toggle handles its own clicks).
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onCloseRef.current(); };
    const onDown = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (rootRef.current?.contains(target) || target.closest(`[${PICKER_TOGGLE_ATTR}]`)) return;
      onCloseRef.current();
    };
    document.addEventListener('keydown', onKey);
    document.addEventListener('mousedown', onDown);
    return () => { document.removeEventListener('keydown', onKey); document.removeEventListener('mousedown', onDown); };
  }, []);

  const visibleCount = active.filter((a) => !a.hidden).length;

  return (
    <div ref={rootRef} role="dialog" aria-label="Indicators"
      className="absolute left-2 top-10 z-30 flex max-h-[min(560px,80vh)] w-[min(680px,calc(100vw-2rem))] flex-col overflow-hidden rounded-xl border border-border bg-bg-card shadow-2xl">
      {/* Header */}
      <div className="flex items-center gap-3 border-b border-border px-4 py-3">
        <div className="flex items-center gap-2">
          <Layers size={16} className="text-accent" />
          <span className="text-sm font-semibold text-text-primary">Indicators</span>
          <span className="rounded-full bg-accent/15 px-2 py-0.5 text-[11px] font-medium text-accent">{visibleCount} active</span>
        </div>
        <div className="relative ml-auto min-w-0 flex-1 sm:max-w-[280px]">
          <Search size={14} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-text-secondary" />
          <input autoFocus value={query} onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter' && matches[0]) props.onAdd(matches[0]); }}
            placeholder={registry ? `Search ${registry.indicators.length} indicators…` : 'Search indicators…'}
            aria-label="Search indicators"
            className="w-full rounded-lg border border-border bg-bg-elevated py-1.5 pl-8 pr-7 text-xs text-text-primary outline-none transition focus:border-accent" />
          {query && (
            <button type="button" onClick={() => setQuery('')} aria-label="Clear search"
              className="absolute right-2 top-1/2 -translate-y-1/2 text-text-secondary hover:text-text-primary">
              <X size={12} />
            </button>
          )}
        </div>
        <button type="button" onClick={props.onClose} aria-label="Close"
          className="rounded-md p-1 text-text-secondary transition hover:bg-bg-elevated hover:text-text-primary">
          <X size={16} />
        </button>
      </div>

      {props.dailyOnly && (
        <div className="flex items-center gap-2 border-b border-border bg-amber-500/10 px-4 py-2 text-[11px] text-amber-500">
          <Info size={13} /> Library indicators use daily bars — switch the chart to 1D to see them.
        </div>
      )}

      <div className="flex min-h-0 flex-1 flex-col sm:flex-row">
        {/* Library */}
        <div className="flex min-h-0 flex-col sm:w-[55%] sm:border-r sm:border-border">
          <div className="flex flex-wrap gap-1.5 border-b border-border px-3 py-2">
            {[['All', registry?.indicators.length ?? 0] as const, ...categories].map(([name, count]) => (
              <button key={name} type="button" onClick={() => setCategory(name)}
                className={clsx('shrink-0 rounded-full px-2.5 py-1 text-[11px] font-medium transition',
                  category === name ? 'bg-accent text-white' : 'bg-bg-elevated text-text-secondary hover:text-text-primary')}>
                {name} <span className="opacity-70">{count}</span>
              </button>
            ))}
          </div>
          <div className="min-h-[160px] flex-1 overflow-y-auto px-2 py-2">
            {props.registryError && <p className="px-2 py-1 text-xs text-red-500">{props.registryError}</p>}
            {!registry && !props.registryError && (
              <div className="space-y-2 p-2">{[0, 1, 2, 3, 4].map((i) => <div key={i} className="h-6 animate-pulse rounded bg-bg-elevated" />)}</div>
            )}
            {registry && matches.length === 0 && (
              <p className="px-2 py-6 text-center text-xs text-text-secondary">No indicator matches “{query}”.</p>
            )}
            {grouped.map(([cat, defs]) => (
              <div key={cat} className="mb-2">
                {category === 'All' && (
                  <p className="sticky top-0 z-10 bg-bg-card px-2 py-1 text-[10px] font-semibold uppercase tracking-wide text-text-secondary">{cat}</p>
                )}
                {defs.map((def) => {
                  const count = addedCount.get(def.id) ?? 0;
                  return (
                    <button key={def.id} type="button" onClick={() => props.onAdd(def)} title={def.notes || undefined}
                      className="group flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left transition hover:bg-bg-elevated">
                      <span className={clsx('min-w-0 flex-1 truncate text-xs', count ? 'font-medium text-text-primary' : 'text-text-primary')}>
                        {def.name}
                      </span>
                      <span className={clsx('shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium',
                        def.display === 'overlay' ? 'bg-sky-500/10 text-sky-500' : 'bg-violet-500/10 text-violet-500')}>
                        {def.display === 'overlay' ? 'Price' : 'Panel'}
                      </span>
                      <span className="flex w-5 shrink-0 justify-center">
                        {count
                          ? <Check size={14} className="text-emerald-500 group-hover:hidden" />
                          : null}
                        <Plus size={14} className={clsx('text-accent', count ? 'hidden group-hover:block' : 'opacity-0 group-hover:opacity-100')} />
                      </span>
                    </button>
                  );
                })}
              </div>
            ))}
          </div>
        </div>

        {/* On the chart */}
        <div className="flex min-h-0 flex-col border-t border-border sm:w-[45%] sm:border-t-0">
          <div className="min-h-0 flex-1 space-y-3 overflow-y-auto px-3 py-3">
            <div>
              <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wide text-text-secondary">Chart</p>
              <div className="space-y-1">
                {props.builtins.map((b) => (
                  <div key={b.name} className="flex items-center justify-between gap-2 rounded-md px-1 py-1">
                    <span className="text-xs text-text-primary">{b.label}</span>
                    <Switch on={b.on} label={b.label} onChange={(on) => props.onBuiltin(b.name, on)} />
                  </div>
                ))}
              </div>
            </div>

            <div>
              <p className="mb-1.5 flex items-center justify-between text-[10px] font-semibold uppercase tracking-wide text-text-secondary">
                <span>On the chart</span>
                <span className="tabular-nums">{active.length}</span>
              </p>
              {active.length === 0 ? (
                <div className="rounded-lg border border-dashed border-border px-3 py-6 text-center text-xs text-text-secondary">
                  Nothing added yet. Pick an indicator on the left.
                </div>
              ) : (
                <div className="space-y-2">
                  {active.map((a) => {
                    const def = byId.get(a.id);
                    return def ? (
                      <ActiveCard key={a.uid} def={def} item={a} error={props.errors[a.uid]}
                        onRemove={() => props.onRemove(a.uid)} onParams={(p) => props.onParams(a.uid, p)}
                        onToggleHidden={() => props.onToggleHidden(a.uid)} />
                    ) : null;
                  })}
                </div>
              )}
            </div>
          </div>

          {/* Footer */}
          <div className="space-y-2 border-t border-border px-3 py-2.5">
            <p className="text-[11px] leading-snug text-text-secondary">
              Calculated from crawled prices only. Lines start once there are enough sessions for their period.
            </p>
            {registry && registry.not_implemented.length > 0 && (
              <div>
                <button type="button" onClick={() => setShowMissing((v) => !v)}
                  className="flex items-center gap-1 text-[11px] text-text-secondary hover:text-text-primary">
                  {showMissing ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
                  Not implemented ({registry.not_implemented.length})
                </button>
                {showMissing && (
                  <ul className="mt-1 space-y-0.5 pl-4 text-[11px] text-text-secondary">
                    {registry.not_implemented.map((m) => <li key={m.name} title={m.reason}>{m.name}</li>)}
                  </ul>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
