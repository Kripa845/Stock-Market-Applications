// import { useEffect, useRef } from 'react';
// import { dispose, init, registerIndicator, type KLineData } from 'klinecharts';

// // Minimal shape the chart needs. Works with both DailyPrice and PricePoint.
// interface ChartPrice {
//   date: string;                    // "YYYY-MM-DD"
//   open: string | number;
//   high: string | number;
//   low: string | number;
//   close: string | number;
//   volume: number;
//   turnover?: string | number | null;
// }

// interface Props {
//   prices: ChartPrice[];
//   symbol: string;
//   anomalyDates?: string[];         // e.g. ["2026-03-10", "2026-03-12"]
// }

// // ─── Custom indicators (registered once, at module level) ─────────────────────

// // Daily VWAP = turnover / volume, drawn as a line on the candle pane.
// registerIndicator({
//   name: 'DAILY_VWAP',
//   shortName: 'VWAP',
//   series: 'price',
//   figures: [{ key: 'vwap', title: 'VWAP: ', type: 'line' }],
//   calc: (dataList) =>
//     dataList.map((d) => ({
//       vwap: d.volume && d.turnover ? d.turnover / d.volume : d.close,
//     })),
// });

// // Volume bars: magenta on anomaly days, otherwise green/red by candle direction.
// registerIndicator({
//   name: 'VOL_ANOMALY',
//   shortName: 'VOL',
//   figures: [
//     {
//       key: 'volume',
//       title: 'VOL: ',
//       type: 'bar',
//       baseValue: 0,
//       styles: (data: any) => {
//         const ind = data.current?.indicatorData;
//         if (ind?.anomaly) return { color: '#d946ef' };
//         const k = data.current?.kLineData;
//         return { color: k && k.close >= k.open ? '#22C55E' : '#EF4444' };
//       },
//     },
//   ],
//   calc: (dataList, indicator: any) => {
//     const flagged: string[] = indicator.extendData ?? [];
//     return dataList.map((d) => {
//       const day = new Date(d.timestamp).toISOString().slice(0, 10);
//       return { volume: d.volume ?? 0, anomaly: flagged.includes(day) };
//     });
//   },
// });

// // ─── Component ────────────────────────────────────────────────────────────────

// export default function KlinePriceChart({ prices, symbol, anomalyDates }: Props) {
//   const containerRef = useRef<HTMLDivElement>(null);
//   // A string key keeps the effect stable even if the parent passes a new array each render.
//   const anomalyKey = (anomalyDates ?? []).join(',');

//   useEffect(() => {
//     const container = containerRef.current;
//     if (!container) return;

//     const flagged = anomalyKey ? anomalyKey.split(',') : [];

//     const chart = init(container, {
//       locale: 'en-US',
//       timezone: 'Asia/Kathmandu',
//       styles: {
//         grid: {
//           show: true,
//           horizontal: { color: '#E5E7EB', size: 1, style: 'dashed', dashedValue: [3, 3] },
//           vertical: { color: '#E5E7EB', size: 1, style: 'dashed', dashedValue: [3, 3] },
//         },
//         candle: {
//           bar: {
//             upColor: '#22C55E', downColor: '#EF4444', noChangeColor: '#64748B',
//             upBorderColor: '#22C55E', downBorderColor: '#EF4444', noChangeBorderColor: '#64748B',
//             upWickColor: '#22C55E', downWickColor: '#EF4444', noChangeWickColor: '#64748B',
//           },
//           tooltip: {
//             showRule: 'always',
//             showType: 'standard',
//             rect: { position: 'fixed', color: '#FFFFFF', borderColor: '#E2E8F0' },
//             title: { color: '#475569' },
//             legend: { color: '#334155' },
//           },
//         },
//         indicator: {
//           lines: [
//             { color: '#F59E0B', size: 1.5 },
//             { color: '#A855F7', size: 1.5 },
//             { color: '#3B82F6', size: 1.5 },
//             { color: '#EC4899', size: 1.5 },
//           ],
//           bars: [{ upColor: '#22C55E', downColor: '#EF4444', noChangeColor: '#94A3B8' }],
//         },
//         xAxis: {
//           axisLine: { color: '#CBD5E1' },
//           tickLine: { color: '#CBD5E1' },
//           tickText: { color: '#64748B' },
//         },
//         yAxis: {
//           axisLine: { color: '#CBD5E1' },
//           tickLine: { color: '#CBD5E1' },
//           tickText: { color: '#64748B' },
//         },
//         separator: { color: '#CBD5E1', fill: true, activeBackgroundColor: 'rgba(148, 163, 184, .12)' },
//         crosshair: {
//           show: true,
//           horizontal: {
//             show: true,
//             line: { color: '#64748B', size: 1, style: 'dashed', dashedValue: [4, 3] },
//             text: { color: '#FFFFFF', backgroundColor: '#475569', borderColor: '#475569' },
//           },
//           vertical: {
//             show: true,
//             line: { color: '#64748B', size: 1, style: 'dashed', dashedValue: [4, 3] },
//             text: { color: '#FFFFFF', backgroundColor: '#475569', borderColor: '#475569' },
//           },
//         },
//       },
//     });

