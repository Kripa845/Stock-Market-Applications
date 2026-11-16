export type Tone = "pos" | "neg" | "neutral";

export interface Candle {
  timestamp: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface Metric {
  label: string;
  value: string;
  tone?: Tone;
  wide?: boolean; // spans 2 columns
}

export interface RangeMetric {
  label: string;
  value: number;
  min: number;
  avg: number;
  max: number;
}

export interface TechRow {
  name: string;
  value: string;
  signal: "Bullish" | "Bearish" | "Neutral";
}

export interface PivotLevel {
  label: string; // S3, S2, S1, PP, R1, R2, R3
  value: string;
  active?: boolean;
}

export interface FinCell {
  v: string;
  /** better / worse vs same quarter last year */
  tone: "better" | "worse" | "flat";
}

export interface FinRow {
  label: string;
  cells: (FinCell | null)[];
}

export interface FinQuarter {
  q: string; // "Q4"
  fy: string; // "2082/2083"
  latest?: boolean;
}

export interface StockDetail {
  symbol: string;
  name: string;
  sector: string;
  ltp: number;
  change: number;
  changePct: number;
  asOf: string;
  candles: Candle[];
  quote: Metric[]; // 8 tiles under the chart
  masterScore: { score: number; label: string };
  holding: { promoter: string; public: string };
  performance: Metric[];
  valuation: Metric[];
  valuationFiled: string;
  valuationNote: string;
  rangeMetrics: RangeMetric[];
  technicals: TechRow[];
  pivots: PivotLevel[];
  quarters: FinQuarter[];
  financials: FinRow[];
}

export interface MasterScoreResponse {
  status: 'ok';
  company_id: number;
  symbol: string;
  score: number;
  band: string;
  as_of: string;
  components: { trend: number; momentum: number; macd: number; volume: number };
  holding: { promoter: number; public: number } | null;
}

