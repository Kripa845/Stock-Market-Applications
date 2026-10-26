import { useState } from 'react';
import type { AccumulationRange, AccumulationWindow } from '../../../api/brokerAccumulation';

// 1D / 1W / 1M / 3M (counted in floorsheet sessions) or a custom date range.

const PRESETS: { id: AccumulationWindow; label: string }[] = [
  { id: '1d', label: '1D' }, { id: '1w', label: '1W' }, { id: '1m', label: '1M' }, { id: '3m', label: '3M' },
];

export default function RangeSelector({ value, onChange }: { value: AccumulationRange; onChange: (range: AccumulationRange) => void }) {
  const custom = !('window' in value);
  const [open, setOpen] = useState(custom);
  const [start, setStart] = useState(custom ? value.start_date : '');
  const [end, setEnd] = useState(custom ? value.end_date ?? '' : '');
  const invalid = !start || (end !== '' && end < start);

  const button = (active: boolean) =>
    `rounded-md px-3 py-1 text-xs font-medium transition-colors ${active ? 'bg-accent text-white shadow-sm' : 'text-text-muted hover:text-text-primary'}`;

  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="flex rounded-lg border border-bg-border bg-bg-secondary p-0.5" role="tablist" aria-label="Range">
        {PRESETS.map((preset) => (
          <button
            key={preset.id}
            type="button"
            role="tab"
            aria-selected={!custom && value.window === preset.id}
            onClick={() => { setOpen(false); onChange({ window: preset.id }); }}
            className={button(!custom && value.window === preset.id)}
          >
            {preset.label}
          </button>
        ))}
        <button type="button" role="tab" aria-selected={custom} onClick={() => setOpen((current) => !current)} className={button(custom || open)}>
          Custom
        </button>
      </div>
      {open && (
        <form
          className="flex flex-wrap items-center gap-1.5"
          onSubmit={(event) => { event.preventDefault(); if (!invalid) onChange(end ? { start_date: start, end_date: end } : { start_date: start }); }}
        >
          <input type="date" value={start} onChange={(event) => setStart(event.target.value)} className="input py-1 text-xs" aria-label="From" required />
          <span className="text-xs text-text-muted">to</span>
          <input type="date" value={end} min={start || undefined} onChange={(event) => setEnd(event.target.value)} className="input py-1 text-xs" aria-label="To (optional)" />
          <button type="submit" disabled={invalid} className="btn-primary px-3 py-1 text-xs disabled:opacity-50">Apply</button>
        </form>
      )}
    </div>
  );
}
