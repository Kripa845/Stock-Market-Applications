// // Small formatters shared by the Broker Acc / Dist page's charts.
// import { formatCount } from '../../market/format';

// /** 1.2K / 3.4M axis labels. */
// export const compact = (value: number) => {
//   const abs = Math.abs(value);
//   const [div, suffix] = abs >= 1e6 ? [1e6, 'M'] : abs >= 1e3 ? [1e3, 'K'] : [1, ''];
//   return `${(value / div).toFixed(div === 1 ? 0 : 1).replace(/\.0$/, '')}${suffix}`;
// };

// export const signed = (value: number) => `${value > 0 ? '+' : ''}${formatCount(value)}`;

// export const toneText = (value: number | null | undefined) =>
//   value == null || value === 0 ? 'text-text-secondary' : value > 0 ? 'text-up' : 'text-down';

// /** Categorical series colour for a slot (0-7); index.css defines light and dark steps. */
// export const seriesColor = (slot: number) => `var(--series-${(slot % 8) + 1})`;
import { formatCount } from '../../market/format';

/** 1.2K / 3.4M axis labels. */
export const compact = (value: number) => {
  const abs = Math.abs(value);
  const [div, suffix] =
    abs >= 1e6 ? [1e6, 'M'] :
    abs >= 1e3 ? [1e3, 'K'] :
    [1, ''];

  return `${(value / div).toFixed(div === 1 ? 0 : 1).replace(/\.0$/, '')}${suffix}`;
};

export const signed = (value: number) =>
  `${value > 0 ? '+' : ''}${formatCount(value)}`;

export const toneText = (
  value: number | null | undefined
) =>
  value == null || value === 0
    ? 'text-text-secondary'
    : value > 0
      ? 'text-up'
      : 'text-down';

/**
 * Use a larger categorical palette.
 * CSS variables are defined in index.css so themes can control the colors.
 */
export const SERIES_COLOR_COUNT = 20;

export const seriesColor = (slot: number) => {
  const normalized =
    ((Math.trunc(slot) % SERIES_COLOR_COUNT) + SERIES_COLOR_COUNT) %
    SERIES_COLOR_COUNT;

  return `var(--series-${normalized + 1})`;
};

/** Neutral color for the aggregated Others slice. */
export const otherSeriesColor = () => 'var(--series-other)';