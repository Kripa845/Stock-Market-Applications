import type { BrokerRow, CompareDividend, CompareProfile, SmaBlock } from '../../api/compare';
import { formatCompactNumber, formatCount, formatPct, formatThousands, formatTradeDate } from '../market/format';

// One entry per table row.  `path` is where the value sits in a /api/compare/ profile and is
// also the key the backend uses in data_quality.null_fields, so missing values get their
// reason automatically.  Adding a row is one line here; a new `kind` also needs a renderer
// in MetricCell.tsx.
//
// Not returned by the API yet, so deliberately absent (add one line each when they are):
//   { id: 'alpha', label: 'Alpha', path: 'technicals.alpha', kind: 'ratio', better: 'higher' },
//   { id: 'beta', label: 'Beta', path: 'technicals.beta', kind: 'ratio' },
//   { id: 'sharpe', label: 'Sharpe ratio', path: 'technicals.sharpe', kind: 'ratio', better: 'higher' },
//   { id: 'regime', label: 'Trending / mean-reverting', path: 'technicals.regime', kind: 'text' },
//   a "Trading signals" section, and volume trend.

export type Better = 'higher' | 'lower';
export type CellKind =
  | 'price' | 'signedPct' | 'pct' | 'ratio' | 'compact' | 'count' | 'text' | 'faceValue'
  | 'range52' | 'brokerDate' | 'brokers' | 'dividend' | 'sparkline' | 'rsi' | 'macd' | 'sma';

export interface RowDef {
  id: string;
  label: string;
  path: string;
  kind: CellKind;
  /** Which end is "best" for highlighting; omit for rows where neither is. */
  better?: Better;
  tooltip?: string;
  side?: 'buy' | 'sell';
}

export interface SectionDef { id: string; title: string; rows: RowDef[] }

export const SECTIONS: SectionDef[] = [
  {
    id: 'general', title: 'General', rows: [
      { id: 'ltp', label: 'LTP', path: 'general.ltp', kind: 'price', tooltip: 'Latest crawled closing price' },
      { id: 'change', label: 'Change %', path: 'general.change_pct', kind: 'signedPct', tooltip: 'Session change against the previous close (adjusted on book-closure days)' },
      { id: 'range52', label: '52-week range', path: 'general.week52_low', kind: 'range52', tooltip: 'Where the LTP sits between the 52-week low and high' },
      { id: 'mcap', label: 'Market cap', path: 'general.market_cap', kind: 'compact', tooltip: 'LTP × listed shares' },
      { id: 'paidup', label: 'Paid-up capital', path: 'general.paid_up_capital', kind: 'compact', tooltip: 'Listed shares × face value' },
      { id: 'reserve', label: 'Reserve & surplus', path: 'general.reserve_surplus', kind: 'compact', tooltip: 'Book value × listed shares − paid-up capital' },
      { id: 'shares', label: 'Listed shares', path: 'general.listed_shares', kind: 'count' },
      { id: 'face', label: 'Face value', path: 'general.face_value', kind: 'faceValue' },
      { id: 'eps', label: 'EPS (TTM)', path: 'general.eps_ttm', kind: 'price', better: 'higher', tooltip: 'Trailing twelve-month earnings per share' },
    ],
  },
  {
    id: 'brokers', title: 'Broker activity', rows: [
      { id: 'brokerDate', label: 'Broker session', path: 'general.brokers_date', kind: 'brokerDate' },
      { id: 'buyers', label: 'Top 5 buyers', path: 'general.top_buy_brokers', kind: 'brokers', side: 'buy', tooltip: 'Quantity bought and share of the day’s volume' },
      { id: 'sellers', label: 'Top 5 sellers', path: 'general.top_sell_brokers', kind: 'brokers', side: 'sell', tooltip: 'Quantity sold and share of the day’s volume' },
    ],
  },
  {
    id: 'fundamentals', title: 'Fundamentals', rows: [
      { id: 'period', label: 'Report period', path: 'fundamentals.report_period', kind: 'text' },
      { id: 'pe', label: 'P/E', path: 'fundamentals.pe', kind: 'ratio', better: 'lower', tooltip: 'LTP / EPS (TTM)' },
      { id: 'pb', label: 'P/B', path: 'fundamentals.pb', kind: 'ratio', better: 'lower', tooltip: 'LTP / book value per share' },
      { id: 'roe', label: 'ROE', path: 'fundamentals.roe', kind: 'pct', better: 'higher', tooltip: 'EPS / book value per share' },
      { id: 'roa', label: 'ROA', path: 'fundamentals.roa', kind: 'pct', better: 'higher' },
      { id: 'ps', label: 'P/S', path: 'fundamentals.ps', kind: 'ratio', better: 'lower' },
      { id: 'de', label: 'Debt / equity', path: 'fundamentals.debt_equity', kind: 'ratio', better: 'lower' },
      { id: 'peg', label: 'PEG', path: 'fundamentals.peg', kind: 'ratio', better: 'lower' },
      { id: 'yoy', label: 'YoY profit growth', path: 'fundamentals.yoy_profit_growth', kind: 'signedPct', better: 'higher' },
      { id: 'trend', label: 'Earnings trend (5Q)', path: 'fundamentals.earning_trend_5q', kind: 'sparkline' },
      { id: 'dividend', label: 'Latest dividend', path: 'fundamentals.dividend', kind: 'dividend' },
      { id: 'yield', label: 'Dividend yield', path: 'fundamentals.dividend_yield', kind: 'pct', better: 'higher', tooltip: '(Cash % + bonus %) × face value / LTP' },
    ],
  },
  {
    id: 'technicals', title: 'Technicals', rows: [
      { id: 'rsi', label: 'RSI (14)', path: 'technicals.rsi', kind: 'rsi', tooltip: 'Above 70 overbought, below 30 oversold' },
      { id: 'macd', label: 'MACD (12, 26, 9)', path: 'technicals.macd', kind: 'macd', tooltip: 'MACD line, signal line and histogram' },
      { id: 'sma50', label: 'SMA 50', path: 'technicals.sma50', kind: 'sma', tooltip: 'LTP above or below the 50-session average' },
      { id: 'sma200', label: 'SMA 200', path: 'technicals.sma200', kind: 'sma', tooltip: 'LTP above or below the 200-session average' },
    ],
  },
];

