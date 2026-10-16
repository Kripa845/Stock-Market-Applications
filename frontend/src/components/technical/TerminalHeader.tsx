// Top bar of the Technical Charts terminal: back, the selected symbol with its price,
// a symbol search (Ctrl/⌘ K), the market status, refresh and the theme switch.
import { useEffect, useMemo, useRef, useState } from 'react';
import { ArrowLeft, RefreshCw, Search } from 'lucide-react';
import clsx from 'clsx';

import ThemeToggle from '../ThemeToggle';
import { ChangeBadge, RowIcon, fmt, indexLabel, type ListRow } from './terminal';

const MAX_RESULTS = 8;

const kindLabel = (row: ListRow) => (row.kind === 'company' ? row.group : row.isSubIndex ? 'Sub-index' : 'Index');

function SymbolSearch({ rows, onSelect }: { rows: ListRow[]; onSelect: (row: ListRow) => void }) {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const [cursor, setCursor] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const isMac = typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        inputRef.current?.focus();
        inputRef.current?.select();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return rows.slice(0, MAX_RESULTS);
    const score = (row: ListRow) => {
      const code = row.code.toLowerCase();
      const label = (row.kind === 'index' ? indexLabel(row) : row.name).toLowerCase();
      if (code === q) return 0;
      if (code.startsWith(q) || label.startsWith(q)) return 1;
      if (code.includes(q) || label.includes(q) || row.name.toLowerCase().includes(q)) return 2;
      if (row.group.toLowerCase().includes(q)) return 3;
      return -1;
    };
    return rows
      .map((row) => ({ row, s: score(row) }))
      .filter((item) => item.s >= 0)
      .sort((a, b) => a.s - b.s)
      .slice(0, MAX_RESULTS)
      .map((item) => item.row);
  }, [rows, query]);

  const choose = (row: ListRow) => {
    onSelect(row);
    setQuery('');
    setOpen(false);
    inputRef.current?.blur();
  };

  return (
    <div className="relative w-full max-w-[420px]">
      <Search size={16} className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-text-muted" />
      <input
        ref={inputRef}
        value={query}
        onChange={(event) => { setQuery(event.target.value); setCursor(0); setOpen(true); }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 120)}
        onKeyDown={(event) => {
          if (event.key === 'ArrowDown') { event.preventDefault(); setCursor((c) => Math.min(c + 1, results.length - 1)); }
          else if (event.key === 'ArrowUp') { event.preventDefault(); setCursor((c) => Math.max(c - 1, 0)); }
          else if (event.key === 'Enter' && results[cursor]) choose(results[cursor]);
          else if (event.key === 'Escape') { setOpen(false); event.currentTarget.blur(); }
        }}
        placeholder="Search symbol, index, sector…"
        aria-label="Search symbols"
        role="combobox"
        aria-expanded={open}
        aria-controls="terminal-symbol-results"
        className="h-10 w-full rounded-xl border border-bg-border bg-bg-card pl-10 pr-20 text-[13px] text-text-primary outline-none transition-colors placeholder:text-text-muted focus:border-accent/70 focus:ring-2 focus:ring-accent/20"
      />
      <kbd className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 rounded-md border border-bg-border px-1.5 py-0.5 font-mono text-[10px] text-text-muted">
        {isMac ? '⌘ K' : 'Ctrl K'}
      </kbd>
      {open && (
        <ul id="terminal-symbol-results" role="listbox" className="absolute left-0 right-0 top-12 z-40 max-h-[420px] overflow-y-auto rounded-xl border border-bg-border bg-bg-card p-1.5 shadow-2xl">
          {results.length === 0 ? (
            <li className="px-3 py-6 text-center text-xs text-text-muted">No symbol matches “{query}”.</li>
          ) : results.map((row, i) => (
            <li key={row.key} role="option" aria-selected={i === cursor}>
              <button
                type="button"
                onMouseDown={(event) => event.preventDefault()}
                onMouseEnter={() => setCursor(i)}
                onClick={() => choose(row)}
                className={clsx('flex w-full items-center gap-3 rounded-lg px-2.5 py-2 text-left', i === cursor && 'bg-accent/10')}
              >
                <RowIcon row={row} />
                <span className="min-w-0 flex-1 leading-tight">
                  <span className="block truncate text-[13px] font-semibold text-text-primary">
                    {row.kind === 'index' ? indexLabel(row) : row.code}
                  </span>
                  <span className="block truncate text-[11px] text-text-muted">{row.name}</span>
                </span>
                <span className="rounded-md bg-bg-elevated px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-text-secondary">{kindLabel(row)}</span>
                <span className="w-20 text-right font-mono text-xs tabular-nums text-text-primary">{fmt(row.ltp)}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function MarketStatus({ open }: { open: boolean | null }) {
  const today = new Date().toLocaleDateString('en-GB', { timeZone: 'Asia/Kathmandu', weekday: 'short', day: 'numeric', month: 'short' });
  return (
    <span className={clsx(
      'hidden items-center gap-2 whitespace-nowrap rounded-full px-3.5 py-2 text-xs font-medium xl:flex',
      open ? 'bg-up/10 text-up' : 'bg-bg-elevated text-text-secondary',
    )}>
      <span className={clsx('h-2 w-2 rounded-full', open ? 'animate-pulse bg-up' : 'bg-text-muted')} />
      {open === null ? 'Market status unknown' : `Market ${open ? 'open' : 'closed'}`} · {today.replace(',', '')}
    </span>
  );
}

export default function TerminalHeader({ selected, rows, marketOpen, busy, onBack, onRefresh, onSelect }: {
  selected: ListRow | null;
  rows: ListRow[];
  marketOpen: boolean | null;
  busy: boolean;
  onBack: () => void;
  onRefresh: () => void;
  onSelect: (row: ListRow) => void;
}) {
  const title = !selected ? 'Technical Charts'
    : selected.kind === 'index' ? (selected.code === 'NEPSE' ? 'NEPSE Index' : selected.name.replace(/ ?Sub-?Index$/i, ' Sub-index'))
    : selected.code;
  const subtitle = !selected ? 'Pick a symbol' : selected.kind === 'index' ? 'NEPSE · Technical chart' : selected.name;
  const chip = !selected ? null : selected.kind === 'index' ? (selected.isSubIndex ? 'Sub-index' : 'Index') : selected.group;

  return (
    <header className="flex h-[60px] shrink-0 items-center gap-4 border-b border-bg-border bg-bg-secondary px-4">
      <button
        type="button"
        onClick={onBack}
        className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm font-medium text-text-secondary hover:bg-white/[0.04] hover:text-text-primary"
      >
        <ArrowLeft size={16} />
        Back
      </button>
      <span className="h-8 w-px bg-bg-border" />

      {selected && (
        <div className="flex min-w-0 items-center gap-3">
          <RowIcon row={selected} size="lg" />
          <div className="min-w-0 leading-tight">
            <div className="flex items-center gap-2">
              <h1 className="truncate text-[15px] font-semibold text-text-primary">{title}</h1>
              {chip && (
                <span className="hidden whitespace-nowrap rounded-md border border-bg-border bg-bg-elevated px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide text-text-secondary sm:inline">
                  {chip}
                </span>
              )}
            </div>
            <p className="mt-0.5 truncate text-xs text-text-muted">{subtitle}</p>
          </div>
          <div className="ml-3 hidden items-center gap-3 md:flex">
            <span className="font-mono text-2xl font-semibold tabular-nums text-text-primary">{fmt(selected.ltp)}</span>
            <ChangeBadge ch={selected.ch} chPct={selected.chPct} withPoints className="text-xs" />
          </div>
        </div>
      )}

      <div className="ml-auto flex min-w-0 flex-1 items-center justify-end gap-3">
        <SymbolSearch rows={rows} onSelect={onSelect} />
        <MarketStatus open={marketOpen} />
        <button
          type="button"
          onClick={onRefresh}
          disabled={busy}
          title="Refresh"
          aria-label="Refresh"
          className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-bg-border text-text-muted transition-colors hover:bg-blue-500/10 hover:text-text-primary disabled:opacity-50"
        >
          <RefreshCw size={16} className={busy ? 'animate-spin' : ''} />
        </button>
        <ThemeToggle />
      </div>
    </header>
  );
}
