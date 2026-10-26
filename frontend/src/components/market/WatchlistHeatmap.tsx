import { useEffect, useMemo, useRef, useState, type MouseEvent } from 'react';
import { hierarchy, treemap, treemapSquarify } from 'd3-hierarchy';
import { scaleLinear } from 'd3-scale';
import Section from '../common/Section';
import { useHeatmap } from '../../hooks/useHeatmap';
import type { HeatmapCompany, HeatmapSector } from '../../api/market';
import { formatCount, formatNprArab, formatNprCompact, formatPct, formatPrice } from './format';

// Treemap of the tracked companies grouped by sector: area from market cap, colour from
// the day's change (Backend services/heatmap.py). Not NEPSE's official heatmap.

/** Colour saturates at ±this %. NEPSE's daily circuit is 10%, but most days move far less. */
export const HEATMAP_CLAMP_PCT = 5;
const NULL_FILL = '#3A4150';
const SECTOR_HEADER_PX = 18;
const CHAR_PX = 6.6;       // rough width of one 11px character, to truncate SVG text

const fill = scaleLinear<string>()
  .domain([-HEATMAP_CLAMP_PCT, 0, HEATMAP_CLAMP_PCT])
  .range(['#B91C1C', '#4B5563', '#15803D'])
  .clamp(true);

type SizeMode = 'market_cap' | 'sqrt' | 'equal';
const SIZE_MODES: { value: SizeMode; label: string }[] = [
  { value: 'market_cap', label: 'Market cap' },
  { value: 'sqrt', label: '√ Market cap' },
  { value: 'equal', label: 'Equal' },
];

interface Node { sector?: HeatmapSector; company?: HeatmapCompany; children?: Node[] }
interface Hover { company: HeatmapCompany; sector: HeatmapSector; x: number; y: number }

const num = (value: number | string | null | undefined) =>
  value === null || value === undefined || value === '' ? null : Number(value);

function fit(text: string, width: number) {
  const chars = Math.floor((width - 8) / CHAR_PX);
  if (chars >= text.length) return text;
  return chars >= 3 ? `${text.slice(0, chars - 1)}…` : '';
}

function formatNpt(iso: string | null) {
  if (!iso) return null;
  return new Date(iso).toLocaleString('en-GB', {
    timeZone: 'Asia/Kathmandu', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false,
  });
}

function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const element = ref.current;
    if (!element) return undefined;
    const observer = new ResizeObserver(([entry]) => setWidth(Math.floor(entry.contentRect.width)));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return [ref, width] as const;
}

