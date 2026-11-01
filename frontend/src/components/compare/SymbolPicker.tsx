import { useId, useMemo, useRef, useState } from 'react';
import clsx from 'clsx';
import { Layers, Search, X } from 'lucide-react';

import { MAX_SYMBOLS, MIN_SYMBOLS, type CompareCompany } from '../../api/compare';
import { Shimmer, ui } from './ui';

// Searchable multi-select over the tracked companies from /api/compare/companies/.
// Results are grouped by sector; the sector filter lists whatever sectors the data has.

export default function SymbolPicker({ companies, selected, onChange, loading, error }: {
  companies: CompareCompany[]; selected: string[]; onChange: (next: string[]) => void;
  loading: boolean; error: boolean;
}) {
  const [query, setQuery] = useState('');
  const [sector, setSector] = useState('');
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  const listId = useId();
  const full = selected.length >= MAX_SYMBOLS;

  const bySymbol = useMemo(() => new Map(companies.map((c) => [c.symbol, c])), [companies]);
  const sectors = useMemo(() => [...new Set(companies.map((c) => c.sector))].sort(), [companies]);

  const groups = useMemo(() => {
    const q = query.trim().toLowerCase();
    const matches = companies.filter((c) => !selected.includes(c.symbol)
      && (!sector || c.sector === sector)
      && (!q || c.symbol.toLowerCase().includes(q) || c.name.toLowerCase().includes(q)));
    const map = new Map<string, CompareCompany[]>();
    matches.forEach((c) => map.set(c.sector, [...(map.get(c.sector) ?? []), c]));
    return [...map.entries()].sort(([a], [b]) => a.localeCompare(b))
      .map(([name, list]) => [name, list.sort((a, b) => a.symbol.localeCompare(b.symbol))] as const);
  }, [companies, selected, sector, query]);
  const flat = useMemo(() => groups.flatMap(([, list]) => list), [groups]);

  const lastSector = selected.length ? bySymbol.get(selected[selected.length - 1])?.sector : undefined;
  const sameSectorLeft = lastSector
    ? companies.filter((c) => c.sector === lastSector && !selected.includes(c.symbol)).length : 0;

  const add = (symbol: string) => {
    if (full || selected.includes(symbol)) return;
    onChange([...selected, symbol]);
    setQuery('');
    setActive(0);
    if (selected.length + 1 >= MAX_SYMBOLS) setOpen(false);
  };

  const onKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setOpen(true); setActive((i) => Math.min(i + 1, flat.length - 1)); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive((i) => Math.max(i - 1, 0)); }
    else if (e.key === 'Enter') { e.preventDefault(); if (open && flat[active]) add(flat[active].symbol); }
    else if (e.key === 'Escape') setOpen(false);
    else if (e.key === 'Backspace' && !query && selected.length) onChange(selected.slice(0, -1));
  };

  const compareWithinSector = () => {
    if (!lastSector) return;
    setSector(lastSector);
    setQuery('');
    setActive(0);
    setOpen(true);
    inputRef.current?.focus();
  };

  const optionId = (symbol: string) => `${listId}-${symbol}`;
  const showList = open && !full && !loading;

  return (
    <section aria-label="Choose companies" className={clsx(ui.card, 'space-y-3 p-4')}
      onBlur={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setOpen(false); }}>
      {selected.length > 0 && (
        <ul className="flex flex-wrap gap-2" aria-label="Selected companies">
          {selected.map((symbol) => {
            const company = bySymbol.get(symbol);
            return (
              <li key={symbol}
                className={clsx('flex h-[38px] items-center gap-2 rounded-lg border pl-3 pr-1 text-sm font-semibold', ui.selected)}>
                <span>{symbol}</span>
                {company && <span className="hidden max-w-[12rem] truncate text-xs font-normal text-[#b9e6e1] sm:inline">{company.name}</span>}
                <button type="button" onClick={() => onChange(selected.filter((s) => s !== symbol))}
                  aria-label={`Remove ${symbol}`}
                  className={clsx('rounded-md p-1.5 text-[#b9e6e1] hover:bg-white/10 hover:text-white', ui.focus)}>
                  <X size={14} aria-hidden="true" />
                </button>
              </li>
            );
          })}
        </ul>
      )}

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search size={15} aria-hidden="true" className={clsx('pointer-events-none absolute left-3 top-1/2 -translate-y-1/2', ui.muted)} />
          {loading ? <Shimmer className="h-10 w-full rounded-lg" /> : (
            <input ref={inputRef} type="text" role="combobox" value={query} disabled={full || error}
              aria-label="Search companies by symbol or name" aria-expanded={showList} aria-controls={listId}
              aria-autocomplete="list" aria-activedescendant={showList && flat[active] ? optionId(flat[active].symbol) : undefined}
              placeholder={error ? 'Company list unavailable' : full ? `Max ${MAX_SYMBOLS} companies` : 'Search by symbol or name…'}
              onChange={(e) => { setQuery(e.target.value); setActive(0); setOpen(true); }}
              onFocus={() => setOpen(true)} onClick={() => setOpen(true)} onKeyDown={onKeyDown}
              className={clsx(ui.input, ui.focus, 'h-10 w-full pl-9 pr-3 disabled:cursor-not-allowed disabled:opacity-60')} />
          )}
          {showList && (
            <div id={listId} role="listbox" aria-label="Companies"
              className="absolute left-0 right-0 top-full z-40 mt-1 max-h-80 overflow-y-auto rounded-xl border border-white/[0.08] bg-[#1a1d24] p-1 shadow-2xl">
              {flat.length === 0 ? (
                <p className={clsx('px-3 py-4 text-center text-xs', ui.muted)}>No companies match.</p>
              ) : groups.map(([name, list]) => (
                <div key={name} role="group" aria-label={name}>
                  <p className={clsx('px-3 pb-1 pt-2 text-[10px] font-bold uppercase tracking-wide', ui.muted)}>{name}</p>
                  {list.map((c) => {
                    const isActive = flat[active]?.symbol === c.symbol;
                    return (
                      <div key={c.symbol} id={optionId(c.symbol)} role="option" aria-selected={isActive}
                        onMouseDown={(e) => { e.preventDefault(); add(c.symbol); }}
                        onMouseEnter={() => setActive(flat.indexOf(c))}
                        className={clsx('flex cursor-pointer items-baseline gap-2 rounded-lg px-3 py-2 text-sm',
                          isActive ? 'bg-[#0f3b3b] text-white' : 'text-[#d1d5db]')}>
                        <span className="w-20 shrink-0 font-semibold">{c.symbol}</span>
                        <span className={clsx('truncate text-xs', isActive ? 'text-[#b9e6e1]' : ui.muted)}>{c.name}</span>
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>
          )}
        </div>

        <label className="flex items-center gap-2 text-xs text-[#b4bcc8]">
          <span className="sr-only sm:not-sr-only">Sector</span>
          <select value={sector} onChange={(e) => { setSector(e.target.value); setActive(0); }}
            disabled={loading || error} aria-label="Filter by sector"
            className={clsx(ui.input, ui.focus, 'h-10 min-w-[11rem] px-3 [color-scheme:dark]')}>
            <option value="">All sectors</option>
            {sectors.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </label>

        <button type="button" onClick={compareWithinSector} disabled={!lastSector || full || sameSectorLeft === 0}
          title={lastSector ? (sameSectorLeft ? `Show other ${lastSector} companies` : `No other ${lastSector} companies`) : 'Select a company first'}
          className={clsx('inline-flex h-10 items-center justify-center gap-2 rounded-lg border px-3 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50',
            ui.chip, ui.focus)}>
          <Layers size={15} aria-hidden="true" />
          {lastSector ? `Compare within ${lastSector}` : 'Compare within sector'}
          {lastSector && sameSectorLeft > 0 && <span className={clsx('text-xs', ui.muted)}>({sameSectorLeft})</span>}
        </button>
      </div>

      <p className={clsx('text-xs', ui.muted)} aria-live="polite">
        {full ? `Max ${MAX_SYMBOLS} companies. Remove one to add another.`
          : `${selected.length} of ${MAX_SYMBOLS} selected · pick at least ${MIN_SYMBOLS} · ${companies.length} tracked companies available`}
      </p>
    </section>
  );
}