//     if (!chart) return;

//     chart.setSymbol({ ticker: symbol });
//     chart.setPeriod({ span: 1, type: 'day' });

//     // Candle pane: moving averages + daily VWAP
//     chart.createIndicator({ name: 'MA', paneId: 'candle_pane', calcParams: [5, 10, 30, 60] }, true);
//     chart.createIndicator({ name: 'DAILY_VWAP', paneId: 'candle_pane' }, true);

//     // Volume pane with anomaly colouring (replaces the built-in 'VOL')
//     chart.createIndicator({ name: 'VOL_ANOMALY', extendData: flagged });

//     chart.setDataLoader({
//       getBars: ({ callback }) => {
//         const bars: KLineData[] = prices.map((price) => {
//           const [year, month, day] = price.date.split('-').map(Number);
//           return {
//             timestamp: Date.UTC(year, month - 1, day),
//             open: Number(price.open),
//             high: Number(price.high),
//             low: Number(price.low),
//             close: Number(price.close),
//             volume: price.volume,
//             turnover: Number(price.turnover ?? 0),
//           };
//         });
//         callback(bars);
//       },
//     });

//     return () => dispose(container);
//   }, [prices, symbol, anomalyKey]);

//   return <div ref={containerRef} className="h-full w-full" aria-label={`${symbol} daily candlestick chart`} />;
// }

import { useEffect, useRef } from 'react';
import { dispose, init, registerIndicator, type KLineData } from 'klinecharts';

// Minimal shape the chart needs. Works with both DailyPrice and PricePoint.
interface ChartPrice {
  date: string;                    // "YYYY-MM-DD"
  open: string | number;
  high: string | number;
  low: string | number;
  close: string | number;
  volume: number;
  turnover?: string | number | null;
}

interface RvolItem {
  date: string;
  rvol: number | null;
}

interface Props {
  prices: ChartPrice[];
  symbol: string;
  anomalyDates?: string[];                            // e.g. ["2026-03-10", "2026-03-12"]
  rvol?: RvolItem[];                                  // [{ date, rvol }]
  rvolThresholds?: [number, number, number, number];  // default [0.5, 0.8, 1.25, 4]
}

const DEFAULT_RVOL_THRESHOLDS: [number, number, number, number] = [0.5, 0.8, 1.25, 4];
// Dead, Below Average, Normal, Above Average / High, Extreme
const RVOL_COLORS = ['#ef4444', '#f59e0b', '#64748B', '#22C55E', '#d946ef'];

// ─── Custom indicators (registered once, at module level) ─────────────────────

// Daily VWAP = turnover / volume, drawn as a line on the candle pane.
registerIndicator({
  name: 'DAILY_VWAP',
  shortName: 'VWAP',
  series: 'price',
  figures: [{ key: 'vwap', title: 'VWAP: ', type: 'line' }],
  calc: (dataList) =>
    dataList.map((d) => ({
      vwap: d.volume && d.turnover ? d.turnover / d.volume : d.close,
    })),
});

// Volume bars: magenta on anomaly days, otherwise green/red by candle direction.
registerIndicator({
  name: 'VOL_ANOMALY',
  shortName: 'VOL',
  figures: [
    {
      key: 'volume',
      title: 'VOL: ',
      type: 'bar',
      baseValue: 0,
      styles: (data: any) => {
        const ind = data.current?.indicatorData;
        if (ind?.anomaly) return { color: '#d946ef' };
        const k = data.current?.kLineData;
        return { color: k && k.close >= k.open ? '#22C55E' : '#EF4444' };
      },
    },
  ],
  calc: (dataList, indicator: any) => {
    const flagged: string[] = indicator.extendData ?? [];
    return dataList.map((d) => {
      const day = new Date(d.timestamp).toISOString().slice(0, 10);
      return { volume: d.volume ?? 0, anomaly: flagged.includes(day) };
    });
  },
});

// RVOL bars, coloured by tier.
registerIndicator({
  name: 'RVOL_TIER',
  shortName: 'RVOL',
  figures: [
    {
      key: 'rvol',
      title: 'RVOL: ',
      type: 'bar',
      baseValue: 0,
      styles: (data: any) => ({
        color: data.current?.indicatorData?.color ?? '#64748B',
      }),
    },
  ],
  calc: (dataList, indicator: any) => {
    const ext = indicator.extendData ?? { byDate: {}, thresholds: DEFAULT_RVOL_THRESHOLDS };
    const t: number[] = ext.thresholds;
    return dataList.map((d) => {
      const day = new Date(d.timestamp).toISOString().slice(0, 10);
      const v: number | null | undefined = ext.byDate[day];
      if (v === null || v === undefined) return {};
      const tier = v < t[0] ? 0 : v < t[1] ? 1 : v < t[2] ? 2 : v < t[3] ? 3 : 4;
      return { rvol: v, color: RVOL_COLORS[tier] };
    });
  },
});

