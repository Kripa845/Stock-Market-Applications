import { registerOverlay, type OverlayFigure } from 'klinecharts';

// Drawing tools the chart library does not ship with. Registered once, globally, like customIndicators.ts.
// totalStep is "points + 1": a two-point tool has totalStep 3.

const BLUE = '#2962FF';
const FILL = 'rgba(41, 98, 255, 0.12)';
const UP = '#22C55E';
const DOWN = '#EF4444';

type Coord = { x: number; y: number };

const label = (at: Coord, text: string, baseline: 'bottom' | 'top' = 'bottom'): OverlayFigure => ({
  type: 'text',
  attrs: { x: at.x, y: baseline === 'bottom' ? at.y - 6 : at.y + 6, text, align: 'center', baseline },
  styles: { color: BLUE, backgroundColor: 'transparent', borderSize: 0, size: 12, weight: 'bold' },
  ignoreEvent: true,
});

const path = (coordinates: Coord[]): OverlayFigure => ({ type: 'line', attrs: { coordinates } });

const fill = (coordinates: Coord[]): OverlayFigure => ({
  type: 'polygon', attrs: { coordinates }, styles: { style: 'fill', color: FILL },
});

// Peaks get their label above, troughs below, judged against the neighbouring points.
const isPeak = (c: Coord[], i: number) => [c[i - 1], c[i + 1]].filter(Boolean).every((n) => c[i].y <= n.y);

const labelled = (c: Coord[], names: string[]) =>
  c.map((p, i) => label(p, names[i] ?? '', isPeak(c, i) ? 'bottom' : 'top'));

// ─── Shapes ───────────────────────────────────────────────────────────────────
registerOverlay({
  name: 'rectShape',
  totalStep: 3,
  needDefaultPointFigure: true,
  createPointFigures: ({ coordinates: c }) => {
    if (c.length < 2) return [];
    return {
      type: 'rect',
      attrs: { x: Math.min(c[0].x, c[1].x), y: Math.min(c[0].y, c[1].y), width: Math.abs(c[1].x - c[0].x), height: Math.abs(c[1].y - c[0].y) },
      styles: { style: 'stroke_fill', color: FILL, borderColor: BLUE, borderSize: 1 },
    };
  },
});

registerOverlay({
  name: 'circleShape',
  totalStep: 3,
  needDefaultPointFigure: true,
  createPointFigures: ({ coordinates: c }) => {
    if (c.length < 2) return [];
    return {
      type: 'circle',
      attrs: { x: c[0].x, y: c[0].y, r: Math.hypot(c[1].x - c[0].x, c[1].y - c[0].y) },
      styles: { style: 'stroke_fill', color: FILL, borderColor: BLUE, borderSize: 1 },
    };
  },
});

registerOverlay({
  name: 'triangleShape',
  totalStep: 4,
  needDefaultPointFigure: true,
  createPointFigures: ({ coordinates: c }) => {
    if (c.length < 2) return [];
    if (c.length === 2) return path(c);
    return { type: 'polygon', attrs: { coordinates: c }, styles: { style: 'stroke_fill', color: FILL, borderColor: BLUE, borderSize: 1 } };
  },
});

// ─── Patterns ─────────────────────────────────────────────────────────────────
registerOverlay({
  name: 'xabcdPattern',
  totalStep: 6,
  needDefaultPointFigure: true,
  createPointFigures: ({ coordinates: c }) => {
    const figures: OverlayFigure[] = [];
    if (c.length >= 3) figures.push(fill([c[0], c[1], c[2]]));
    if (c.length >= 5) figures.push(fill([c[2], c[3], c[4]]));
    if (c.length >= 2) figures.push(path(c));
    // Dashed legs X-B and B-D show the ratio lines.
    const dashed = { style: 'dashed', dashedValue: [4, 4] };
    if (c.length >= 3) figures.push({ type: 'line', attrs: { coordinates: [c[0], c[2]] }, styles: dashed });
    if (c.length >= 5) figures.push({ type: 'line', attrs: { coordinates: [c[2], c[4]] }, styles: dashed });
    return [...figures, ...labelled(c, ['X', 'A', 'B', 'C', 'D'])];
  },
});

registerOverlay({
  name: 'abcdPattern',
  totalStep: 5,
  needDefaultPointFigure: true,
  createPointFigures: ({ coordinates: c }) => (c.length < 2 ? [] : [path(c), ...labelled(c, ['A', 'B', 'C', 'D'])]),
});

registerOverlay({
  name: 'elliottImpulse',
  totalStep: 7,
  needDefaultPointFigure: true,
  createPointFigures: ({ coordinates: c }) =>
    (c.length < 2 ? [] : [path(c), ...labelled(c, ['(0)', '(1)', '(2)', '(3)', '(4)', '(5)'])]),
});

registerOverlay({
  name: 'elliottCorrection',
  totalStep: 5,
  needDefaultPointFigure: true,
  createPointFigures: ({ coordinates: c }) =>
    (c.length < 2 ? [] : [path(c), ...labelled(c, ['(0)', '(A)', '(B)', '(C)'])]),
});

