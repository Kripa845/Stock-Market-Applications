
import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { mockStock } from "./mock";
import type { StockDetail } from "./types";
import { Panel, Tile } from "./ui";
import PriceChart from "./Pricechart";
import MasterGauge from "./Mastergauge";
import RangeBars from "./Rangebars";
import Technicals from "./Technicals";
import KeyFinancials from "./Keyfinancials";
import apiClient from "../api/client";

const EMPTY_QUOTE = [
  "Open", "High / Low", "Prev. close", "Volume", "52-week high", "52-week low", "Market cap", "Shares outstanding",
].map((label) => ({ label, value: "—" }));

/**
 * Drop-in page. Pass real data from your API; falls back to mock data for now.
 * e.g. <Route path="/stocks/:symbol" element={<StockDetailPage />} />
 */
export default function StockDetailPage({ stock = mockStock }: { stock?: StockDetail }) {
  const [liveQuote, setLiveQuote] = useState<StockDetail["quote"] | null>(null);
  const [trackedCompanies, setTrackedCompanies] = useState<{ symbol: string; name: string }[]>([]);
  const [quoteMeta, setQuoteMeta] = useState<{ name: string; asOf: string } | null>(null);
  const navigate = useNavigate();
  const { symbol: current } = useParams();
  const [query, setQuery] = useState("");

  useEffect(() => {
    let active = true;
    setLiveQuote(null);
    setQuoteMeta(null);
    if (!current) return () => { active = false; };
    apiClient.get(`/companies/${encodeURIComponent(current)}/quote/`).then(({ data }) => {
      if (!active) return;
      setQuoteMeta({
        name: data.name,
        asOf: data.as_of ? new Date(`${data.as_of}T00:00:00`).toLocaleDateString() : "No crawled quote",
      });
      const price = (v: number | string | null) => v == null ? "—" : Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 });
      const count = (v: number | string | null) => v == null ? "—" : Number(v).toLocaleString();
      const cap = (v: number | string | null) => v == null ? "—" : `Rs. ${Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
      setLiveQuote([
        { label: "Open", value: price(data.open) },
        { label: "High / Low", value: `${price(data.high)} / ${price(data.low)}` },
        { label: "Prev. close", value: price(data.prev_close) },
        { label: "Volume", value: count(data.volume) },
        { label: "52-week high", value: price(data.week52_high) },
        { label: "52-week low", value: price(data.week52_low) },
        { label: "Market cap", value: cap(data.market_cap) },
        { label: "Shares outstanding", value: count(data.shares_outstanding) },
      ]);
    }).catch(() => {
      if (active) setLiveQuote([
        "Open", "High / Low", "Prev. close", "Volume", "52-week high", "52-week low", "Market cap", "Shares outstanding",
      ].map((label) => ({ label, value: "—" })));
    });
    return () => { active = false; };
  }, [current]);

  useEffect(() => {
    let active = true;
    const loadTrackedCompanies = async () => {
      const all: { symbol: string; name: string }[] = [];
      let page = 1;
      let count = 0;
      do {
        const { data } = await apiClient.get(`/companies/?tracking=tracked&status=active&page=${page}`);
        all.push(...(data.results ?? []));
        count = data.count ?? all.length;
        page += 1;
      } while (all.length < count && page < 100);
      if (active) setTrackedCompanies(all);
    };
    loadTrackedCompanies().catch(() => { if (active) setTrackedCompanies([]); });
    return () => { active = false; };
  }, []);

  const displayStock = {
    ...stock,
    name: quoteMeta?.name ?? stock.name,
    symbol: current?.toUpperCase() ?? stock.symbol,
    asOf: quoteMeta ? `Data as of ${quoteMeta.asOf}` : current ? "Loading quote date…" : stock.asOf,
    quote: current ? liveQuote ?? EMPTY_QUOTE : stock.quote,
  };
  const down = displayStock.change < 0;

  const goToSymbol = (e: FormEvent) => {
    e.preventDefault();
    const sym = query.trim().toUpperCase();
    if (!sym) return;
    setQuery("");
    navigate(`/stocks/${encodeURIComponent(sym)}`);
  };

  return (
    <div className="min-h-screen bg-[#060b16] px-2 pb-8 text-slate-200 antialiased">
      {/* Header */}
      <header className="flex flex-wrap items-start justify-between gap-2 px-1 pb-2 pt-3">
        <div>
          <h1 className="text-[15px] font-extrabold text-white">
            {displayStock.name} <span className="text-slate-400">({displayStock.symbol})</span>
          </h1>
          <p className="text-[10px] text-slate-400">
            {displayStock.sector} ·{" "}
            <b className="text-white">Rs. {displayStock.ltp.toFixed(2)}</b>{" "}
            <span className={down ? "text-red-400" : "text-emerald-400"}>
              {displayStock.change.toFixed(2)} ({displayStock.changePct.toFixed(2)}%)
            </span>{" "}
            <span className="text-slate-500">{displayStock.asOf}</span>
          </p>
        </div>

        {/* Symbol search + quick chips */}
        <div className="flex flex-wrap items-center gap-1.5">
          <form
            role="search"
            onSubmit={goToSymbol}
            className="flex h-7 items-center gap-1.5 rounded-full border border-[#1e2d47] bg-[#0c1626] pl-2.5 pr-1 focus-within:border-emerald-500/70"
          >
            <svg viewBox="0 0 24 24" className="size-3 text-slate-500" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
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
              className="w-24 bg-transparent text-[10px] uppercase text-slate-100 outline-none placeholder:normal-case placeholder:text-slate-500"
            />
            <button
              type="submit"
              className="h-5 rounded-full bg-emerald-500 px-2.5 text-[9px] font-bold text-[#04130c] hover:bg-emerald-400"
            >
              Go
            </button>
          </form>

          <div className="flex max-h-16 max-w-full flex-wrap gap-1 overflow-y-auto">
          {trackedCompanies.map(({ symbol: sym, name }) => {
            const active = current?.toUpperCase() === sym;
            return (
              <Link
                key={sym}
                to={`/stocks/${sym}`}
                title={name}
                className={`rounded-full border px-2 py-0.5 text-[8px] font-semibold tracking-wide ${
                  active
                    ? "border-emerald-400 bg-emerald-500/20 text-emerald-300"
                    : "border-emerald-700/70 text-slate-300 hover:border-emerald-400 hover:text-white"
                }`}
              >
                {sym}
              </Link>
            );
          })}
          </div>
        </div>
      </header>

      <div className="space-y-2">
        {/* Row 1: chart + master score */}
        <div className="grid gap-2 lg:grid-cols-[1fr_230px]">
          <Panel
            title="Price — last 6 months"
            right={<a href="#chart" className="text-emerald-400 hover:underline">Full chart</a>}
          >
            <PriceChart data={displayStock.candles} />
            <div className="mt-2 grid grid-cols-2 gap-1.5 md:grid-cols-4">
              {displayStock.quote.map((m) => (
                <Tile key={m.label} {...m} />
              ))}
            </div>
          </Panel>

          <Panel title="MASTER score">
            <MasterGauge {...stock.masterScore} />
            <dl className="mt-3 space-y-1 text-[9px]">
              <div className="flex justify-between">
                <dt className="text-slate-500">Promoter holding</dt>
                <dd className="font-bold text-white">{stock.holding.promoter}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-slate-500">Public holding</dt>
                <dd className="font-bold text-white">{stock.holding.public}</dd>
              </div>
            </dl>
          </Panel>
        </div>

        {/* Row 2: performance + valuation */}
        <div className="grid gap-2 lg:grid-cols-2">
          <Panel title="Stock performance">
            <div className="grid grid-cols-2 gap-1.5 md:grid-cols-3">
              {stock.performance.map((m) => (
                <Tile key={m.label} {...m} />
              ))}
            </div>
          </Panel>

          <Panel title="Valuation" right={`Filed ${stock.valuationFiled.replace("filed ", "")}`}>
            <div className="grid grid-cols-2 gap-1.5 md:grid-cols-3">
              {stock.valuation.map((m) => (
                <Tile key={m.label} {...m} />
              ))}
            </div>
            <p className="mt-2 text-[8px] text-slate-500">
              {stock.valuationNote}{" "}
              <a href="#dividends" className="text-emerald-400 hover:underline">Full dividend history</a>
            </p>
          </Panel>
        </div>

        {/* Row 3: peers + technicals */}
        <div className="grid gap-2 lg:grid-cols-2">
          <Panel title={`Key indicators vs ${stock.sector}`} className="min-h-[190px]">
            <RangeBars rows={stock.rangeMetrics} />
          </Panel>
          <Panel title="Technical indicators">
            <Technicals rows={stock.technicals} pivots={stock.pivots} />
          </Panel>
        </div>

        {/* Row 4: financials */}
        <Panel
          title="Key financials — last 8 quarters"
          right={
            <span className="flex items-center gap-2">
              <i className="inline-block size-1.5 rounded-full bg-red-500" /> worse
              <i className="inline-block size-1.5 rounded-full bg-emerald-500" /> better vs same quarter last year
              · amounts in Rs · per-share in Rs
            </span>
          }
        >
          <KeyFinancials quarters={stock.quarters} rows={stock.financials} />
        </Panel>
      </div>
    </div>
  );
}