export default function WatchlistHeatmap() {
  const { data, loading, error, reload } = useHeatmap();
  const [mode, setMode] = useState<SizeMode>('market_cap');
  const [hover, setHover] = useState<Hover | null>(null);
  const [boxRef, width] = useWidth<HTMLDivElement>();
  const height = Math.round(Math.min(560, Math.max(320, width * 0.55)));

  const layout = useMemo(() => {
    const sectors = data?.sectors ?? [];
    if (!width || sectors.length === 0) return null;
    // A company without listed shares still gets a tile, at the smallest known cap.
    const caps = sectors.flatMap((s) => s.companies.map((c) => num(c.market_cap) ?? 0)).filter((v) => v > 0);
    const fallback = caps.length ? Math.min(...caps) : 1;
    const size = (company: HeatmapCompany) => {
      const cap = num(company.market_cap) || fallback;
      return mode === 'equal' ? 1 : mode === 'sqrt' ? Math.sqrt(cap) : cap;
    };
    const root = hierarchy<Node>({
      children: sectors.map((sector) => ({ sector, children: sector.companies.map((company) => ({ sector, company })) })),
    })
      .sum((node) => (node.company ? size(node.company) : 0))
      .sort((a, b) => (b.value ?? 0) - (a.value ?? 0));
    return treemap<Node>()
      .size([width, height])
      .tile(treemapSquarify)
      .paddingInner(2)
      .paddingOuter(1)
      .paddingTop((node) => (node.depth === 1 ? SECTOR_HEADER_PX : 0))
      .round(true)(root);
  }, [data, width, height, mode]);

  const track = (event: MouseEvent, company: HeatmapCompany, sector: HeatmapSector) => {
    const box = boxRef.current?.getBoundingClientRect();
    if (box) setHover({ company, sector, x: event.clientX - box.left, y: event.clientY - box.top });
  };

  const updated = formatNpt(data?.last_updated ?? null);
  const missing = data?.missing_shares ?? [];

  return (
    <Section
      title="Watchlist Heatmap"
      subtitle={`Your ${data?.tracked_count ?? ''} tracked companies by sector · colour: today's change (±${HEATMAP_CLAMP_PCT}% scale) · live NEPSE feed, unofficial until the close`}
      action={(
        <div className="flex gap-1" role="group" aria-label="Tile size">
          {SIZE_MODES.map(({ value, label }) => (
            <button key={value} onClick={() => setMode(value)}
              className={`rounded px-2 py-1 text-xs ${mode === value ? 'bg-accent text-white' : 'text-text-secondary hover:bg-blue-500/10'}`}>
              {label}
            </button>
          ))}
        </div>
      )}
    >
      <div className="card space-y-3">
        {error && (
          <p className="text-sm text-down">
            Unable to load the heatmap.{' '}
            <button onClick={() => reload()} className="underline">Retry</button>
          </p>
        )}
        {loading && !data && <p className="text-sm text-text-secondary">Loading heatmap...</p>}
        {data?.reason && <p className="text-sm text-text-secondary">{data.reason}</p>}

        <div ref={boxRef} className="relative w-full" onMouseLeave={() => setHover(null)}>
          {layout && (
            <svg width={width} height={height} className="block text-text-primary" role="img" aria-label="Watchlist heatmap">
              {layout.children?.map((sectorNode) => {
                const sector = sectorNode.data.sector!;
                const w = sectorNode.x1 - sectorNode.x0;
                const change = num(sector.change_pct);
                const label = fit(`${sector.name}${change === null ? '' : `  ${formatPct(change)}`}`, w);
                return (
                  <g key={sector.name}>
                    {label && (
                      <text x={sectorNode.x0 + 3} y={sectorNode.y0 + 13} fontSize={11} fontWeight={600} fill="currentColor">
                        {label}
                      </text>
                    )}
                    {sectorNode.children?.map((leaf) => {
                      const company = leaf.data.company!;
                      const tw = leaf.x1 - leaf.x0;
                      const th = leaf.y1 - leaf.y0;
                      const pct = num(company.change_pct);
                      const cx = leaf.x0 + tw / 2;
                      const lines = [
                        th >= 22 && tw >= 34 ? { text: fit(company.symbol, tw), size: 12, weight: 700 } : null,
                        th >= 38 && tw >= 50 ? { text: pct === null ? '—' : formatPct(pct), size: 11, weight: 500 } : null,
                        th >= 54 && tw >= 62 ? { text: formatPrice(company.ltp), size: 10, weight: 400 } : null,
                      ].filter((line): line is { text: string; size: number; weight: number } => line !== null && line.text !== '');
                      const top = leaf.y0 + th / 2 - ((lines.length - 1) * 14) / 2;
                      return (
                        <g key={company.symbol}
                          onMouseMove={(event) => track(event, company, sector)}
                          className="cursor-default">
                          <rect x={leaf.x0} y={leaf.y0} width={tw} height={th} rx={2}
                            fill={pct === null ? NULL_FILL : fill(pct)}
                            stroke={hover?.company.symbol === company.symbol ? '#FFFFFF' : 'none'} strokeWidth={1.5} />
                          {lines.map((line, i) => (
                            <text key={i} x={cx} y={top + i * 14} dy="0.35em" textAnchor="middle"
                              fontSize={line.size} fontWeight={line.weight} fill="#FFFFFF" pointerEvents="none"
                              className="font-mono">
                              {line.text}
                            </text>
                          ))}
                        </g>
                      );
                    })}
                  </g>
                );
              })}
            </svg>
          )}

          {hover && (
            <div className="pointer-events-none absolute z-10 w-60 rounded-md border border-bg-border bg-bg-elevated p-3 text-xs shadow-lg"
              style={{
                left: Math.min(hover.x + 14, Math.max(0, width - 244)),
                top: hover.y + 14 > height - 150 ? Math.max(0, hover.y - 160) : hover.y + 14,
              }}>
              <p className="font-semibold text-text-primary">{hover.company.name}</p>
              <p className="mb-2 text-text-muted">{hover.company.symbol} · {hover.sector.name}</p>
              <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 font-mono">
                <dt className="text-text-muted">LTP</dt><dd className="text-right text-text-primary">Rs {formatPrice(hover.company.ltp)}</dd>
                <dt className="text-text-muted">Change</dt>
                <dd className={`text-right ${(num(hover.company.change_pct) ?? 0) > 0 ? 'text-up' : (num(hover.company.change_pct) ?? 0) < 0 ? 'text-down' : 'text-text-primary'}`}>
                  {formatPct(hover.company.change_pct)}
                </dd>
                <dt className="text-text-muted">Prev close</dt><dd className="text-right text-text-primary">{formatPrice(hover.company.prev_close)}</dd>
                <dt className="text-text-muted">Market cap</dt><dd className="text-right text-text-primary">{formatNprArab(hover.company.market_cap)}</dd>
                <dt className="text-text-muted">Volume</dt><dd className="text-right text-text-primary">{formatCount(hover.company.volume)}</dd>
                <dt className="text-text-muted">Turnover</dt><dd className="text-right text-text-primary">{formatNprCompact(hover.company.turnover)}</dd>
              </dl>
              {!hover.company.traded && <p className="mt-2 text-text-muted">No trade this session (last price shown).</p>}
            </div>
          )}
        </div>

        <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-text-muted">
          <div className="flex items-center gap-2">
            <span>-{HEATMAP_CLAMP_PCT}%</span>
            <span className="h-2 w-28 rounded-sm"
              style={{ background: `linear-gradient(to right, ${fill(-HEATMAP_CLAMP_PCT)}, ${fill(0)}, ${fill(HEATMAP_CLAMP_PCT)})` }} />
            <span>+{HEATMAP_CLAMP_PCT}%</span>
            <span className="ml-2 inline-block h-2 w-3 rounded-sm" style={{ background: NULL_FILL }} />
            <span>no trade / no change data</span>
          </div>
          <span>
            {updated ? `Last updated ${updated} NPT` : ''}
            {data?.stale ? ' · live feed stale' : ''}
            {data && !data.market_open && updated ? ' · market closed' : ''}
          </span>
        </div>
        {missing.length > 0 && (
          <p className="text-[11px] text-text-muted">
            No listed shares set for {missing.join(', ')}: shown at the smallest tile size. Set them in the admin or run
            {' '}<code>manage.py sync_listed_shares</code>.
          </p>
        )}
      </div>
    </Section>
  );
}
