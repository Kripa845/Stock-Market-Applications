import { registerIndicator, type Chart } from 'klinecharts';

// Shared by TradingChart and KlinePriceChart. registerIndicator is global, so defining the same
// names in two files meant whichever module loaded last silently replaced the other.

registerIndicator({
  name: 'DAILY_VWAP', shortName: 'VWAP', series: 'price',
  figures: [{ key: 'vwap', title: 'VWAP: ', type: 'line' }],
  calc: (list) => list.map((d) => ({ vwap: d.volume && d.turnover ? d.turnover / d.volume : d.close })),
});

// In KLineCharts v10 `data.current` is this indicator's own calc() row (v9 passed
// { kLineData, indicatorData }), so the row carries what the colour needs. The anomaly
// lookup happens at draw time because changing extendData redraws but does not recalc.
registerIndicator<{ volume: number; up: boolean; day: string }>({
  name: 'VOL_ANOMALY', shortName: 'VOL', precision: 0, shouldFormatBigNumber: true,
  figures: [{
    key: 'volume', title: 'VOL: ', type: 'bar', baseValue: 0,
    styles: ({ data, indicator }) => {
      const row = data.current;
      if (row && ((indicator.extendData ?? []) as string[]).includes(row.day)) return { color: '#d946ef' };
      return { color: row?.up ? '#22C55E' : '#EF4444' };
    },
  }],
  calc: (list) => list.map((d) => ({
    volume: d.volume ?? 0,
    up: d.close >= d.open,
    day: new Date(d.timestamp).toISOString().slice(0, 10),
  })),
});

// Approximation of a "buy sell pressure" pane: 14-bar share of up-volume vs down-volume, 0-100.
// Replace calc() with your real formula when you have it.
registerIndicator({
  name: 'BSP', shortName: 'Buy/Sell pressure', calcParams: [14],
  figures: [
    { key: 'buy', title: 'Buy: ', type: 'line' },
    { key: 'sell', title: 'Sell: ', type: 'line' },
  ],
  calc: (list, ind: any) => {
    const n: number = ind.calcParams?.[0] ?? 14;
    return list.map((_, i) => {
      if (i < n - 1) return {};
      let up = 0, down = 0;
      for (let j = i - n + 1; j <= i; j++) {
        const x = (list[j].close - list[j].open) * (list[j].volume ?? 0);
        if (x > 0) up += x; else down -= x;
      }
      const buy = up + down ? (up / (up + down)) * 100 : 50;
      return { buy, sell: 100 - buy };
    });
  },
});

// createIndicator returns the indicator id in v10, not the pane id it was placed in.
export const paneOf = (chart: Chart, indicatorId: string | null) =>
  (indicatorId && chart.getIndicators({ id: indicatorId })[0]?.paneId) || 'candle_pane';
