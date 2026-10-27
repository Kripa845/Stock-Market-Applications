/**
 * accDistMock.ts
 *
 * Mock data for the stock accumulation / distribution page.  The 1D figures are the
 * reference snapshot; longer periods scale and jitter them deterministically so each
 * period looks different but stays stable across reloads.  Delete once the backend
 * endpoint exists (see api/accDist.ts).
 */

import type { AccDistPeriod, AccDistRow } from '../api/accDist';

interface Seed {
  symbol: string;
  sector: string;
  broker: number;
  /** Net quantity, unsigned. */
  qty: number;
  /** Net amount in NPR, unsigned. */
  amount: number;
  avgRate: number;
  /** Net quantity as % of free-float shares. */
  floatPct: number;
}

const BANK = 'Commercial Banks';
const HYDRO = 'Hydropower';
const MFG = 'Manufacturing And Processing';

const ACCUMULATION: Seed[] = [
  { symbol: 'GHL', sector: HYDRO, broker: 25, qty: 202_140, amount: 63_877_000, avgRate: 316.01, floatPct: 0.0087 },
  { symbol: 'SANIMA', sector: BANK, broker: 33, qty: 126_310, amount: 49_921_000, avgRate: 395.23, floatPct: 0.0011 },
  { symbol: 'GVL', sector: HYDRO, broker: 58, qty: 72_850, amount: 40_452_000, avgRate: 555.28, floatPct: 0.0042 },
  { symbol: 'HDL', sector: MFG, broker: 66, qty: 22_750, amount: 29_954_000, avgRate: 1316.67, floatPct: 0.0012 },
  { symbol: 'MBL', sector: BANK, broker: 44, qty: 97_670, amount: 26_714_000, avgRate: 273.52, floatPct: 0.0006 },
  { symbol: 'TAMOR', sector: HYDRO, broker: 62, qty: 41_100, amount: 24_097_000, avgRate: 586.31, floatPct: 0.0033 },
  { symbol: 'SHIVM', sector: MFG, broker: 42, qty: 32_600, amount: 22_659_000, avgRate: 695.08, floatPct: 0.0024 },
  { symbol: 'NIMB', sector: BANK, broker: 33, qty: 109_210, amount: 22_614_000, avgRate: 207.07, floatPct: 0.0004 },
  { symbol: 'SBL', sector: BANK, broker: 65, qty: 51_240, amount: 22_012_000, avgRate: 429.59, floatPct: 0.0005 },
  { symbol: 'CBBL', sector: 'Microfinance', broker: 17, qty: 22_330, amount: 21_924_000, avgRate: 981.81, floatPct: 0.0021 },
  { symbol: 'NMB', sector: BANK, broker: 33, qty: 67_820, amount: 18_472_000, avgRate: 272.36, floatPct: 0.0005 },
  { symbol: 'MBJC', sector: HYDRO, broker: 35, qty: 53_460, amount: 17_488_000, avgRate: 327.13, floatPct: 0.0029 },
  { symbol: 'NABIL', sector: BANK, broker: 58, qty: 31_420, amount: 15_982_000, avgRate: 508.66, floatPct: 0.0001 },
  { symbol: 'UPPER', sector: HYDRO, broker: 45, qty: 48_900, amount: 9_312_000, avgRate: 190.43, floatPct: 0.0013 },
  { symbol: 'NICA', sector: BANK, broker: 49, qty: 19_850, amount: 7_421_000, avgRate: 373.85, floatPct: 0.0002 },
  { symbol: 'API', sector: HYDRO, broker: 34, qty: 26_400, amount: 6_204_000, avgRate: 235.0, floatPct: 0.0015 },
];

