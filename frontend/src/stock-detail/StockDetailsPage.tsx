
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { isAxiosError } from "axios";
import type { StockDetail, Candle, MasterScoreResponse } from "./types";
import { Panel, Tile } from "./ui";
import PriceChart from "./Pricechart";
import MasterGauge from "./Mastergauge";
import apiClient from "../api/client";

const EMPTY_QUOTE = [
  "Open", "High / Low", "Prev. close", "Volume",
  "52-week high", "52-week low", "Market cap", "Shares outstanding",
].map((label) => ({ label, value: "—" }));

// Backend stock performance response
interface StockPerformance {
  status: string;
  company_id: number;
  symbol: string;
  name: string;

  current_price: number;

  week_change: number | null;
  month_change: number | null;
  three_month_change: number | null;
  six_month_change: number | null;
  ytd_change: number | null;
  year_change: number | null;

  three_month_high: number | null;
  three_month_low: number | null;
  fifty_two_week_high: number | null;
  fifty_two_week_low: number | null;

  from_52_week_high: number | null;
  from_52_week_low: number | null;

  avg_price_180d: number | null;
  avg_price_350d: number | null;

  avg_volume_1w: number | null;
  avg_volume_1m: number | null;
  avg_volume_6m: number | null;
  avg_volume_12m: number | null;

  daily_volatility_1m: number | null;

  beta_vs_nepse_1y: {
    beta: number | null;
    observations: number;
    status: string;
  };
}

// Backend stock valuation response
interface StockValuation {
  status: string;
  company_id: number;
  symbol: string;
  name: string;

  fiscal_year: string;
  quarter: number;
  reported_on: string | null;

  ltp: number | string | null;
  price_date: string | null;

  eps: number | string | null;
  bv: number | string | null;
  pe: number | string | null;
  pb: number | string | null;

  dpps: number | string | null;
  dpps_yield: number | string | null;

  avg_dpps: number | string | null;
  avg_years_used: number;
  avg_window_years: number;
  avg_yield: number | string | null;

  previous_dpps: number | string | null;
  yoy: number | string | null;
}

// One row from /companies/<id>/prices/
interface PriceRow {
  date: string;
  open: number | string | null;
  high: number | string | null;
  low: number | string | null;
  close: number | string | null;
  volume: number | string | null;
}

// Tracked company response
interface TrackedCompany {
  id: number;
  symbol: string;
  name: string;
  sector?: string;
}

// GET /companies/<id>/technicals/
interface TechIndicator {
  key: string;
  label: string;
  value: number | null;
  signal: string | null;
}

interface TechnicalsResponse {
  status: string;
  as_of?: string;
  sessions?: number;
  possible_corporate_action?: boolean;
  indicators: TechIndicator[];
  pivots: Record<"s3" | "s2" | "s1" | "pp" | "r1" | "r2" | "r3", number | null> | null;
}

// GET /companies/<id>/financials/
interface FinancialsResponse {
  status: string;
  quarters: {
    fiscal_year: string;
    quarter: number;
    reported_on: string | null;
    is_latest: boolean;
    filed: boolean;
  }[];
  rows: {
    key: string;
    label: string;
    unit: "rs" | "per_share";
    values: { value: number | null; yoy: string | null }[];
  }[];
}

