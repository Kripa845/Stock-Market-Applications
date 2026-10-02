import { registerIndicator, type KLineData } from 'klinecharts';
import type { IndicatorDef, IndicatorResult } from '../../api/marketIntelligence';

// Turns a server registry entry into a KLineCharts indicator template named `REG_<id>`.
// Values are calculated on the server; the template only reads them from `extendData`,
// keyed by bar timestamp, so the chart never recalculates anything itself.

export interface RegistrySeries {
  byTs: Record<number, Record<string, number>>;
  rows?: { low: number; high: number; volume: number }[];
}

const PALETTE = ['#F59E0B', '#3B82F6', '#A855F7', '#EC4899', '#14B8A6', '#F97316', '#84CC16', '#06B6D4',
  '#EAB308', '#6366F1', '#EF4444', '#22C55E'];
const UP = '#22C55E';
const DOWN = '#EF4444';
const REF = '#94A3B8';

export const templateName = (id: string) => `REG_${id}`;

/** Colour used for an indicator's i-th output; shared with the picker's swatches. */
export const outputColor = (kind: string, i: number) => (kind === 'bar' ? UP : PALETTE[i % PALETTE.length]);

/** Converts an API result into per-timestamp rows, dropping nulls so lines break during warm-up. */
export function toSeries(dates: string[], result: IndicatorResult): RegistrySeries {
  const byTs: RegistrySeries['byTs'] = {};
  const outputs = result.outputs ?? {};
  dates.forEach((date, i) => {
    const [y, m, d] = date.split('-').map(Number);
    const row: Record<string, number> = {};
    for (const [key, values] of Object.entries(outputs)) {
      const v = values[i];
      if (typeof v === 'number' && Number.isFinite(v)) row[key] = v;
    }
    byTs[Date.UTC(y, m - 1, d)] = row;
  });
  return { byTs, rows: result.extra?.rows };
}

const registered = new Set<string>();

type Row = Record<string, number>;
type Ctx = CanvasRenderingContext2D;

export function ensureRegistered(def: IndicatorDef) {
  const name = templateName(def.id);
  if (registered.has(name)) return name;
  registered.add(name);

  const figures: any[] = def.outputs.map((output, i) => {
    const color = outputColor(output.kind, i);
    if (output.kind === 'bar') {
      return {
        key: output.key, title: `${output.label}: `, type: 'bar', baseValue: 0,
        styles: ({ data }: { data: { current?: Row } }) => {
          const row = data.current ?? {};
          const sign = def.color_by ? row[def.color_by] : row[output.key];
          return { color: (sign ?? 0) >= 0 ? UP : DOWN };
        },
      };
    }
    if (output.kind === 'dot') {
      return {
        key: output.key, title: `${output.label}: `, type: 'circle',
        styles: () => ({ style: 'fill', color, borderColor: color }),
      };
    }
    return { key: output.key, title: `${output.label}: `, type: 'line', styles: () => ({ color }) };
  });
  def.ref_lines.forEach((_, i) => figures.push({
    key: `__ref${i}`, type: 'line',  // no title: drawn, but kept out of the legend
    styles: () => ({ color: REF, style: 'dashed', dashedValue: [3, 3], size: 1 }),
  }));

  const hasDraw = def.fill.length === 2 || def.id === 'volume_profile';

  registerIndicator<Row>({
    name,
    shortName: def.name,
    series: def.display === 'overlay' ? 'price' : 'normal',
    precision: def.id === 'volume' || def.id === 'obv' || def.id === 'ad' ? 0 : 4,
    shouldFormatBigNumber: true,
    minValue: def.value_range.length === 2 ? def.value_range[0] : null,
    maxValue: def.value_range.length === 2 ? def.value_range[1] : null,
    figures,
    calc: (list: KLineData[], indicator: any) => {
      const byTs: RegistrySeries['byTs'] = indicator.extendData?.byTs ?? {};
      return list.map((bar) => {
        const row: Row = { ...(byTs[bar.timestamp] ?? {}) };
        def.ref_lines.forEach((level, i) => { row[`__ref${i}`] = level; });
        return row;
      });
    },
    draw: hasDraw
      ? ({ ctx, chart, indicator, bounding, xAxis, yAxis }: any) => {
        const range = chart.getVisibleRange();
        const result: Row[] = indicator.result ?? [];
        if (def.fill.length === 2) fillBetween(ctx, result, range, xAxis, yAxis, def.fill[0], def.fill[1]);
        if (def.id === 'volume_profile') drawProfile(ctx, indicator.extendData?.rows ?? [], bounding, yAxis);
        return false;  // still draw the normal figures on top
      }
      : null,
  } as any);
  return name;
}

// Shades between two outputs (the Ichimoku cloud): green where a >= b, red where a < b.
function fillBetween(ctx: Ctx, result: Row[], range: { from: number; to: number }, xAxis: any, yAxis: any,
  a: string, b: string) {
  let segment: { x: number; ya: number; yb: number; up: boolean }[] = [];
  const flush = () => {
    if (segment.length > 1) {
      ctx.beginPath();
      segment.forEach((p, i) => (i ? ctx.lineTo(p.x, p.ya) : ctx.moveTo(p.x, p.ya)));
      [...segment].reverse().forEach((p) => ctx.lineTo(p.x, p.yb));
      ctx.closePath();
      ctx.fillStyle = segment[0].up ? 'rgba(34,197,94,0.15)' : 'rgba(239,68,68,0.15)';
      ctx.fill();
    }
    segment = [];
  };
  for (let i = range.from; i < range.to; i++) {
    const row = result[i];
    if (!row || row[a] === undefined || row[b] === undefined) { flush(); continue; }
    const up = row[a] >= row[b];
    if (segment.length && segment[0].up !== up) flush();
    segment.push({ x: xAxis.convertToPixel(i), ya: yAxis.convertToPixel(row[a]), yb: yAxis.convertToPixel(row[b]), up });
  }
  flush();
}

// Horizontal volume-at-price bars along the right edge, up to a quarter of the pane width.
function drawProfile(ctx: Ctx, rows: { low: number; high: number; volume: number }[], bounding: any, yAxis: any) {
  const max = Math.max(0, ...rows.map((r) => r.volume));
  if (!max) return;
  const maxWidth = bounding.width * 0.25;
  ctx.fillStyle = 'rgba(59,130,246,0.25)';
  for (const r of rows) {
    const top = yAxis.convertToPixel(r.high);
    const bottom = yAxis.convertToPixel(r.low);
    const width = (r.volume / max) * maxWidth;
    ctx.fillRect(bounding.width - width, top, width, Math.max(1, bottom - top - 1));
  }
}