const DISTRIBUTION: Seed[] = [
  { symbol: 'HDL', sector: MFG, broker: 34, qty: 40_240, amount: 53_011_000, avgRate: 1317.37, floatPct: 0.0021 },
  { symbol: 'CBBL', sector: 'Microfinance', broker: 35, qty: 39_900, amount: 39_146_000, avgRate: 981.15, floatPct: 0.0038 },
  { symbol: 'SHIVM', sector: MFG, broker: 44, qty: 46_210, amount: 32_141_000, avgRate: 695.55, floatPct: 0.0034 },
  { symbol: 'MEN', sector: HYDRO, broker: 84, qty: 46_040, amount: 31_098_000, avgRate: 675.52, floatPct: 0.0041 },
  { symbol: 'SANIMA', sector: BANK, broker: 65, qty: 69_840, amount: 27_746_000, avgRate: 397.28, floatPct: 0.0006 },
  { symbol: 'SANIMA', sector: BANK, broker: 44, qty: 66_850, amount: 26_325_000, avgRate: 393.79, floatPct: 0.0006 },
  { symbol: 'SBL', sector: BANK, broker: 17, qty: 53_020, amount: 22_761_000, avgRate: 429.28, floatPct: 0.0005 },
  { symbol: 'MBL', sector: BANK, broker: 48, qty: 82_070, amount: 22_406_000, avgRate: 273.01, floatPct: 0.0005 },
  { symbol: 'MFIL', sector: 'Finance', broker: 43, qty: 28_010, amount: 21_367_000, avgRate: 762.84, floatPct: 0.0031 },
  { symbol: 'GHL', sector: HYDRO, broker: 62, qty: 67_770, amount: 21_333_000, avgRate: 314.78, floatPct: 0.0029 },
  { symbol: 'GVL', sector: HYDRO, broker: 17, qty: 34_800, amount: 19_430_000, avgRate: 558.35, floatPct: 0.002 },
  { symbol: 'CITY', sector: 'Hotels And Tourism', broker: 44, qty: 53_840, amount: 17_259_000, avgRate: 320.56, floatPct: 0.0026 },
  { symbol: 'NABIL', sector: BANK, broker: 45, qty: 27_300, amount: 13_873_000, avgRate: 508.17, floatPct: 0.0001 },
  { symbol: 'UPPER', sector: HYDRO, broker: 34, qty: 51_200, amount: 9_725_000, avgRate: 189.94, floatPct: 0.0013 },
  { symbol: 'NIMB', sector: BANK, broker: 58, qty: 38_700, amount: 8_005_000, avgRate: 206.85, floatPct: 0.0002 },
  { symbol: 'TAMOR', sector: HYDRO, broker: 17, qty: 11_900, amount: 6_970_000, avgRate: 585.7, floatPct: 0.001 },
];

/** Rough number of 1D sessions' worth of flow each period accumulates. */
const PERIOD_SCALE: Record<AccDistPeriod, number> = {
  '1D': 1, '2D': 1.8, '1W': 4.2, '2W': 7.9, '1M': 15.5,
  '3M': 41, '6M': 78, '1Y': 150, '2Y': 270, '3Y': 390,
};

/** FNV-1a, mapped to [0, 1). */
function unit(key: string): number {
  let h = 2166136261;
  for (let i = 0; i < key.length; i += 1) {
    h ^= key.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return (h >>> 0) / 2 ** 32;
}

function build(seeds: Seed[], period: AccDistPeriod, sign: 1 | -1): AccDistRow[] {
  const scale = PERIOD_SCALE[period];
  return seeds
    .map((seed) => {
      const key = `${seed.symbol}:${seed.broker}:${period}`;
      if (period === '1D') {
        return { ...seed, netQty: sign * seed.qty, netAmount: sign * seed.amount, floatQtyPct: seed.floatPct };
      }
      const qtyFactor = scale * (0.6 + unit(key) * 0.8);
      const avgRate = Math.round(seed.avgRate * (0.9 + unit(`${key}:rate`) * 0.2) * 100) / 100;
      const qty = Math.round(seed.qty * qtyFactor);
      return { ...seed, avgRate, netQty: sign * qty, netAmount: sign * qty * avgRate, floatQtyPct: seed.floatPct * qtyFactor };
    })
    .sort((a, b) => Math.abs(b.netAmount) - Math.abs(a.netAmount))
    .map(({ symbol, sector, broker, netQty, netAmount, avgRate, floatQtyPct }, index) => ({
      symbol, sector, broker, netQty, netAmount, avgRate, floatQtyPct, rank: index + 1,
    }));
}

export const mockAccDist = (period: AccDistPeriod) => ({
  period,
  accumulation: build(ACCUMULATION, period, 1),
  distribution: build(DISTRIBUTION, period, -1),
});

export const MOCK_WATCHLIST = ['GHL', 'HDL', 'SANIMA', 'CBBL', 'NABIL'];
