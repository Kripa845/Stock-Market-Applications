// DEV ONLY.  Generated Stock Comparison payloads in the API's shape, used when
// VITE_COMPARE_MOCK=1 under `npm run dev` (see api/compare.ts).  Nothing here is real
// market data: symbols are synthetic (MOCK-xxx), values are pseudo-random but seeded per
// symbol so a page reload shows the same numbers.  Some fields are null with reasons and
// some warnings are set, so the null / warning handling can be exercised.

import type {
  BrokerRow, CompareCompaniesResponse, CompareCompany, CompareProfile, CompareResponse,
  CoverageResponse, NullField, QualityWarning,
} from './compare';

const SECTORS = [
  'Commercial Bank', 'Development Bank', 'Finance', 'Microfinance', 'Hydropower',
  'Life Insurance', 'Non Life Insurance', 'Manufacturing', 'Hotels and Tourism', 'Investment', 'Others',
];
const FINANCIAL = new Set(SECTORS.slice(0, 4).concat(SECTORS.slice(5, 7)));
const COMPANY_COUNT = 20;

function rng(seed: string) {
  let h = 2166136261;
  for (const ch of seed) h = Math.imul(h ^ ch.charCodeAt(0), 16777619);
  return () => {
    h = Math.imul(h ^ (h >>> 15), 2246822507);
    h = Math.imul(h ^ (h >>> 13), 3266489909);
    return ((h ^= h >>> 16) >>> 0) / 4294967296;
  };
}

const round = (n: number, d = 2) => Math.round(n * 10 ** d) / 10 ** d;
const iso = (d: Date) => d.toISOString().slice(0, 10);

function companies(): CompareCompany[] {
  return Array.from({ length: COMPANY_COUNT }, (_, i) => {
    const sector = SECTORS[i % SECTORS.length];
    const code = sector.replace(/[^A-Z]/g, '').padEnd(2, 'X');
    const symbol = `MOCK-${code}${Math.floor(i / SECTORS.length) + 1}`;
    return { symbol, name: `Mock ${sector} Company ${Math.floor(i / SECTORS.length) + 1} Ltd`, sector };
  });
}

function brokers(rand: () => number, total: number): BrokerRow[] {
  let left = 60;
  return Array.from({ length: 5 }, () => {
    const pct = round(Math.max(1, rand() * left * 0.5));
    left -= pct;
    const no = 1 + Math.floor(rand() * 90);
    return { broker_no: no, broker_name: rand() < 0.1 ? null : `Mock Securities ${no} Pvt. Ltd.`,
      quantity: Math.round((total * pct) / 100), pct_of_day_volume: pct };
  }).sort((a, b) => b.quantity - a.quantity);
}

