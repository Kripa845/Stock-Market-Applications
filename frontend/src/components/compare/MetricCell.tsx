import clsx from 'clsx';
import { AlertTriangle, ArrowDown, ArrowUp, Minus } from 'lucide-react';

import Sparkline from '../common/Sparkline';
import { reasonLabel, type BrokerRow, type CompareDividend, type CompareProfile, type SmaBlock } from '../../api/compare';
import { formatCompactNumber, formatCount, formatPct, formatThousands, formatTradeDate } from '../market/format';
import { getPath, isMissing, toNumber, type RowDef } from './rows';
import { Tip, ui } from './ui';

// One table cell.  A missing value is always "—" with the backend's reason (and note) in a
// tooltip; nothing here knows about particular companies or sectors.

const num = 'font-mono tabular-nums';

function Missing({ row, profile }: { row: RowDef; profile: CompareProfile }) {
  const entry = profile.data_quality?.null_fields.find((f) => f.field === row.path);
  const reason = entry ? reasonLabel(entry.reason) : 'No data';
  return (
    <Tip label={`${row.label} for ${profile.symbol}: not available. ${reason}`}
      content={<><span className="font-semibold">{reason}</span>{entry?.note && <span className="mt-1 block text-[#b4bcc8]">{entry.note}</span>}</>}>
      <span className={clsx(num, ui.muted)}>—</span>
    </Tip>
  );
}

function Signed({ value, digits = 2, suffix = '%' }: { value: unknown; digits?: number; suffix?: string }) {
  const n = toNumber(value) ?? 0;
  const Icon = n > 0 ? ArrowUp : n < 0 ? ArrowDown : Minus;
  return (
    <span className={clsx(num, 'inline-flex items-center gap-0.5', n > 0 ? 'text-up' : n < 0 ? 'text-down' : ui.muted)}>
      <Icon size={12} aria-hidden="true" />
      {suffix === '%' ? formatPct(value as number, digits) : `${n > 0 ? '+' : ''}${formatThousands(n, digits)}`}
    </span>
  );
}

function Compact({ value }: { value: unknown }) {
  return (
    <Tip content={<span className={num}>NPR {formatThousands(value as number)}</span>}>
      <span className={num}>{formatCompactNumber(value as number)}</span>
    </Tip>
  );
}

function Range52({ profile }: { profile: CompareProfile }) {
  const g = profile.general;
  const low = toNumber(g.week52_low)!, high = toNumber(g.week52_high)!, ltp = toNumber(g.ltp)!;
  const pos = high > low ? Math.min(100, Math.max(0, ((ltp - low) / (high - low)) * 100)) : 50;
  return (
    <Tip label={`52-week range ${formatThousands(low)} to ${formatThousands(high)}, LTP ${formatThousands(ltp)}`}
      content={<span className={num}>Low {formatThousands(low)} · LTP {formatThousands(ltp)} · High {formatThousands(high)}<br />LTP is {pos.toFixed(0)}% of the way from low to high</span>}>
      <span className="inline-flex w-36 flex-col gap-1">
        <span className="relative h-1.5 rounded-full bg-white/[0.08]">
          <span className="absolute inset-y-0 left-0 rounded-full bg-[#1f6f6b]" style={{ width: `${pos}%` }} />
          <span className="absolute top-1/2 h-3 w-0.5 -translate-y-1/2 rounded bg-white" style={{ left: `calc(${pos}% - 1px)` }} />
        </span>
        <span className={clsx(num, 'flex justify-between text-[11px]', ui.muted)}>
          <span>{formatThousands(low)}</span><span>{formatThousands(high)}</span>
        </span>
      </span>
    </Tip>
  );
}

function Brokers({ rows, side }: { rows: BrokerRow[]; side: 'buy' | 'sell' }) {
  const max = Math.max(...rows.map((b) => toNumber(b.pct_of_day_volume) ?? 0), 1);
  return (
    <ol className="w-56 space-y-1 text-left" aria-label={side === 'buy' ? 'Top buyers' : 'Top sellers'}>
      {rows.map((b) => {
        const pct = toNumber(b.pct_of_day_volume);
        return (
          <li key={String(b.broker_no)} className="text-xs">
            <span className="flex items-baseline gap-1.5">
              <span className={clsx(num, 'w-6 shrink-0 text-[#e5e7eb]')}>{b.broker_no}</span>
              <Tip content={b.broker_name ?? 'Broker not in the directory'} className="min-w-0 flex-1 truncate">
                <span className={clsx('block truncate', ui.muted)}>{b.broker_name ?? 'Unknown broker'}</span>
              </Tip>
              <span className={clsx(num, 'shrink-0')}>{formatCount(b.quantity)}</span>
              <span className={clsx(num, 'w-12 shrink-0 text-right', side === 'buy' ? 'text-up' : 'text-down')}>
                {pct === null ? '—' : `${pct.toFixed(2)}%`}
              </span>
            </span>
            <span className="mt-0.5 block h-0.5 rounded-full bg-white/[0.05]" aria-hidden="true">
              <span className={clsx('block h-full rounded-full', side === 'buy' ? 'bg-up/70' : 'bg-down/70')}
                style={{ width: `${((pct ?? 0) / max) * 100}%` }} />
            </span>
          </li>
        );
      })}
    </ol>
  );
}