// ─── Fibonacci ────────────────────────────────────────────────────────────────
const FIB_EXT_LEVELS = [0, 0.382, 0.618, 1, 1.272, 1.618, 2, 2.618];

// Trend-based extension: A → B is the move, C is where the projection starts.
registerOverlay({
  name: 'fibExtension',
  totalStep: 4,
  needDefaultPointFigure: true,
  needDefaultYAxisFigure: true,
  createPointFigures: ({ chart, overlay, coordinates: c, bounding, yAxis }) => {
    const figures: OverlayFigure[] = [];
    if (c.length >= 2) figures.push({ type: 'line', attrs: { coordinates: c.slice(0, 3) }, styles: { style: 'dashed', dashedValue: [4, 4] } });
    const [a, b, cc] = overlay.points;
    if (c.length < 3 || a?.value == null || b?.value == null || cc?.value == null || !yAxis) return figures;
    const precision = chart.getSymbol()?.pricePrecision ?? 2;
    const move = b.value - a.value;
    const startX = Math.min(c[0].x, c[2].x);
    FIB_EXT_LEVELS.forEach((r) => {
      const price = cc.value! + move * r;
      const y = yAxis.convertToPixel(price);
      figures.push({ type: 'line', attrs: { coordinates: [{ x: startX, y }, { x: bounding.width, y }] } });
      figures.push({
        type: 'text', ignoreEvent: true,
        attrs: { x: startX, y, text: `${r} (${price.toFixed(precision)})`, baseline: 'bottom' },
        styles: { color: BLUE, backgroundColor: 'transparent', borderSize: 0, paddingLeft: 2 },
      });
    });
    return figures;
  },
});

// ─── Annotations ──────────────────────────────────────────────────────────────
// extendData holds the text; the toolbar asks for it when the point is placed.
registerOverlay<string>({
  name: 'textLabel',
  totalStep: 2,
  needDefaultPointFigure: false,
  createPointFigures: ({ overlay, coordinates: c }) => (c.length ? {
    type: 'text',
    attrs: { x: c[0].x, y: c[0].y, text: overlay.extendData || 'Text', align: 'left', baseline: 'middle' },
    styles: { color: '#FFFFFF', backgroundColor: BLUE, borderColor: BLUE, size: 12, paddingLeft: 6, paddingRight: 6, paddingTop: 4, paddingBottom: 4, borderRadius: 3 },
  } : []),
});

registerOverlay<string>({
  name: 'emojiMark',
  totalStep: 2,
  needDefaultPointFigure: false,
  createPointFigures: ({ overlay, coordinates: c }) => (c.length ? {
    type: 'text',
    attrs: { x: c[0].x, y: c[0].y, text: overlay.extendData || '🙂', align: 'center', baseline: 'middle' },
    styles: { backgroundColor: 'transparent', borderSize: 0, size: 26, paddingLeft: 0, paddingRight: 0, paddingTop: 0, paddingBottom: 0 },
  } : []),
});

// Date & price range: change, percent and bar count between two points.
registerOverlay({
  name: 'measureRange',
  totalStep: 3,
  needDefaultPointFigure: true,
  createPointFigures: ({ chart, overlay, coordinates: c }) => {
    const [p0, p1] = overlay.points;
    if (c.length < 2 || p0?.value == null || p1?.value == null) return [];
    const precision = chart.getSymbol()?.pricePrecision ?? 2;
    const diff = p1.value - p0.value;
    const pct = p0.value ? (diff / p0.value) * 100 : 0;
    const bars = (p1.dataIndex ?? 0) - (p0.dataIndex ?? 0);
    const color = diff >= 0 ? UP : DOWN;
    const tint = diff >= 0 ? 'rgba(34, 197, 94, 0.15)' : 'rgba(239, 68, 68, 0.15)';
    const left = Math.min(c[0].x, c[1].x), right = Math.max(c[0].x, c[1].x);
    const top = Math.min(c[0].y, c[1].y), bottom = Math.max(c[0].y, c[1].y);
    const midX = (left + right) / 2, midY = (top + bottom) / 2;
    const sign = diff >= 0 ? '+' : '';
    return [
      { type: 'rect', attrs: { x: left, y: top, width: right - left, height: bottom - top }, styles: { style: 'fill', color: tint } },
      { type: 'line', attrs: { coordinates: [{ x: midX, y: c[0].y }, { x: midX, y: c[1].y }] }, styles: { color } },
      { type: 'line', attrs: { coordinates: [{ x: c[0].x, y: midY }, { x: c[1].x, y: midY }] }, styles: { color } },
      {
        type: 'text', ignoreEvent: true,
        attrs: {
          x: midX, y: diff >= 0 ? top - 6 : bottom + 6, align: 'center', baseline: diff >= 0 ? 'bottom' : 'top',
          text: `${sign}${diff.toFixed(precision)} (${sign}${pct.toFixed(2)}%) · ${Math.abs(bars)} bars`,
        },
        styles: { color: '#FFFFFF', backgroundColor: color, borderColor: color, borderRadius: 3, paddingLeft: 6, paddingRight: 6, paddingTop: 4, paddingBottom: 4 },
      },
    ];
  },
});