export default function StockDetailPage(_props: { stock?: StockDetail }) {
  const [liveQuote, setLiveQuote] = useState<StockDetail["quote"] | null>(null);

  const [trackedCompanies, setTrackedCompanies] = useState<TrackedCompany[]>([]);
  const [trackedCompaniesLoaded, setTrackedCompaniesLoaded] = useState(false);

  const [quoteMeta, setQuoteMeta] = useState<{
    name: string;
    asOf: string;
  } | null>(null);

  const [performance, setPerformance] = useState<StockPerformance | null>(null);
  const [performanceLoading, setPerformanceLoading] = useState(false);
  const [performanceError, setPerformanceError] = useState<string | null>(null);

  // Backend valuation state
  const [valuation, setValuation] = useState<StockValuation | null>(null);
  const [valuationLoading, setValuationLoading] = useState(false);
  const [valuationError, setValuationError] = useState<string | null>(null);

  // MASTER score state
  const [masterScore, setMasterScore] = useState<MasterScoreResponse | null>(null);
  const [masterScoreLoading, setMasterScoreLoading] = useState(false);
  const [masterScoreError, setMasterScoreError] = useState<string | null>(null);

  // Price history (chart) state
  const [candles, setCandles] = useState<Candle[] | null>(null);
  const [candlesLoading, setCandlesLoading] = useState(false);
  const [candlesError, setCandlesError] = useState<string | null>(null);

  // Technical indicators state
  const [technicals, setTechnicals] = useState<TechnicalsResponse | null>(null);
  const [technicalsLoading, setTechnicalsLoading] = useState(false);
  const [technicalsError, setTechnicalsError] = useState<string | null>(null);

  // Quarterly financials state
  const [financials, setFinancials] = useState<FinancialsResponse | null>(null);
  const [financialsLoading, setFinancialsLoading] = useState(false);
  const [financialsError, setFinancialsError] = useState<string | null>(null);

  const navigate = useNavigate();
  const { symbol: rawSymbol } = useParams();
  const [query, setQuery] = useState("");

  // --------------------------------------------------
  // 0. Normalise the selected symbol
  //    - no symbol in the URL           -> undefined (nothing selected)
  //    - unreplaced placeholder ":symbol" (bad link) -> undefined
  // --------------------------------------------------

  const current = useMemo(() => {
    const s = rawSymbol?.trim();
    if (!s || s.startsWith(":")) return undefined;
    return s;
  }, [rawSymbol]);

  const selectedCompany = useMemo(
    () =>
      current
        ? trackedCompanies.find(
            (item) => item.symbol.toUpperCase() === current.toUpperCase()
          )
        : undefined,
    [current, trackedCompanies]
  );

  // A symbol is selected, companies have loaded, but it is not a tracked one
  const symbolNotFound =
    !!current && trackedCompaniesLoaded && !selectedCompany;

  // --------------------------------------------------
  // 1. Fetch live stock quote
  // --------------------------------------------------

  useEffect(() => {
    let active = true;

    setLiveQuote(null);
    setQuoteMeta(null);

    if (!current) {
      return () => {
        active = false;
      };
    }

    apiClient
      .get(`/companies/${encodeURIComponent(current)}/quote/`)
      .then(({ data }) => {
        if (!active) return;

        setQuoteMeta({
          name: data.name,
          asOf: data.as_of
            ? new Date(`${data.as_of}T00:00:00`).toLocaleDateString()
            : "No crawled quote",
        });

        const price = (v: number | string | null) =>
          v == null
            ? "—"
            : Number(v).toLocaleString(undefined, {
                maximumFractionDigits: 2,
              });

        const count = (v: number | string | null) =>
          v == null ? "—" : Number(v).toLocaleString();

        const cap = (v: number | string | null) =>
          v == null
            ? "—"
            : `Rs. ${Number(v).toLocaleString(undefined, {
                maximumFractionDigits: 0,
              })}`;

        setLiveQuote([
          { label: "Open", value: price(data.open) },
          {
            label: "High / Low",
            value: `${price(data.high)} / ${price(data.low)}`,
          },
          { label: "Prev. close", value: price(data.prev_close) },
          { label: "Volume", value: count(data.volume) },
          { label: "52-week high", value: price(data.week52_high) },
          { label: "52-week low", value: price(data.week52_low) },
          { label: "Market cap", value: cap(data.market_cap) },
          {
            label: "Shares outstanding",
            value: count(data.shares_outstanding),
          },
        ]);
      })
      .catch(() => {
        if (active) {
          setLiveQuote(EMPTY_QUOTE);
        }
      });

    return () => {
      active = false;
    };
  }, [current]);

  // --------------------------------------------------
  // 2. Fetch tracked companies
  // --------------------------------------------------

  useEffect(() => {
    let active = true;

    const loadTrackedCompanies = async () => {
      const all: TrackedCompany[] = [];

      let page = 1;
      let count = 0;

      do {
        const { data } = await apiClient.get(
          `/companies/?tracking=tracked&status=active&page=${page}`
        );

        const results: TrackedCompany[] = data.results ?? [];

        if (results.length === 0) break;

        all.push(...results);

        count = data.count ?? all.length;
        page += 1;
      } while (all.length < count);

      if (active) {
        setTrackedCompanies(all);
        setTrackedCompaniesLoaded(true);
      }
    };

    loadTrackedCompanies().catch((error) => {
      console.error("Error loading tracked companies:", error);

      if (active) {
        setTrackedCompanies([]);
        setTrackedCompaniesLoaded(true);
      }
    });

    return () => {
      active = false;
    };
  }, []);

  // --------------------------------------------------
  // 3. Fetch stock performance from backend
  // --------------------------------------------------

  useEffect(() => {
    let active = true;

    // Reset whenever the selection changes
    setPerformance(null);
    setPerformanceError(null);
    setPerformanceLoading(false);

    if (!current || !trackedCompaniesLoaded || !selectedCompany) {
      return () => {
        active = false;
      };
    }

    const loadPerformance = async () => {
      try {
        setPerformanceLoading(true);

        const { data } = await apiClient.get<StockPerformance>(
          `/companies/${selectedCompany.id}/performance/`
        );

        if (active) {
          setPerformance(data);
        }
      } catch (error) {
        console.error("Error fetching stock performance:", error);

        if (active) {
          setPerformance(null);
          setPerformanceError("Unable to load stock performance.");
        }
      } finally {
        if (active) {
          setPerformanceLoading(false);
        }
      }
    };

    loadPerformance();

    return () => {
      active = false;
    };
  }, [current, selectedCompany, trackedCompaniesLoaded]);

  // --------------------------------------------------
  // 4. Fetch stock valuation from backend
  // --------------------------------------------------

  useEffect(() => {
    let active = true;

    setValuation(null);
    setValuationError(null);
    setValuationLoading(false);

    if (!current || !trackedCompaniesLoaded || !selectedCompany) {
      return () => {
        active = false;
      };
    }

    const loadValuation = async () => {
      try {
        setValuationLoading(true);

        const { data } = await apiClient.get<StockValuation>(
          `/companies/${selectedCompany.id}/valuation/`
        );

        if (active) {
          setValuation(data);
        }
      } catch (error) {
        console.error("Error fetching stock valuation:", error);

        if (active) {
          setValuation(null);
          setValuationError("Unable to load stock valuation.");
        }
      } finally {
        if (active) {
          setValuationLoading(false);
        }
      }
    };

    loadValuation();

    return () => {
      active = false;
    };
  }, [current, selectedCompany, trackedCompaniesLoaded]);

  // --------------------------------------------------
  // 5. Fetch MASTER score from backend
  // --------------------------------------------------

  useEffect(() => {
    let active = true;

    setMasterScore(null);
    setMasterScoreError(null);
    setMasterScoreLoading(false);

    if (!current || !trackedCompaniesLoaded || !selectedCompany) {
      return () => {
        active = false;
      };
    }

    const loadMasterScore = async () => {
      try {
        setMasterScoreLoading(true);

        const { data } = await apiClient.get<MasterScoreResponse>(
          `/companies/${selectedCompany.id}/master-score/`
        );

        if (active) {
          setMasterScore(data);
        }
      } catch (error) {
        console.error("Error fetching MASTER score:", error);

        if (active) {
          setMasterScore(null);
          // Backend returns 404 when there are fewer than 200 crawled sessions
          setMasterScoreError(
            isAxiosError(error) && error.response?.status === 404
              ? "Not enough price history to compute a score."
              : "Unable to load MASTER score."
          );
        }
      } finally {
        if (active) {
          setMasterScoreLoading(false);
        }
      }
    };

    loadMasterScore();

    return () => {
      active = false;
    };
  }, [current, selectedCompany, trackedCompaniesLoaded]);

  // --------------------------------------------------
  // 6. Fetch 6-month price history for the chart
  // --------------------------------------------------

  useEffect(() => {
    let active = true;

    setCandles(null);
    setCandlesError(null);
    setCandlesLoading(false);

    if (!current || !trackedCompaniesLoaded || !selectedCompany) {
      return () => {
        active = false;
      };
    }

    const loadCandles = async () => {
      try {
        setCandlesLoading(true);

        const { data } = await apiClient.get<{ prices: PriceRow[] }>(
          `/companies/${selectedCompany.id}/prices/`,
          { params: { range: "180d" } }
        );

        if (!active) return;

        // Convert backend rows (strings) into the Candle shape the chart needs
        const rows: Candle[] = data.prices
          .map((p) => ({
            timestamp: new Date(`${p.date}T00:00:00`).getTime(),
            open: Number(p.open),
            high: Number(p.high),
            low: Number(p.low),
            close: Number(p.close),
            volume: Number(p.volume ?? 0),
          }))
          .filter((c) =>
            [c.timestamp, c.open, c.high, c.low, c.close].every(Number.isFinite)
          );

        setCandles(rows);
      } catch (error) {
        console.error("Error fetching price history:", error);

        if (active) {
          setCandles(null);
          setCandlesError("Unable to load price history.");
        }
      } finally {
        if (active) {
          setCandlesLoading(false);
        }
      }
    };

    loadCandles();

    return () => {
      active = false;
    };
  }, [current, selectedCompany, trackedCompaniesLoaded]);

  // --------------------------------------------------
  // 6b. Fetch technical indicators
  // --------------------------------------------------

  useEffect(() => {
    let active = true;

    setTechnicals(null);
    setTechnicalsError(null);
    setTechnicalsLoading(false);

    if (!current || !trackedCompaniesLoaded || !selectedCompany) {
      return () => {
        active = false;
      };
    }

    const load = async () => {
      try {
        setTechnicalsLoading(true);
        const { data } = await apiClient.get<TechnicalsResponse>(
          `/companies/${selectedCompany.id}/technicals/`
        );
        if (active) setTechnicals(data);
      } catch (error) {
        console.error("Error fetching technical indicators:", error);
        if (active) setTechnicalsError("Unable to load technical indicators.");
      } finally {
        if (active) setTechnicalsLoading(false);
      }
    };

    load();

    return () => {
      active = false;
    };
  }, [current, selectedCompany, trackedCompaniesLoaded]);

  // --------------------------------------------------
  // 6c. Fetch quarterly financials
  // --------------------------------------------------

  useEffect(() => {
    let active = true;

    setFinancials(null);
    setFinancialsError(null);
    setFinancialsLoading(false);

    if (!current || !trackedCompaniesLoaded || !selectedCompany) {
      return () => {
        active = false;
      };
    }

    const load = async () => {
      try {
        setFinancialsLoading(true);
        const { data } = await apiClient.get<FinancialsResponse>(
          `/companies/${selectedCompany.id}/financials/`
        );
        if (active) setFinancials(data);
      } catch (error) {
        console.error("Error fetching financials:", error);
        if (active) setFinancialsError("Unable to load quarterly financials.");
      } finally {
        if (active) setFinancialsLoading(false);
      }
    };

    load();

    return () => {
      active = false;
    };
  }, [current, selectedCompany, trackedCompaniesLoaded]);

  // --------------------------------------------------
  // 7. Formatting helpers
  // --------------------------------------------------

  // Nepali units: 1 Cr = 1e7, 1 Arba = 1e9
  const formatAmount = (v: number | null, unit: "rs" | "per_share") => {
    if (v == null || !Number.isFinite(v)) return "—";

    if (unit === "per_share") {
      return v.toLocaleString(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
      });
    }

    const abs = Math.abs(v);
    const sign = v < 0 ? "-" : "";

    if (abs >= 1e9) return `${sign}${(abs / 1e9).toFixed(2)} Arba`;
    if (abs >= 1e7) return `${sign}${(abs / 1e7).toFixed(2)} Cr`;
    if (abs >= 1e5) return `${sign}${(abs / 1e5).toFixed(2)} Lakh`;
    return v.toLocaleString();
  };

  const signalClass = (signal: string | null) => {
    switch (signal) {
      case "Bullish":
        return "text-emerald-400";
      case "Bearish":
        return "text-red-400";
      case "Overbought":
      case "Oversold":
        return "text-amber-400";
      default:
        return "text-text-secondary";
    }
  };

  const yoyCellClass = (yoy: string | null) =>
    yoy === "better"
      ? "bg-emerald-500/10"
      : yoy === "worse"
        ? "bg-red-500/15"
        : "";

  const formatCurrency = (value: number | string | null) => {
    if (value == null || !Number.isFinite(Number(value))) {
      return "—";
    }

    return `Rs. ${Number(value).toLocaleString(undefined, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })}`;
  };

  const formatRatio = (value: number | string | null) => {
    if (value == null || !Number.isFinite(Number(value))) {
      return "n/m";
    }

    return `${Number(value).toFixed(2)}x`;
  };

  const formatPercent = (value: number | string | null) => {
    if (value == null || !Number.isFinite(Number(value))) {
      return "—";
    }

    return `${Number(value).toFixed(2)}%`;
  };

  // --------------------------------------------------
  // 8. Display stock data (only meaningful when a symbol is selected)
  // --------------------------------------------------

  const displayName = quoteMeta?.name ?? selectedCompany?.name ?? current ?? "";

  const asOfText = quoteMeta
    ? `Data as of ${quoteMeta.asOf}`
    : "Loading quote date…";

  const quoteTiles = liveQuote ?? EMPTY_QUOTE;

  // Header price / change come from the last two real candles
  const lastCandle = candles?.[candles.length - 1];
  const prevCandle = candles?.[candles.length - 2];

  const ltp: number | null = lastCandle ? lastCandle.close : null;
  const change: number | null =
    lastCandle && prevCandle ? lastCandle.close - prevCandle.close : null;
  const changePct: number | null =
    change != null && prevCandle && prevCandle.close
      ? (change / prevCandle.close) * 100
      : null;

  const down = (change ?? 0) < 0;

  const gaugeProps = masterScore
    ? { score: masterScore.score, label: masterScore.band }
    : null;

  // --------------------------------------------------
  // 9. Stock symbol search
  // --------------------------------------------------

  const goToSymbol = (e: FormEvent) => {
    e.preventDefault();

    const sym = query.trim().toUpperCase();

    if (!sym) return;

    setQuery("");
    navigate(`/stocks/${encodeURIComponent(sym)}`);
  };

  // --------------------------------------------------
  // 10. Render page
  // --------------------------------------------------

  return (
    <div className="min-h-screen bg-bg-primary px-2 pb-8 text-text-primary antialiased">

      {/* Page header (a div, so the global `header` light-theme rule can't turn it white) */}
      <div className="flex flex-wrap items-start justify-between gap-3 px-1 pb-3 pt-4">
        <div className="min-w-0">
          {current ? (
            <>
              <h1 className="text-[15px] font-extrabold text-text-primary">
                {displayName}{" "}
                <span className="text-text-secondary">
                  ({current.toUpperCase()})
                </span>
              </h1>

              <p className="text-[10px] text-text-secondary">
                {selectedCompany?.sector && (
                  <>
                    {selectedCompany.sector} ·{" "}
                  </>
                )}
                <b className="text-text-primary">
                  {ltp != null ? `Rs. ${ltp.toFixed(2)}` : "—"}
                </b>{" "}
                {change != null && changePct != null && (
                  <span className={down ? "text-red-400" : "text-emerald-400"}>
                    {change.toFixed(2)} ({changePct.toFixed(2)}%)
                  </span>
                )}{" "}
                <span className="text-text-muted">{asOfText}</span>
              </p>
            </>
          ) : (
            <>
              <h1 className="text-[15px] font-extrabold text-text-primary">
                Stock Details
              </h1>
              <p className="text-[10px] text-text-secondary">
                Select a company to view its details
              </p>
            </>
          )}
        </div>

        {/* Symbol search */}
        <div className="flex items-center gap-2">
          <form
            role="search"
            onSubmit={goToSymbol}
            className="flex h-9 items-center gap-2 rounded-lg border border-bg-border bg-bg-elevated pl-3 pr-1.5 focus-within:border-emerald-500/70"
          >
            <svg
              viewBox="0 0 24 24"
              className="size-4 text-text-muted"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              aria-hidden
            >
              <circle cx="11" cy="11" r="7" />
              <path d="m20 20-3.5-3.5" strokeLinecap="round" />
            </svg>

            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Symbol…"
              aria-label="Stock symbol"
              autoComplete="off"
              spellCheck={false}
              className="w-32 bg-transparent text-xs uppercase text-text-primary outline-none placeholder:normal-case placeholder:text-text-muted"
            />

            <button
              type="submit"
              className="h-7 rounded-md bg-emerald-500 px-3 text-[10px] font-bold text-[#04130c] hover:bg-emerald-400"
            >
              Go
            </button>
          </form>
        </div>
      </div>

      {/* Tracked companies */}
      <section className="mb-3 rounded-lg border border-bg-border bg-bg-card p-3">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-xs font-bold text-text-primary">
              Tracked companies
            </h2>

            <p className="mt-0.5 text-[10px] text-text-muted">
              {trackedCompaniesLoaded
                ? `${trackedCompanies.length} active companies`
                : "Loading companies…"}
            </p>
          </div>

          {current && (
            <span className="rounded-full border border-emerald-700/60 bg-emerald-500/10 px-2.5 py-1 text-[10px] font-semibold text-emerald-300">
              Selected: {current.toUpperCase()}
            </span>
          )}
        </div>

        <div className="grid grid-cols-2 gap-1.5 pr-1 sm:grid-cols-3 md:grid-cols-4 xl:grid-cols-6">
          {trackedCompanies.map(({ symbol: sym, name }) => {
            const active = current?.toUpperCase() === sym.toUpperCase();

            return (
              <Link
                key={sym}
                to={`/stocks/${sym}`}
                title={name}
                className={`min-w-0 rounded-md border px-2.5 py-2 text-left transition-colors ${
                  active
                    ? "border-emerald-400/70 bg-emerald-500/10"
                    : "border-bg-border bg-bg-elevated hover:border-emerald-500/50 hover:bg-blue-500/10"
                }`}
              >
                <span
                  className={`block text-[10px] font-bold ${
                    active ? "text-emerald-300" : "text-text-primary"
                  }`}
                >
                  {sym}
                </span>

                <span className="mt-0.5 block truncate text-[9px] font-normal text-text-muted">
                  {name}
                </span>
              </Link>
            );
          })}

          {trackedCompaniesLoaded && trackedCompanies.length === 0 && (
            <p className="col-span-full py-4 text-center text-[11px] text-text-muted">
              No active tracked companies available.
            </p>
          )}
        </div>
      </section>

      {/* ---------- State 1: nothing selected -> friendly empty state ---------- */}
      {!current && (
        <section className="flex flex-col items-center justify-center rounded-lg border border-dashed border-bg-border bg-bg-card px-4 py-16 text-center">
          <svg
            viewBox="0 0 24 24"
            className="mb-3 size-10 text-text-muted"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            aria-hidden
          >
            <path
              d="M3 3v18h18M7 15l4-4 3 3 5-6"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>

          <h2 className="text-sm font-bold text-text-primary">
            Select a company to view its details
          </h2>

          <p className="mt-1 max-w-sm text-[11px] text-text-muted">
            Search a symbol above or pick one of the tracked companies to see
            its price chart, MASTER score, performance and valuation.
          </p>
        </section>
      )}

      {/* ---------- State 2: symbol given but not a tracked company ---------- */}
      {symbolNotFound && (
        <section className="flex flex-col items-center justify-center rounded-lg border border-bg-border bg-bg-card px-4 py-16 text-center">
          <h2 className="text-sm font-bold text-text-primary">
            “{current?.toUpperCase()}” is not a tracked company
          </h2>

          <p className="mt-1 max-w-sm text-[11px] text-text-muted">
            Check the symbol, or choose one of the tracked companies above.
          </p>

          <Link
            to="/stocks"
            className="mt-4 rounded-md bg-emerald-500 px-3 py-1.5 text-[10px] font-bold text-[#04130c] hover:bg-emerald-400"
          >
            Clear selection
          </Link>
        </section>
      )}

      {/* ---------- State 3: valid selected company -> full details ---------- */}
      {current && !symbolNotFound && (
        <div className="space-y-2">

          {/* Row 1: chart + master score */}
          <div className="grid gap-2 lg:grid-cols-[1fr_230px]">

            <Panel
              title="Price — last 6 months"
              right={
                <a href="#chart" className="text-emerald-400 hover:underline">
                  Full chart
                </a>
              }
            >
              {!trackedCompaniesLoaded || candlesLoading ? (
                <p className="py-16 text-center text-xs text-text-secondary">
                  Loading price history...
                </p>
              ) : candlesError ? (
                <p className="py-16 text-center text-xs text-red-400">
                  {candlesError}
                </p>
              ) : candles && candles.length > 0 ? (
                <PriceChart data={candles} />
              ) : (
                <p className="py-16 text-center text-xs text-text-muted">
                  No price history available.
                </p>
              )}

              <div className="mt-2 grid grid-cols-2 gap-1.5 md:grid-cols-4">
                {quoteTiles.map((m) => (
                  <Tile key={m.label} {...m} />
                ))}
              </div>
            </Panel>

            <Panel
              title="MASTER score"
              right={
                masterScore ? (
                  <span className="text-text-muted">
                    {new Date(`${masterScore.as_of}T00:00:00`).toLocaleDateString()}
                  </span>
                ) : undefined
              }
            >
              {!trackedCompaniesLoaded || masterScoreLoading ? (
                <p className="py-8 text-center text-xs text-text-secondary">
                  Calculating score...
                </p>
              ) : masterScoreError ? (
                <p className="py-8 text-center text-xs text-text-muted">
                  {masterScoreError}
                </p>
              ) : gaugeProps ? (
                <>
                  <MasterGauge {...gaugeProps} />

                  <dl className="mt-3 space-y-1 text-[9px]">
                    <div className="flex justify-between">
                      <dt className="text-text-muted">Promoter holding</dt>
                      <dd className="font-bold text-text-primary">
                        {formatPercent(masterScore?.holding?.promoter ?? null)}
                      </dd>
                    </div>

                    <div className="flex justify-between">
                      <dt className="text-text-muted">Public holding</dt>
                      <dd className="font-bold text-text-primary">
                        {formatPercent(masterScore?.holding?.public ?? null)}
                      </dd>
                    </div>
                  </dl>

                  {masterScore?.components && (
                    <dl className="mt-3 space-y-1 border-t border-bg-border pt-2 text-[9px]">
                      {Object.entries(masterScore.components).map(([k, v]) => (
                        <div key={k} className="flex justify-between">
                          <dt className="capitalize text-text-muted">{k}</dt>
                          <dd className="font-bold text-text-primary">{v.toFixed(0)}</dd>
                        </div>
                      ))}
                    </dl>
                  )}
                </>
              ) : (
                <p className="py-8 text-center text-xs text-text-muted">
                  No score available.
                </p>
              )}
            </Panel>
          </div>

          {/* Row 2: performance + valuation */}
          <div className="grid gap-2 lg:grid-cols-2">

            {/* Backend Stock Performance */}
            <Panel title="Stock performance">
              {!trackedCompaniesLoaded || performanceLoading ? (
                <p className="py-5 text-center text-xs text-text-secondary">
                  Loading stock performance...
                </p>
              ) : performanceError ? (
                <p className="py-5 text-center text-xs text-red-400">
                  {performanceError}
                </p>
              ) : performance ? (
                <div className="space-y-3">

                  {/* Price changes */}
                  <div>
                    <h3 className="mb-1.5 text-[10px] font-bold text-text-secondary">
                      PRICE CHANGES
                    </h3>

                    <div className="grid grid-cols-2 gap-1.5 md:grid-cols-3">
                      {[
                        { label: "1 Week", value: performance.week_change },
                        { label: "1 Month", value: performance.month_change },
                        { label: "3 Months", value: performance.three_month_change },
                        { label: "6 Months", value: performance.six_month_change },
                        { label: "YTD", value: performance.ytd_change },
                        { label: "1 Year", value: performance.year_change },
                      ].map((item) => (
                        <Tile
                          key={item.label}
                          label={item.label}
                          value={
                            item.value == null
                              ? "—"
                              : `${item.value > 0 ? "+" : ""}${item.value.toFixed(2)}%`
                          }
                        />
                      ))}
                    </div>
                  </div>

                  {/* Price range */}
                  <div>
                    <h3 className="mb-1.5 text-[10px] font-bold text-text-secondary">
                      PRICE RANGE
                    </h3>

                    <div className="grid grid-cols-2 gap-1.5 md:grid-cols-3">
                      {[
                        { label: "3M High", value: performance.three_month_high },
                        { label: "3M Low", value: performance.three_month_low },
                        { label: "52W High", value: performance.fifty_two_week_high },
                        { label: "52W Low", value: performance.fifty_two_week_low },
                        {
                          label: "Distance from 52W High",
                          value: performance.from_52_week_high,
                        },
                        {
                          label: "Distance from 52W Low",
                          value: performance.from_52_week_low,
                        },
                      ].map((item) => (
                        <Tile
                          key={item.label}
                          label={item.label}
                          value={
                            item.value == null
                              ? "—"
                              : `${item.value.toFixed(2)}%`
                          }
                        />
                      ))}
                    </div>
                  </div>

                  {/* Average close */}
                  <div>
                    <h3 className="mb-1.5 text-[10px] font-bold text-text-secondary">
                      AVERAGE CLOSE
                    </h3>

                    <div className="grid grid-cols-2 gap-1.5">
                      <Tile
                        label="180 Sessions"
                        value={
                          performance.avg_price_180d == null
                            ? "—"
                            : `Rs. ${performance.avg_price_180d.toFixed(2)}`
                        }
                      />

                      <Tile
                        label="350 Sessions"
                        value={
                          performance.avg_price_350d == null
                            ? "—"
                            : `Rs. ${performance.avg_price_350d.toFixed(2)}`
                        }
                      />
                    </div>
                  </div>

                  {/* Average volume */}
                  <div>
                    <h3 className="mb-1.5 text-[10px] font-bold text-text-secondary">
                      AVERAGE VOLUME
                    </h3>

                    <div className="grid grid-cols-2 gap-1.5 md:grid-cols-4">
                      {[
                        { label: "1 Week", value: performance.avg_volume_1w },
                        { label: "1 Month", value: performance.avg_volume_1m },
                        { label: "6 Months", value: performance.avg_volume_6m },
                        { label: "12 Months", value: performance.avg_volume_12m },
                      ].map((item) => (
                        <Tile
                          key={item.label}
                          label={item.label}
                          value={
                            item.value == null
                              ? "—"
                              : item.value.toLocaleString(undefined, {
                                  maximumFractionDigits: 0,
                                })
                          }
                        />
                      ))}
                    </div>
                  </div>

                  {/* Risk indicators */}
                  <div>
                    <h3 className="mb-1.5 text-[10px] font-bold text-text-secondary">
                      RISK INDICATORS
                    </h3>

                    <div className="grid grid-cols-2 gap-1.5">
                      <Tile
                        label="1M Daily Volatility"
                        value={
                          performance.daily_volatility_1m == null
                            ? "—"
                            : `${performance.daily_volatility_1m.toFixed(2)}%`
                        }
                      />

                      <Tile
                        label="Beta vs NEPSE"
                        value={
                          performance.beta_vs_nepse_1y?.beta == null
                            ? "—"
                            : performance.beta_vs_nepse_1y.beta.toFixed(2)
                        }
                      />
                    </div>

                    {performance.beta_vs_nepse_1y && (
                      <p className="mt-1.5 text-[9px] text-text-muted">
                        Beta observations: {performance.beta_vs_nepse_1y.observations} ·
                        Status: {performance.beta_vs_nepse_1y.status.replace("_", " ")}
                      </p>
                    )}
                  </div>
                </div>
              ) : (
                <p className="py-5 text-center text-xs text-text-muted">
                  No performance data available.
                </p>
              )}
            </Panel>

            {/* Backend Stock Valuation */}
            <Panel
              title="Valuation"
              right={
                valuation
                  ? `${valuation.fiscal_year} · Q${valuation.quarter}`
                  : "Quarterly fundamentals"
              }
            >
              {!trackedCompaniesLoaded || valuationLoading ? (
                <p className="py-5 text-center text-xs text-text-secondary">
                  Loading stock valuation...
                </p>
              ) : valuationError ? (
                <p className="py-5 text-center text-xs text-red-400">
                  {valuationError}
                </p>
              ) : valuation ? (
                <>
                  <div className="grid grid-cols-2 gap-1.5 md:grid-cols-3">
                    <Tile label="P/E Ratio" value={formatRatio(valuation.pe)} />
                    <Tile label="P/B Ratio" value={formatRatio(valuation.pb)} />
                    <Tile label="EPS (Annualized)" value={formatCurrency(valuation.eps)} />
                    <Tile label="Book Value / Share" value={formatCurrency(valuation.bv)} />
                    <Tile label="DPPS" value={formatCurrency(valuation.dpps)} />
                    <Tile label="DPPS Yield" value={formatPercent(valuation.dpps_yield)} />
                    <Tile
                      label={`${valuation.avg_window_years}-Year Avg. DPPS`}
                      value={formatCurrency(valuation.avg_dpps)}
                    />
                    <Tile label="Average DPPS Yield" value={formatPercent(valuation.avg_yield)} />
                    <Tile label="DPPS Growth (YoY)" value={formatPercent(valuation.yoy)} />
                  </div>

                  <div className="mt-3 border-t border-bg-border pt-2">
                    <p className="text-[9px] text-text-muted">
                      Reporting period: {valuation.fiscal_year}, Q{valuation.quarter}
                      {" · "}
                      Reported: {valuation.reported_on ?? "—"}
                    </p>

                    <p className="mt-1 text-[9px] text-text-muted">
                      Latest crawled price: {formatCurrency(valuation.ltp)}
                      {" · "}
                      Price date: {valuation.price_date ?? "—"}
                    </p>

                    <p className="mt-1 text-[9px] text-text-muted">
                      Average DPPS calculated using {valuation.avg_years_used}/
                      {valuation.avg_window_years} available years.
                    </p>

                    <p className="mt-2 text-[8px] text-text-muted">
                      DPPS means Distributable Profit Per Share. DPPS yield is not
                      actual cash dividend yield.
                      {" "}
                      <a href="#dividends" className="text-emerald-400 hover:underline">
                        Full dividend history
                      </a>
                    </p>
                  </div>
                </>
              ) : (
                <p className="py-5 text-center text-xs text-text-muted">
                  No valuation data available.
                </p>
              )}
            </Panel>
          </div>

          {/* Row 3: technical indicators (live) */}
          <Panel
            title="Technical indicators"
            right={
              technicals?.as_of ? (
                <span className="text-text-muted">
                  As of {new Date(`${technicals.as_of}T00:00:00`).toLocaleDateString()}
                </span>
              ) : undefined
            }
          >
            {!trackedCompaniesLoaded || technicalsLoading ? (
              <p className="py-5 text-center text-xs text-text-secondary">
                Loading technical indicators...
              </p>
            ) : technicalsError ? (
              <p className="py-5 text-center text-xs text-red-400">
                {technicalsError}
              </p>
            ) : technicals && technicals.indicators.length > 0 ? (
              <>
                {technicals.status === "insufficient_history" && (
                  <p className="mb-2 text-[9px] text-amber-400">
                    Limited price history: some indicators may be unavailable.
                  </p>
                )}

                {technicals.possible_corporate_action && (
                  <p className="mb-2 text-[9px] text-amber-400">
                    A possible corporate action (bonus / right share) was detected.
                    Moving averages and MACD may be distorted.
                  </p>
                )}

                <div className="divide-y divide-bg-border">
                  {technicals.indicators.map((ind) => (
                    <div
                      key={ind.key}
                      className="grid grid-cols-3 items-center py-1.5 text-[10px]"
                    >
                      <span className="text-text-secondary">{ind.label}</span>
                      <span className="text-center font-bold text-text-primary">
                        {ind.value == null ? "—" : ind.value.toFixed(2)}
                      </span>
                      <span className={`text-right font-bold ${signalClass(ind.signal)}`}>
                        {ind.signal ?? "—"}
                      </span>
                    </div>
                  ))}
                </div>

                {technicals.pivots && (
                  <div className="mt-3">
                    <h3 className="mb-1.5 text-[9px] font-bold uppercase text-text-muted">
                      Pivot levels (classic)
                    </h3>

                    <div className="grid grid-cols-4 gap-1.5 md:grid-cols-7">
                      {(["s3", "s2", "s1", "pp", "r1", "r2", "r3"] as const).map((k) => (
                        <div
                          key={k}
                          className={`rounded-md border px-2 py-1.5 text-center ${
                            k === "pp"
                              ? "border-emerald-400/70 bg-emerald-500/10"
                              : "border-bg-border bg-bg-elevated"
                          }`}
                        >
                          <div className="text-[8px] font-bold uppercase text-text-muted">
                            {k}
                          </div>
                          <div className="text-[10px] font-bold text-text-primary">
                            {technicals.pivots?.[k] == null
                              ? "—"
                              : technicals.pivots[k]!.toFixed(2)}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <p className="py-5 text-center text-xs text-text-muted">
                No technical data available.
              </p>
            )}
          </Panel>

          {/* Row 4: quarterly financials (live) */}
          <Panel
            title="Key financials — last 8 quarters"
            right={
              <span className="flex items-center gap-2">
                <i className="inline-block size-1.5 rounded-full bg-red-500" /> worse
                <i className="inline-block size-1.5 rounded-full bg-emerald-500" /> better vs same quarter last year
              </span>
            }
          >
            {!trackedCompaniesLoaded || financialsLoading ? (
              <p className="py-5 text-center text-xs text-text-secondary">
                Loading quarterly financials...
              </p>
            ) : financialsError ? (
              <p className="py-5 text-center text-xs text-red-400">
                {financialsError}
              </p>
            ) : financials && financials.rows.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[640px] border-collapse text-[10px]">
                  <thead>
                    <tr>
                      <th className="py-1.5 pr-2 text-left text-[9px] font-normal uppercase text-text-muted">
                        Particulars
                      </th>
                      {financials.quarters.map((q) => (
                        <th
                          key={`${q.fiscal_year}-${q.quarter}`}
                          className="px-2 py-1.5 text-right font-normal text-text-muted"
                        >
                          <div className={q.is_latest ? "font-bold text-emerald-400" : ""}>
                            Q{q.quarter}
                          </div>
                          <div className="text-[8px]">{q.fiscal_year}</div>
                          {q.is_latest && <div className="text-[8px]">latest</div>}
                          {!q.filed && (
                            <div className="text-[8px] text-amber-400">not filed</div>
                          )}
                        </th>
                      ))}
                    </tr>
                  </thead>

                  <tbody>
                    {financials.rows.map((row) => (
                      <tr key={row.key} className="border-t border-bg-border">
                        <td className="py-1.5 pr-2 text-text-secondary">{row.label}</td>
                        {row.values.map((cell, i) => (
                          <td
                            key={i}
                            className={`px-2 py-1.5 text-right font-bold text-text-primary ${yoyCellClass(cell.yoy)}`}
                          >
                            {formatAmount(cell.value, row.unit)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="py-5 text-center text-xs text-text-muted">
                No quarterly financials available.
              </p>
            )}
          </Panel>
        </div>
      )}
    </div>
  );
}