function Dividend({ d }: { d: CompareDividend }) {
  return (
    <span className="inline-flex flex-col items-end gap-0.5">
      <span className={num}>{formatThousands(d.total_pct)}%</span>
      <span className={clsx('text-[11px]', ui.muted)}>
        <span className={num}>{formatThousands(d.cash_pct)}%</span> cash + <span className={num}>{formatThousands(d.bonus_pct)}%</span> bonus
      </span>
      <span className={clsx('text-[11px]', ui.muted)}>FY {d.fiscal_year} · {d.status.replace(/_/g, ' ')}</span>
    </span>
  );
}

function Rsi({ value }: { value: unknown }) {
  const n = toNumber(value)!;
  const state = n > 70 ? 'Overbought' : n < 30 ? 'Oversold' : null;
  return (
    <span className="inline-flex flex-col items-end">
      <span className={clsx(num, n > 70 ? 'text-down' : n < 30 ? 'text-up' : '')}>{n.toFixed(2)}</span>
      {state && <span className={clsx('text-[11px]', n > 70 ? 'text-down' : 'text-up')}>{state}</span>}
    </span>
  );
}

function Macd({ profile }: { profile: CompareProfile }) {
  const t = profile.technicals;
  const bullish = t.macd_label === 'Bullish';
  return (
    <span className="inline-flex flex-col items-end gap-1">
      {t.macd_label && (
        <span className={clsx('inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-semibold',
          bullish ? 'border-up/40 text-up' : 'border-down/40 text-down')}>
          {bullish ? <ArrowUp size={11} aria-hidden="true" /> : <ArrowDown size={11} aria-hidden="true" />}{t.macd_label}
        </span>
      )}
      <span className={clsx(num, 'text-[11px]')}>
        <span className={ui.muted}>MACD </span>{formatThousands(t.macd, 2)}
        <span className={ui.muted}> · Sig </span>{formatThousands(t.macd_signal, 2)}
      </span>
      <span className={clsx(num, 'text-[11px]')}><span className={ui.muted}>Hist </span><Signed value={t.macd_hist} suffix="" /></span>
    </span>
  );
}

function Sma({ block, label }: { block: SmaBlock; label: string }) {
  return (
    <Tip label={`LTP ${block.above ? 'above' : 'below'} ${label} ${formatThousands(block.value)}`}
      content={<span className={num}>{label}: {formatThousands(block.value)}</span>}>
      <span className={clsx('inline-flex items-center gap-1 text-xs font-semibold', block.above ? 'text-up' : 'text-down')}>
        {block.above ? <ArrowUp size={13} aria-hidden="true" /> : <ArrowDown size={13} aria-hidden="true" />}
        {block.above ? 'Above' : 'Below'}
      </span>
    </Tip>
  );
}

export default function MetricCell({ row, profile, best }: { row: RowDef; profile: CompareProfile; best: boolean }) {
  if (profile.error) {
    return <span className="inline-flex items-center gap-1 text-xs text-down"><AlertTriangle size={12} aria-hidden="true" />Error</span>;
  }
  if (isMissing(row, profile)) return <Missing row={row} profile={profile} />;

  const value = getPath(profile, row.path);
  let body: React.ReactNode;
  switch (row.kind) {
    case 'price': body = <span className={num}>{formatThousands(value as number)}</span>; break;
    case 'ratio': body = <span className={num}>{formatThousands(value as number)}</span>; break;
    case 'pct': body = <span className={num}>{formatThousands(value as number)}%</span>; break;
    case 'signedPct': body = <Signed value={value} />; break;
    case 'compact': body = <Compact value={value} />; break;
    case 'count': body = <span className={num}>{(toNumber(value) ?? 0).toLocaleString('en-US')}</span>; break;
    case 'text': body = <span>{String(value)}</span>; break;
    case 'faceValue':
      body = profile.general.face_value_source === 'default_100'
        ? <Tip content="No face value on record; the NEPSE default of 100 is assumed."><span className={num}>{formatThousands(value as number)} <span className={ui.muted}>(assumed)</span></span></Tip>
        : <span className={num}>{formatThousands(value as number)}</span>;
      break;
    case 'range52': body = <Range52 profile={profile} />; break;
    case 'brokerDate': {
      const priceDate = profile.data_quality.price_as_of;
      const differs = priceDate && priceDate !== value;
      body = (
        <span className="inline-flex flex-col items-end">
          <span>{formatTradeDate(value as string)}</span>
          {differs && (
            <Tip content={`Brokers are for ${formatTradeDate(value as string)}; prices are for ${formatTradeDate(priceDate)}.`}>
              <span className="inline-flex items-center gap-1 text-[11px] text-amber-300"><AlertTriangle size={11} aria-hidden="true" />Differs from price date</span>
            </Tip>
          )}
        </span>
      );
      break;
    }
    case 'brokers': body = <Brokers rows={value as BrokerRow[]} side={row.side ?? 'buy'} />; break;
    case 'dividend': body = <Dividend d={value as CompareDividend} />; break;
    case 'sparkline': {
      const series = (value as unknown[]).map((v) => toNumber(v) ?? 0);
      body = <Sparkline data={series} width={96} height={26} positive={series[series.length - 1] >= series[0]} />;
      break;
    }
    case 'rsi': body = <Rsi value={value} />; break;
    case 'macd': body = <Macd profile={profile} />; break;
    case 'sma': body = <Sma block={value as SmaBlock} label={row.label} />; break;
    default: body = <span className={num}>{formatCompactNumber(value as number)}</span>;
  }
  return best ? (
    <span className="inline-flex items-center gap-1 rounded-md bg-[#0f3b3b] px-1.5 py-0.5 ring-1 ring-[#1f6f6b]" title="Best among selected">
      <span className="sr-only">Best: </span>{body}
    </span>
  ) : body;
}
