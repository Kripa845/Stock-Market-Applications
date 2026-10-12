// Display formatting for the raw numbers returned by /api/market/.
// The API never sends display strings; crore (1e7) / lakh (1e5) are applied here.

const CRORE = 1e7;
const LAKH = 1e5;

const toNumber = (value: number | string | null | undefined) =>
  value === null || value === undefined || value === '' ? null : Number(value);

/** 3.24 Cr, 11.79 L, or the plain figure below a lakh. */
export function formatNprCompact(value: number | string | null | undefined, digits = 2): string {
  const n = toNumber(value);
  if (n === null || Number.isNaN(n)) return '—';
  const abs = Math.abs(n);
  if (abs >= CRORE) return `${(n / CRORE).toFixed(digits)} Cr`;
  if (abs >= LAKH) return `${(n / LAKH).toFixed(digits)} L`;
  return n.toLocaleString('en-IN', { maximumFractionDigits: 0 });
}

/** Shares / counts with Indian digit grouping (5,73,825). */
export function formatCount(value: number | string | null | undefined): string {
  const n = toNumber(value);
  return n === null || Number.isNaN(n) ? '—' : n.toLocaleString('en-IN', { maximumFractionDigits: 0 });
}

export function formatPrice(value: number | string | null | undefined): string {
  const n = toNumber(value);
  return n === null || Number.isNaN(n) ? '—' : n.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/** +1.25% / -0.41%; "—" when there is no previous close to compare with. */
export function formatPct(value: number | string | null | undefined, digits = 2): string {
  const n = toNumber(value);
  if (n === null || Number.isNaN(n)) return '—';
  return `${n > 0 ? '+' : ''}${n.toFixed(digits)}%`;
}

export function changeTone(value: number | string | null | undefined): 'up' | 'down' | 'flat' {
  const n = toNumber(value);
  if (n === null || Number.isNaN(n) || n === 0) return 'flat';
  return n > 0 ? 'up' : 'down';
}

export function formatTradeDate(iso: string | null | undefined): string {
  if (!iso) return '—';
  return new Date(`${iso}T00:00:00`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}
