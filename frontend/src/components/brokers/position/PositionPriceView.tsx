// One broker in one stock: stats, then three stacked panels sharing one time axis and one hover
// (recharts syncId) instead of a dual-axis chart: price, running net, and each session's /
// bucket's net.  The "Position vs Price" tab of the Broker Acc / Dist page.
import { useMemo, useState } from 'react';
import { useQuery, keepPreviousData } from '@tanstack/react-query';
import {
  Area, Bar, CartesianGrid, Cell, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts';
import { AlertTriangle, Table2 } from 'lucide-react';

import { formatCount, formatNprCompact, formatPct, formatPrice, formatTradeDate } from '../../market/format';
import { brokerPositionApi, type BrokerPosition, type PositionPoint, type PositionRange } from '../../../api/brokerPosition';
import { compact, signed, toneText } from './format';

// Theme-aware: index.css redefines these for light and dark.
const UP = 'var(--trading-up)';
const DOWN = 'var(--trading-down)';
const POSITION = 'var(--trading-accent)';
const PRICE = 'var(--trading-text-secondary)';
const GRID = 'var(--trading-grid)';
const MUTED = 'var(--trading-muted)';
const AXIS_W = 64;
const SYNC = 'broker-position';

const timeFormat = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Kathmandu', hour: '2-digit', minute: '2-digit', hour12: false });

function pointLabel(point: PositionPoint, mode: BrokerPosition['mode'], long = false) {
  if (mode === 'daily') return long ? formatTradeDate(point.date) : new Date(`${point.date}T00:00:00`).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
  const time = timeFormat.format(new Date(point.time));
  return long ? `${formatTradeDate(point.date)} · ${time}` : time;
}

function Stat({ label, value, hint, tone }: { label: string; value: string; hint?: string; tone?: string }) {
  return (
    <div className="card !p-4">
      <p className="text-[11px] uppercase tracking-wide text-text-muted">{label}</p>
      <p className={`mt-1 font-mono text-xl font-semibold ${tone ?? 'text-text-primary'}`}>{value}</p>
      {hint && <p className="mt-0.5 text-[11px] text-text-muted">{hint}</p>}
    </div>
  );
}

function PositionTooltip({ active, payload, mode }: {
  active?: boolean; payload?: { payload: PositionPoint }[]; mode: BrokerPosition['mode'];
}) {
  const row = payload?.[0]?.payload;
  if (!active || !row) return null;
  return (
    <div className="rounded-lg border border-bg-border bg-bg-elevated px-3 py-2 text-xs shadow-xl">
      <p className="mb-1 text-text-muted">{pointLabel(row, mode, true)}</p>
      <p className="font-mono text-text-primary">Position {signed(row.position)}</p>
      <p className="font-mono text-text-secondary">Bought {formatCount(row.bought)} · sold {formatCount(row.sold)}</p>
      <p className={`font-mono ${toneText(row.net)}`}>Net {signed(row.net)}</p>
      <p className="font-mono text-text-secondary">Price {formatPrice(row.price)}</p>
    </div>
  );
}

function Panel({ title, subtitle, height, children }: { title: string; subtitle: string; height: number; children: React.ReactElement }) {
  return (
    <div>
      <div className="mb-1 flex items-baseline gap-2">
        <h3 className="text-sm font-semibold text-text-primary">{title}</h3>
        <span className="text-[11px] text-text-muted">{subtitle}</span>
      </div>
      <ResponsiveContainer width="100%" height={height}>{children}</ResponsiveContainer>
    </div>
  );
}

// A bar with its data end rounded (top when net bought, bottom when net sold), square at zero.
function NetBar(props: { x?: number; y?: number; width?: number; height?: number; fill?: string; payload?: PositionPoint }) {
  const { x = 0, y = 0, width = 0, height = 0, fill, payload } = props;
  const top = Math.min(y, y + height);
  const h = Math.abs(height);
  if (!h || !width) return null;
  const r = Math.min(4, h, width / 2);
  const up = (payload?.net ?? 0) >= 0;
  const path = up
    ? `M${x},${top + h} V${top + r} Q${x},${top} ${x + r},${top} H${x + width - r} Q${x + width},${top} ${x + width},${top + r} V${top + h} Z`
    : `M${x},${top} V${top + h - r} Q${x},${top + h} ${x + r},${top + h} H${x + width - r} Q${x + width},${top + h} ${x + width},${top + h - r} V${top} Z`;
  return <path d={path} fill={fill} />;
}

function Charts({ data }: { data: BrokerPosition }) {
  const points = data.points;
  const ticks = (value: number) => {
    const point = points[value];
    return point ? pointLabel(point, data.mode) : '';
  };
  // 2D: a dashed line where the second session starts.
  const sessionStart = data.mode === 'intraday'
    ? points.findIndex((p, i) => i > 0 && p.date !== points[i - 1].date)
    : -1;
  const xAxis = (show: boolean) => (
    <XAxis dataKey="index" type="number" domain={[-0.5, points.length - 0.5]} tickFormatter={ticks} hide={!show}
      tick={{ fill: MUTED, fontSize: 11 }} tickLine={false} axisLine={{ stroke: GRID }} minTickGap={28} allowDecimals={false} />
  );
  const yAxis = (format: (v: number) => string, domain?: [string, string]) => (
    <YAxis width={AXIS_W} tickFormatter={format} domain={domain} tick={{ fill: MUTED, fontSize: 11 }} tickLine={false} axisLine={false} />
  );
  const rows = useMemo(() => points.map((p, index) => ({ ...p, index })), [points]);
  const marks = sessionStart > 0 && <ReferenceLine x={sessionStart - 0.5} stroke={MUTED} strokeDasharray="4 4" />;
  const quietTooltip = <Tooltip content={() => null} cursor={{ stroke: MUTED, strokeDasharray: '3 3' }} />;
  const grid = <CartesianGrid vertical={false} stroke={GRID} strokeOpacity={0.35} strokeDasharray="3 3" />;

  return (
    <div className="space-y-4">
      <Panel title="Price" subtitle={data.mode === 'daily' ? 'daily close' : `${data.bucket_minutes}-minute close`} height={150}>
        <ComposedChart data={rows} syncId={SYNC} margin={{ top: 6, right: 8, bottom: 0, left: 0 }}>
          {grid}
          {xAxis(false)}
          {yAxis((v) => formatPrice(v), ['auto', 'auto'])}
          {quietTooltip}
          {marks}
          <Line dataKey="price" stroke={PRICE} strokeWidth={2} dot={false} connectNulls isAnimationActive={false} />
        </ComposedChart>
      </Panel>

      <Panel title={`Broker ${data.broker} running net`} subtitle="bought − sold since the start of the range" height={230}>
        <ComposedChart data={rows} syncId={SYNC} margin={{ top: 6, right: 8, bottom: 0, left: 0 }}>
          {grid}
          {xAxis(false)}
          {yAxis(compact)}
          <Tooltip content={<PositionTooltip mode={data.mode} />} cursor={{ stroke: MUTED, strokeDasharray: '3 3' }} />
          <ReferenceLine y={0} stroke={MUTED} />
          {marks}
          <Area dataKey="position" type="linear" baseValue={0} stroke={POSITION} strokeWidth={2} fill={POSITION} fillOpacity={0.12}
            dot={false} activeDot={{ r: 4 }} isAnimationActive={false} />
        </ComposedChart>
      </Panel>

      <Panel title={data.mode === 'daily' ? 'Net per session' : `Net per ${data.bucket_minutes} minute${data.bucket_minutes === 1 ? '' : 's'}`}
        subtitle="above zero = net bought, below = net sold" height={150}>
        <ComposedChart data={rows} syncId={SYNC} margin={{ top: 6, right: 8, bottom: 0, left: 0 }}>
          {grid}
          {xAxis(true)}
          {yAxis(compact)}
          {quietTooltip}
          <ReferenceLine y={0} stroke={MUTED} />
          {marks}
          <Bar dataKey="net" maxBarSize={18} isAnimationActive={false} shape={NetBar}>
            {rows.map((row) => <Cell key={row.time} fill={row.net >= 0 ? UP : DOWN} />)}
          </Bar>
        </ComposedChart>
      </Panel>
    </div>
  );
}

function DataTable({ data }: { data: BrokerPosition }) {
  return (
    <div className="max-h-[420px] overflow-auto rounded-md border border-bg-border">
      <table className="w-full text-xs">
        <thead className="sticky top-0 bg-bg-elevated text-[11px] uppercase tracking-wide text-text-muted">
          <tr>
            {[data.mode === 'daily' ? 'Session' : 'Time', 'Bought', 'Sold', 'Net', 'Running net', 'Price'].map((h, i) => (
              <th key={h} className={`px-3 py-2 font-medium ${i ? 'text-right' : 'text-left'}`}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {[...data.points].reverse().map((p) => (
            <tr key={p.time} className="table-row font-mono">
              <td className="px-3 py-1.5 text-left font-sans text-text-secondary">{pointLabel(p, data.mode, true)}</td>
              <td className="px-3 py-1.5 text-right text-text-secondary">{formatCount(p.bought)}</td>
              <td className="px-3 py-1.5 text-right text-text-secondary">{formatCount(p.sold)}</td>
              <td className={`px-3 py-1.5 text-right ${toneText(p.net)}`}>{signed(p.net)}</td>
              <td className={`px-3 py-1.5 text-right ${toneText(p.position)}`}>{signed(p.position)}</td>
              <td className="px-3 py-1.5 text-right text-text-secondary">{formatPrice(p.price)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function PositionPriceView({ symbol, broker, range, excludeSelf }: {
  symbol: string; broker: string; range: PositionRange; excludeSelf: boolean;
}) {
  const [showTable, setShowTable] = useState(false);
  const position = useQuery({
    queryKey: ['broker-position', symbol, broker, range, excludeSelf],
    queryFn: () => brokerPositionApi.get({ symbol, broker, range, excludeSelf }),
    enabled: Boolean(symbol && broker),
    placeholderData: keepPreviousData,
  });
  const data = position.data;
  const totals = data?.totals;
  const detail = (position.error as { response?: { data?: { detail?: string } } } | null)?.response?.data?.detail;
  const vsPrice = totals?.avg_buy_price && totals.last_price
    ? ((totals.last_price - totals.avg_buy_price) / totals.avg_buy_price) * 100 : null;

  if (position.error) {
    return (
      <div role="alert" className="flex items-center gap-2 rounded-md border border-down/30 bg-down/10 px-4 py-3 text-sm text-down">
        <AlertTriangle size={15} /> {detail ?? 'Unable to load the broker position.'}
      </div>
    );
  }
  if (!data) return <div className="skeleton h-[520px] rounded-xl" />;
  if (!data.sessions) return <p className="py-10 text-center text-sm text-text-muted">No floorsheet sessions are stored for {symbol}.</p>;

  return (
    <div className={`space-y-5 transition-opacity ${position.isFetching ? 'opacity-60' : ''}`}>
      <p className="text-xs text-text-muted">
        {data.symbol} · {data.sessions} session{data.sessions === 1 ? '' : 's'} · {formatTradeDate(data.start_date)}
        {data.end_date !== data.start_date && ` – ${formatTradeDate(data.end_date)}`}
      </p>
      {totals && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
          <Stat label="Net in range" value={signed(totals.net)} tone={toneText(totals.net)} hint="shares bought − sold" />
          <Stat label="Bought" value={formatCount(totals.bought)} hint={`Rs ${formatNprCompact(totals.buy_value)} · avg ${formatPrice(totals.avg_buy_price)}`} />
          <Stat label="Sold" value={formatCount(totals.sold)} hint={`Rs ${formatNprCompact(totals.sell_value)} · avg ${formatPrice(totals.avg_sell_price)}`} />
          <Stat label="Last price" value={formatPrice(totals.last_price)} hint={vsPrice == null ? undefined : `${formatPct(vsPrice)} vs avg buy`} />
          <Stat label="Share of volume" value={totals.share_of_volume_pct == null ? '—' : `${totals.share_of_volume_pct.toFixed(2)}%`}
            hint={`of ${formatCount(totals.stock_volume)} shares traded`} />
          <Stat label="Active" value={data.mode === 'daily' ? `${totals.active_sessions} / ${data.sessions}` : formatCount(totals.trades)}
            hint={data.mode === 'daily' ? 'sessions with a trade' : 'trades in range'} />
        </div>
      )}
      {data.points.length ? <Charts data={data} /> : (
        <p className="py-10 text-center text-sm text-text-muted">Broker {data.broker} has no timed trades in {data.symbol} in this range.</p>
      )}
      {data.warnings.map((w) => <p key={w} className="flex items-center gap-2 text-xs text-down"><AlertTriangle size={13} /> {w}</p>)}
      <div className="flex justify-end">
        <button type="button" onClick={() => setShowTable((s) => !s)} className="btn-ghost flex items-center gap-2 text-xs">
          <Table2 size={13} /> {showTable ? 'Hide' : 'Show'} data table
        </button>
      </div>
      {showTable && <DataTable data={data} />}
    </div>
  );
}
