// Searchable dropdown for the Broker Acc / Dist page: multi-select (stocks, with colour dots and a
// cap) or single-select (broker).  Keyboard: Enter / Space / ArrowDown open; arrows move; Enter picks;
// Escape closes.
import { useEffect, useMemo, useRef, useState } from 'react';
import { Check, ChevronDown, X } from 'lucide-react';

export interface PickerOption {
  value: string;
  label: string;
  hint?: string;
  color?: string;
  /** Selected but hidden on the chart. */
  muted?: boolean;
}

interface PickerProps {
  label: string;
  placeholder: string;
  options: PickerOption[];
  selected: string[];
  onChange: (values: string[]) => void;
  multi?: boolean;
  /** Multi-select only: options beyond this many are disabled. */
  max?: number;
  heading?: string;
  disabled?: boolean;
  clearable?: boolean;
  /** The option under the pointer or keyboard cursor (null when none), e.g. to highlight its line. */
  onHover?: (value: string | null) => void;
}

export default function Picker({
  label, placeholder, options, selected, onChange, multi = false, max, heading, disabled = false, clearable = true, onHover,
}: PickerProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [active, setActive] = useState(0);
  const root = useRef<HTMLDivElement>(null);
  const search = useRef<HTMLInputElement>(null);

  const matches = useMemo(() => {
    const q = query.trim().toLowerCase();
    return q ? options.filter((o) => `${o.label} ${o.hint ?? ''}`.toLowerCase().includes(q)) : options;
  }, [options, query]);

  // Report the option under the cursor while open, and null once when it closes.  Never while
  // closed: other controls (chips, legend) own the highlight then.
  const wasOpen = useRef(false);
  useEffect(() => {
    if (open) onHover?.(matches[active]?.value ?? null);
    else if (wasOpen.current) onHover?.(null);
    wasOpen.current = open;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, active, matches]);

  useEffect(() => {
    if (!open) return undefined;
    const onDown = (e: MouseEvent) => { if (root.current && !root.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener('mousedown', onDown);
    search.current?.focus();
    return () => document.removeEventListener('mousedown', onDown);
  }, [open]);

  const full = multi && max != null && selected.length >= max;
  const pick = (value: string) => {
    if (!multi) { onChange([value]); setOpen(false); return; }
    if (selected.includes(value)) onChange(selected.filter((v) => v !== value));
    else if (!full) onChange([...selected, value]);
  };
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive((a) => Math.min(matches.length - 1, a + 1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(0, a - 1)); }
    else if (e.key === 'Enter') { e.preventDefault(); if (matches[active]) pick(matches[active].value); }
    else if (e.key === 'Escape') setOpen(false);
  };
  const byValue = new Map(options.map((o) => [o.value, o]));
  const shown = selected.map((v) => byValue.get(v)?.label ?? v).join(', ');

  return (
    <div ref={root} className={`relative min-w-0 ${disabled ? 'pointer-events-none opacity-50' : ''}`}>
      <div
        role="combobox" tabIndex={0} aria-expanded={open} aria-haspopup="listbox" aria-label={label}
        onClick={() => { setOpen((o) => !o); setQuery(''); setActive(0); }}
        onKeyDown={(e) => { if (['Enter', ' ', 'ArrowDown'].includes(e.key)) { e.preventDefault(); setOpen(true); } else if (e.key === 'Escape') setOpen(false); }}
        className={`flex min-h-[46px] cursor-pointer items-center gap-2 rounded-md border bg-bg-card px-3 py-1.5 transition ${
          open ? 'border-accent' : 'border-bg-border hover:border-accent/60'
        }`}
      >
        <span className="flex min-w-0 flex-1 flex-col">
          <span className="text-[10px] uppercase tracking-wide text-text-muted">{label}</span>
          <span className={`truncate text-sm ${shown ? 'font-medium text-text-primary' : 'text-text-muted'}`}>{shown || placeholder}</span>
        </span>
        {clearable && selected.length > 0 && (
          <button type="button" aria-label={`Clear ${label}`} onClick={(e) => { e.stopPropagation(); onChange([]); }}
            className="rounded-full p-1 text-text-muted hover:bg-bg-elevated hover:text-text-primary">
            <X size={14} />
          </button>
        )}
        <ChevronDown size={15} className={`shrink-0 text-text-muted transition ${open ? 'rotate-180' : ''}`} />
      </div>

      {open && (
        <div className="absolute left-0 right-0 top-full z-30 mt-1 flex max-h-[360px] flex-col overflow-hidden rounded-md border border-bg-border bg-bg-card shadow-2xl">
          {heading && <p className="px-3 pb-1 pt-2.5 text-[10px] font-semibold uppercase tracking-[0.12em] text-text-muted">{heading}</p>}
          <input ref={search} value={query} onChange={(e) => { setQuery(e.target.value); setActive(0); }} onKeyDown={onKey}
            placeholder="Search" aria-label={`Search ${label}`}
            className="m-2 rounded-md border border-bg-border bg-bg-elevated px-3 py-1.5 text-sm text-text-primary outline-none focus:border-accent" />
          <div role="listbox" aria-multiselectable={multi} className="overflow-y-auto py-1">
            {matches.length === 0 && <p className="px-3 py-3 text-sm text-text-muted">No match</p>}
            {matches.map((o, i) => {
              const on = selected.includes(o.value);
              const blocked = multi && !on && full;
              return (
                <div key={o.value} role="option" aria-selected={on} aria-disabled={blocked}
                  onMouseEnter={() => setActive(i)} onClick={() => !blocked && pick(o.value)}
                  className={`flex cursor-pointer items-center gap-2.5 px-3 py-2 text-sm ${i === active ? 'bg-bg-elevated' : ''} ${
                    blocked ? 'cursor-not-allowed opacity-40' : ''
                  } ${on ? (o.muted ? 'font-semibold text-text-muted' : 'font-semibold text-text-primary') : 'text-text-secondary'}`}>
                  {multi && (
                    <span className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border ${on ? 'border-accent bg-accent text-white' : 'border-text-muted'}`}>
                      {on && <Check size={11} strokeWidth={3} />}
                    </span>
                  )}
                  {o.color && <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: o.color }} />}
                  <span className={`truncate ${o.muted ? 'line-through' : ''}`}>{o.label}</span>
                  {o.hint && <span className="ml-auto truncate pl-2 text-xs text-text-muted">{o.hint}</span>}
                  {!multi && on && <Check size={14} className="ml-auto text-accent" />}
                </div>
              );
            })}
          </div>
          {multi && (
            <div className="flex items-center justify-between border-t border-bg-border px-3 py-2 text-xs">
              <span className="text-text-muted">{selected.length}{max != null ? ` / ${max}` : ''} selected</span>
              <button type="button" onClick={() => onChange([])} disabled={!selected.length}
                className="font-semibold text-accent hover:underline disabled:cursor-not-allowed disabled:opacity-40 disabled:no-underline">
                Select none
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