export function getPath(profile: CompareProfile, path: string): unknown {
  return path.split('.').reduce<unknown>(
    (node, key) => (node && typeof node === 'object' ? (node as Record<string, unknown>)[key] : undefined),
    profile,
  );
}

export const toNumber = (value: unknown) => {
  if (value === null || value === undefined || value === '') return null;
  const n = Number(value);
  return Number.isNaN(n) ? null : n;
};

/** True when this row has nothing to show for the company. */
export function isMissing(row: RowDef, profile: CompareProfile): boolean {
  if (profile.error) return true;
  const value = getPath(profile, row.path);
  if (value === null || value === undefined) return true;
  if (Array.isArray(value)) return value.length === 0;
  if (row.kind === 'range52') return toNumber(profile.general.week52_high) === null || toNumber(profile.general.ltp) === null;
  return false;
}

/** Number used to pick the best value, or null when the row isn't comparable. */
export function comparable(row: RowDef, profile: CompareProfile): number | null {
  if (!row.better || isMissing(row, profile)) return null;
  return toNumber(getPath(profile, row.path));
}

/** Plain-text cell for the CSV export. */
export function cellText(row: RowDef, profile: CompareProfile): string {
  if (profile.error) return 'error';
  if (isMissing(row, profile)) return '—';
  const value = getPath(profile, row.path);
  const g = profile.general;
  switch (row.kind) {
    case 'price': return formatThousands(value as number);
    case 'ratio': return formatThousands(value as number);
    case 'pct': return `${formatThousands(value as number)}%`;
    case 'signedPct': return formatPct(value as number);
    case 'compact': return formatThousands(value as number);
    case 'count': return formatCount(value as number);
    case 'text': return String(value);
    case 'faceValue': return `${formatThousands(value as number)}${g.face_value_source === 'default_100' ? ' (assumed)' : ''}`;
    case 'range52': return `${formatThousands(g.week52_low)} – ${formatThousands(g.week52_high)}`;
    case 'brokerDate': return formatTradeDate(value as string);
    case 'brokers': return (value as BrokerRow[])
      .map((b) => `${b.broker_no} ${b.broker_name ?? ''} ${b.quantity} (${formatThousands(b.pct_of_day_volume)}%)`.trim()).join('; ');
    case 'dividend': {
      const d = value as CompareDividend;
      return `${d.fiscal_year}: cash ${formatThousands(d.cash_pct)}% + bonus ${formatThousands(d.bonus_pct)}% = ${formatThousands(d.total_pct)}% (${d.status})`;
    }
    case 'sparkline': return (value as unknown[]).map((v) => formatThousands(v as number)).join(' / ');
    case 'rsi': return formatThousands(value as number);
    case 'macd': {
      const t = profile.technicals;
      return `${formatThousands(t.macd, 4)} / signal ${formatThousands(t.macd_signal, 4)} / hist ${formatThousands(t.macd_hist, 4)} (${t.macd_label ?? '—'})`;
    }
    case 'sma': {
      const s = value as SmaBlock;
      return `${s.above ? 'Above' : 'Below'} ${formatThousands(s.value)}`;
    }
    default: return formatCompactNumber(value as number);
  }
}