// ─── Component ────────────────────────────────────────────────────────────────

export default function KlinePriceChart({ prices, symbol, anomalyDates, rvol, rvolThresholds }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  // A string key keeps the effect stable even if the parent passes a new array each render.
  const anomalyKey = (anomalyDates ?? []).join(',');
  const rvolKey = (rvol ?? []).map((p) => `${p.date}:${p.rvol ?? ''}`).join('|');
  const thresholdKey = (rvolThresholds ?? DEFAULT_RVOL_THRESHOLDS).join(',');

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const flagged = anomalyKey ? anomalyKey.split(',') : [];
    const thresholds = thresholdKey.split(',').map(Number) as [number, number, number, number];

    const chart = init(container, {
      locale: 'en-US',
      timezone: 'Asia/Kathmandu',
      styles: {
        grid: {
          show: true,
          horizontal: { color: '#E5E7EB', size: 1, style: 'dashed', dashedValue: [3, 3] },
          vertical: { color: '#E5E7EB', size: 1, style: 'dashed', dashedValue: [3, 3] },
        },
        candle: {
          bar: {
            upColor: '#22C55E', downColor: '#EF4444', noChangeColor: '#64748B',
            upBorderColor: '#22C55E', downBorderColor: '#EF4444', noChangeBorderColor: '#64748B',
            upWickColor: '#22C55E', downWickColor: '#EF4444', noChangeWickColor: '#64748B',
          },
          tooltip: {
            showRule: 'always',
            showType: 'standard',
            rect: { position: 'fixed', color: '#FFFFFF', borderColor: '#E2E8F0' },
            title: { color: '#475569' },
            legend: { color: '#334155' },
          },
        },
        indicator: {
          lines: [
            { color: '#F59E0B', size: 1.5 },
            { color: '#A855F7', size: 1.5 },
            { color: '#3B82F6', size: 1.5 },
            { color: '#EC4899', size: 1.5 },
          ],
          bars: [{ upColor: '#22C55E', downColor: '#EF4444', noChangeColor: '#94A3B8' }],
        },
        xAxis: {
          axisLine: { color: '#CBD5E1' },
          tickLine: { color: '#CBD5E1' },
          tickText: { color: '#64748B' },
        },
        yAxis: {
          axisLine: { color: '#CBD5E1' },
          tickLine: { color: '#CBD5E1' },
          tickText: { color: '#64748B' },
        },
        separator: { color: '#CBD5E1', fill: true, activeBackgroundColor: 'rgba(148, 163, 184, .12)' },
        crosshair: {
          show: true,
          horizontal: {
            show: true,
            line: { color: '#64748B', size: 1, style: 'dashed', dashedValue: [4, 3] },
            text: { color: '#FFFFFF', backgroundColor: '#475569', borderColor: '#475569' },
          },
          vertical: {
            show: true,
            line: { color: '#64748B', size: 1, style: 'dashed', dashedValue: [4, 3] },
            text: { color: '#FFFFFF', backgroundColor: '#475569', borderColor: '#475569' },
          },
        },
      },
    });

    if (!chart) return;

    chart.setSymbol({ ticker: symbol });
    chart.setPeriod({ span: 1, type: 'day' });

    // Candle pane: moving averages + daily VWAP
    chart.createIndicator({ name: 'MA', paneId: 'candle_pane', calcParams: [5, 10, 30, 60] }, true);
    chart.createIndicator({ name: 'DAILY_VWAP', paneId: 'candle_pane' }, true);

    // Volume pane with anomaly colouring (replaces the built-in 'VOL')
    chart.createIndicator({ name: 'VOL_ANOMALY', extendData: flagged });

    // RVOL pane, only when RVOL data was provided
    if (rvol && rvol.length > 0) {
      const byDate: Record<string, number | null> = {};
      rvol.forEach((p) => { byDate[p.date] = p.rvol; });
      chart.createIndicator({ name: 'RVOL_TIER', extendData: { byDate, thresholds } });
    }

    chart.setDataLoader({
      getBars: ({ callback }) => {
        const bars: KLineData[] = prices.map((price) => {
          const [year, month, day] = price.date.split('-').map(Number);
          return {
            timestamp: Date.UTC(year, month - 1, day),
            open: Number(price.open),
            high: Number(price.high),
            low: Number(price.low),
            close: Number(price.close),
            volume: price.volume,
            turnover: Number(price.turnover ?? 0),
          };
        });
        callback(bars);
      },
    });

    return () => dispose(container);
    // rvol is tracked through rvolKey so a new array with identical content does not rebuild the chart
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prices, symbol, anomalyKey, rvolKey, thresholdKey]);

  return <div ref={containerRef} className="h-full w-full" aria-label={`${symbol} daily candlestick chart`} />;
}