function profile(company: CompareCompany, date?: string): CompareProfile {
  const rand = rng(company.symbol);
  const nulls: NullField[] = [];
  const warnings: QualityWarning[] = [];
  const nullable = <T,>(field: string, value: T, chance: number, reason: string, note?: string): T | null => {
    if (rand() < chance) { nulls.push({ field, reason, ...(note ? { note } : {}) }); return null; }
    return value;
  };

  const priceDate = new Date(Date.UTC(2026, 9, 29));
  const ltp = round(100 + rand() * 1200);
  const prev = round(ltp / (1 + (rand() - 0.5) * 0.08));
  const low = round(ltp * (0.6 + rand() * 0.35));
  const high = round(Math.max(ltp, low) * (1.02 + rand() * 0.5));
  const shares = Math.round(5e6 + rand() * 2.5e8);
  const bv = round(80 + rand() * 300);
  const negative = rand() < 0.1;
  const eps = round(negative ? -(rand() * 30) : 1 + rand() * 45);
  const faceAssumed = rand() < 0.15;
  const paidUp = shares * 100;
  const dayVolume = Math.round(10000 + rand() * 400000);
  const financial = FINANCIAL.has(company.sector);
  const sectorNote = financial
    ? 'Banks, finance companies and insurers carry deposits / policy liabilities, so D/E and ROA are not comparable with other sectors.'
    : undefined;

  const quarterlyShort = rand() < 0.15;
  const epsTtm = quarterlyShort ? nullable('general.eps_ttm', eps, 1, 'needs_more_quarterly_data') : eps;
  const noDividend = rand() < 0.12;
  const brokersDate = date ?? iso(new Date(priceDate.getTime() + 86400000));
  if (!date) warnings.push({ code: 'brokers_date_differs', detail: `Floorsheet is for ${brokersDate}; prices are for ${iso(priceDate)}.` });
  if (rand() < 0.6) warnings.push({ code: 'stale_price', detail: `Latest crawled close is ${iso(priceDate)}; the 2026-10-30 session is missing.` });
  if (rand() < 0.4) warnings.push({ code: 'unadjusted_price_adjustment',
    detail: 'Prices are not adjusted for bonus / right shares; these fields span a book closure.',
    sessions: [{ date: '2026-01-01', fields: ['technicals.sma200', 'general.week52_low', 'general.week52_high'] }] });
  if (faceAssumed) warnings.push({ code: 'face_value_assumed', detail: 'No face value in DividendAnnouncement; using the NEPSE default of 100.' });

  const macd = round((rand() - 0.5) * 30, 4);
  const signal = round(macd + (rand() - 0.5) * 8, 4);
  const sma50 = round(ltp * (0.85 + rand() * 0.3));
  const sma200 = round(ltp * (0.75 + rand() * 0.5));
  const cash = round(rand() * 20), bonus = round(rand() < 0.5 ? rand() * 15 : 0);
  const rsi = nullable('technicals.rsi', round(5 + rand() * 90, 4), 0.05, 'no_price_movement');

  const result: CompareProfile = {
    symbol: company.symbol, name: company.name, sector: company.sector,
    general: {
      ltp, ltp_source: 'daily_price', previous_close: prev, change_pct: round(((ltp - prev) / prev) * 100),
      price_trend_3m: null, week52_low: low, week52_high: high, listed_shares: shares,
      face_value: 100, face_value_source: faceAssumed ? 'default_100' : 'dividend_announcement',
      market_cap: round(ltp * shares), paid_up_capital: paidUp, reserve_surplus: round(bv * shares - paidUp),
      eps_ttm: epsTtm, eps_reported: eps, eps_reported_flag: 'same_as_ttm_until_quarterly_history_backfilled',
      brokers_date: brokersDate, top_buy_brokers: brokers(rand, dayVolume), top_sell_brokers: brokers(rand, dayVolume),
    },
    fundamentals: {
      report_period: quarterlyShort ? '2083/2084 Q1' : '2082/2083 Q4',
      pe: epsTtm === null ? nullable('fundamentals.pe', null, 1, 'needs_more_quarterly_data')
        : negative ? nullable('fundamentals.pe', null, 1, 'negative_eps') : round(ltp / eps),
      pb: round(ltp / bv),
      roe: epsTtm === null ? nullable('fundamentals.roe', null, 1, 'needs_more_quarterly_data') : round((eps / bv) * 100),
      dividend: noDividend ? nullable('fundamentals.dividend', null, 1, 'no_dividend_history')
        : { fiscal_year: '2081/2082', cash_pct: cash, bonus_pct: bonus, total_pct: round(cash + bonus),
            status: rand() < 0.8 ? 'distributed' : 'agm_approved', book_closure_date: '2025-12-15' },
      dividend_yield: noDividend ? nullable('fundamentals.dividend_yield', null, 1, 'no_dividend_history')
        : round(((cash + bonus) * 100) / 100 / ltp * 100),
      yoy_profit_growth: nullable('fundamentals.yoy_profit_growth', null, 1, 'needs_more_quarterly_data'),
      earning_trend_5q: nullable('fundamentals.earning_trend_5q', null, 1, 'needs_more_quarterly_data'),
      peg: nullable('fundamentals.peg', null, 1, 'needs_more_quarterly_data'),
      ps: nullable('fundamentals.ps', null, 1, 'no_source_column'),
      roa: nullable('fundamentals.roa', null, 1, 'no_source_column', sectorNote),
      debt_equity: nullable('fundamentals.debt_equity', null, 1, 'no_source_column', sectorNote),
    },
    technicals: {
      volume_trend: null, rsi,
      macd, macd_signal: signal, macd_hist: round(macd - signal, 4), macd_label: macd > signal ? 'Bullish' : 'Bearish',
      sma50: { value: sma50, above: ltp > sma50 }, sma200: { value: sma200, above: ltp > sma200 },
    },
    data_quality: {
      price_as_of: iso(priceDate), expected_latest_session: '2026-10-30', snapshot_as_of: iso(priceDate),
      report_period: quarterlyShort ? '2083/2084 Q1' : '2082/2083 Q4', brokers_as_of: brokersDate,
      null_fields: nulls, warnings,
    },
  };
  return result;
}

const delay = <T,>(value: T) => new Promise<T>((resolve) => setTimeout(() => resolve(value), 250));

export function mockCompanies(): Promise<CompareCompaniesResponse> {
  const list = companies();
  return delay({ results: list, sectors: [...new Set(list.map((c) => c.sector))].sort() });
}

export function mockCompare(symbols: string[], date?: string): Promise<CompareResponse> {
  const known = new Map(companies().map((c) => [c.symbol, c]));
  const unknown = symbols.filter((s) => !known.has(s));
  if (unknown.length) {
    return Promise.reject({ isAxiosError: true, response: { status: 400, data: {
      code: 'unknown_symbols', detail: `Not a tracked company: ${unknown.join(', ')}.`, invalid_symbols: unknown } } });
  }
  // One in ~7 profiles fails, to exercise the per-company error column.
  const results = symbols.map((s) => {
    const company = known.get(s)!;
    if (rng(`${s}-fail`)() < 0.14) {
      return { ...company, error: 'computation_failed', detail: "This company's profile could not be built; the others are unaffected." } as CompareProfile;
    }
    return profile(company, date);
  });
  return delay({ results, universe_label: 'tracked companies' });
}

export function mockCoverage(): Promise<CoverageResponse> {
  return delay({
    as_of: new Date().toISOString(), expected_latest_session: '2026-10-30', tracked_count: COMPANY_COUNT,
    companies: companies().map((c) => {
      const p = profile(c);
      return {
        symbol: c.symbol, sector: c.sector, price_sessions: 690, snapshot_sessions: 690,
        quarters_in_quarterly_report: p.fundamentals.report_period?.endsWith('Q1') ? 2 : 1,
        eps_present: true, book_value_present: true, listed_shares_present: true,
        dividend_rows: p.fundamentals.dividend ? 10 : 0, price_as_of: p.data_quality.price_as_of,
        snapshot_as_of: p.data_quality.snapshot_as_of, null_fields: p.data_quality.null_fields.map((n) => n.field),
        problems: p.data_quality.warnings.map((w) => w.code), sanity_checks_failed: [],
      };
    }),
  });
}
