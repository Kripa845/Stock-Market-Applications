
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { mockStock } from "./mock";
import type { StockDetail } from "./types";
import { Panel, Tile } from "./ui";
import PriceChart from "./Pricechart";
import MasterGauge from "./Mastergauge";
import RangeBars from "./Rangebars";
import Technicals from "./Technicals";
import KeyFinancials from "./Keyfinancials";

// Quick-link chips next to the search box. Change to your own symbols.
const QUICK_SYMBOLS = ["NICA", "NABIL", "NTC", "UPPER", "SHIVM"];

/**
 * Drop-in page. Pass real data from your API; falls back to mock data for now.
 * e.g. <Route path="/stocks/:symbol" element={<StockDetailPage />} />
 */
export default function StockDetailPage({ stock = mockStock }: { stock?: StockDetail }) {
  const down = stock.change < 0;
  const navigate = useNavigate();
  const { symbol: current } = useParams();
  const [query, setQuery] = useState("");

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
            {stock.name} <span className="text-slate-400">({stock.symbol})</span>
          </h1>
          <p className="text-[10px] text-slate-400">
            {stock.sector} ·{" "}
            <b className="text-white">Rs. {stock.ltp.toFixed(2)}</b>{" "}
            <span className={down ? "text-red-400" : "text-emerald-400"}>
              {stock.change.toFixed(2)} ({stock.changePct.toFixed(2)}%)
            </span>{" "}
            <span className="text-slate-500">{stock.asOf}</span>
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

          {QUICK_SYMBOLS.map((sym) => {
            const active = current?.toUpperCase() === sym;
            return (
              <Link
                key={sym}
                to={`/stocks/${sym}`}
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
      </header>

      <div className="space-y-2">
        {/* Row 1: chart + master score */}
        <div className="grid gap-2 lg:grid-cols-[1fr_230px]">
          <Panel
            title="Price — last 6 months"
            right={<a href="#chart" className="text-emerald-400 hover:underline">Full chart</a>}
          >
            <PriceChart data={stock.candles} />
            <div className="mt-2 grid grid-cols-2 gap-1.5 md:grid-cols-4">
              {stock.quote.map((m) => (
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