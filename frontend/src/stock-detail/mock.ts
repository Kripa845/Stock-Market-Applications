import type { Candle, FinCell, StockDetail } from "./types";

/** Deterministic pseudo-random candles so the demo always looks the same. */
function makeCandles(n = 125, start = 345): Candle[] {
  let seed = 7;
  const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
  const out: Candle[] = [];
  let price = start;
  const day = 86_400_000;
  const t0 = Date.now() - n * day;
  for (let i = 0; i < n; i++) {
    const drift = i < 60 ? -0.15 : i < 100 ? -0.05 : 0.35;
    const open = price;
    const close = Math.max(280, open + (rnd() - 0.5) * 6 + drift);
    const high = Math.max(open, close) + rnd() * 3;
    const low = Math.min(open, close) - rnd() * 3;
    out.push({
      timestamp: t0 + i * day,
      open: +open.toFixed(2),
      high: +high.toFixed(2),
      low: +low.toFixed(2),
      close: +close.toFixed(2),
      volume: Math.round(20_000 + rnd() * 120_000),
    });
    price = close;
  }
  return out;
}

const c = (v: string, tone: FinCell["tone"]): FinCell => ({ v, tone });

export const mockStock: StockDetail = {
  symbol: "NICA",
  name: "NIC Asia Bank Ltd.",
  sector: "Commercial Banks",
  ltp: 331.0,
  change: -4.0,
  changePct: -1.19,
  asOf: "as of Oct 30, 2026",
  candles: makeCandles(),
  quote: [
    { label: "Open", value: "335.10" },
    { label: "High / Low", value: "344.90 / 330.10" },
    { label: "Prev. close", value: "335.00" },
    { label: "Volume", value: "3.09 L" },
    { label: "52-week high", value: "411.00" },
    { label: "52-week low", value: "302.90" },
    { label: "Market cap", value: "49.38 Arba" },
    { label: "Shares outstanding", value: "14.92 Cr" },
  ],
  masterScore: { score: 40, label: "MASTER Neutral / Avoid · Avoid" },
  holding: { promoter: "51.00%", public: "49.00%" },
  performance: [
    { label: "1-week change", value: "+3.15%", tone: "pos" },
    { label: "1-month change", value: "+6.09%", tone: "pos" },
    { label: "3-month change", value: "-1.52%", tone: "neg" },
    { label: "6-month change", value: "-7.54%", tone: "neg" },
    { label: "YTD change", value: "+1.22%", tone: "pos" },
    { label: "1-year change", value: "+3.12%", tone: "pos" },
    { label: "3-month high", value: "344.90" },
    { label: "3-month low", value: "303.00" },
    { label: "From 52-week high", value: "-19.46%", tone: "neg" },
    { label: "From 52-week low", value: "+9.28%", tone: "pos" },
    { label: "180-day avg price", value: "330.72" },
    { label: "350-day avg price", value: "335.37" },
    { label: "Avg volume (1W)", value: "1.37 L" },
    { label: "Avg volume (1M)", value: "82,817" },
    { label: "Avg volume (6M)", value: "60,617" },
    { label: "Avg volume (12M)", value: "88,318" },
    { label: "Daily volatility (1M)", value: "1.73%" },
    { label: "Beta vs NEPSE (1Y)", value: "1.38" },
  ],
  valuationFiled: "filed 2082/2083 Q4",
  valuation: [
    { label: "EPS (annualized)", value: "1.22" },
    { label: "EPS (TTM)", value: "1.22" },
    { label: "P/E", value: "271.31" },
    { label: "P/B", value: "1.92" },
    { label: "Book value / share", value: "172.22" },
    { label: "ROE", value: "0.71%" },
    { label: "ROA", value: "0.05%" },
    { label: "Net profit margin", value: "4.51%" },
    { label: "Graham number", value: "68.78" },
    { label: "Dividend yield", value: "0.46%" },
    { label: "Dividend 2079/2080", value: "30.52% (1.52% cash + 29.00% bonus)", wide: true },
  ],
  valuationNote:
    "P/E and P/B use the latest close over per-share values from the company's most recent filed statement.",
  rangeMetrics: [
    { label: "EPS (Rs.)", value: 1.22, min: -1.02, avg: 19.08, max: 34.76 },
    { label: "P/E", value: 271.31, min: 8.48, avg: 22.28, max: 271.31 },
    { label: "P/B", value: 1.92, min: 1.05, avg: 1.77, max: 3.65 },
    { label: "Networth / Share (Rs.)", value: 172.32, min: 140.92, avg: 167.06, max: 292.89 },
    { label: "ROE (%)", value: 0.71, min: 0.0, avg: 8.96, max: 16.49 },
  ],
  technicals: [
    { name: "RSI (14)", value: "60.35", signal: "Neutral" },
    { name: "MACD", value: "2.81", signal: "Bullish" },
    { name: "EMA 5", value: "326.59", signal: "Bullish" },
    { name: "EMA 20", value: "320.09", signal: "Bullish" },
    { name: "EMA 180", value: "332.83", signal: "Bearish" },
    { name: "SMA 50", value: "316.43", signal: "Bullish" },
    { name: "SMA 200", value: "338.03", signal: "Bearish" },
  ],
  pivots: [
    { label: "S3", value: "310.97" },
    { label: "S2", value: "320.53" },
    { label: "S1", value: "325.77" },
    { label: "PP", value: "335.33", active: true },
    { label: "R1", value: "340.57" },
    { label: "R2", value: "350.13" },
    { label: "R3", value: "355.37" },
  ],
  quarters: [
    { q: "Q4", fy: "2082/2083", latest: true },
    { q: "Q3", fy: "2082/2083" },
    { q: "Q2", fy: "2082/2083" },
    { q: "Q1", fy: "2082/2083" },
    { q: "Q4", fy: "2081/2082" },
    { q: "Q3", fy: "2081/2082" },
    { q: "Q2", fy: "2081/2082" },
    { q: "Q1", fy: "2081/2082" },
  ],
  financials: [
    { label: "Paid-up capital", cells: ["14.92 Arba", "14.92 Arba", "14.92 Arba", "14.92 Arba", "14.92 Arba", "14.92 Arba", "14.92 Arba", "14.92 Arba"].map((v) => c(v, "flat")) },
    { label: "Reserve & surplus", cells: [c("10.79 Arba", "worse"), c("10.89 Arba", "worse"), c("14.67 Arba", "worse"), c("14.73 Arba", "worse"), c("14.60 Arba", "worse"), c("14.81 Arba", "worse"), c("14.76 Arba", "worse"), c("15.48 Arba", "better")] },
    { label: "Net interest income", cells: [c("7.85 Arba", "worse"), c("4.36 Arba", "worse"), c("6.31 Arba", "worse"), c("2.29 Arba", "worse"), c("10.26 Arba", "worse"), c("7.96 Arba", "worse"), c("5.19 Arba", "worse"), c("2.55 Arba", "worse")] },
    { label: "Operating profit", cells: [c("97.91 Cr", "worse"), c("67.29 Cr", "worse"), c("19.78 Cr", "worse"), c("19.35 Cr", "better"), c("1.27 Arba", "worse"), c("1.29 Arba", "worse"), c("34.20 Cr", "worse"), c("17.39 Cr", "worse")] },
    { label: "Net profit", cells: [c("18.17 Cr", "worse"), c("14.03 Cr", "worse"), c("13.12 Cr", "worse"), c("12.22 Cr", "better"), c("16.16 Cr", "worse"), c("15.68 Cr", "worse"), c("15.17 Cr", "worse"), c("11.05 Cr", "worse")] },
    { label: "Distributable profit", cells: [c("-14.87 Arba", "worse"), c("-13.66 Arba", "worse"), c("-7.40 Arba", "worse"), c("-6.25 Arba", "worse"), c("-5.21 Arba", "worse"), c("-3.57 Arba", "worse"), c("-2.66 Arba", "worse"), c("-2.21 Arba", "worse")] },
    { label: "Distributable profit / share (Rs.)", cells: [c("-99.65", "worse"), c("-91.55", "worse"), c("-49.60", "worse"), c("-41.88", "worse"), c("-34.94", "worse"), c("-23.93", "worse"), c("-17.80", "worse"), c("-14.84", "worse")] },
    { label: "EPS annualized (Rs.)", cells: [c("1.22", "better"), c("1.25", "worse"), c("1.76", "worse"), c("3.28", "better"), c("1.08", "worse"), c("1.40", "worse"), c("2.03", "worse"), c("2.96", "worse")] },
    { label: "Networth / share (Rs.)", cells: [c("172.32", "better"), null, null, null, null, null, null, null] },
  ],
};