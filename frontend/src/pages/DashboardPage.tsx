import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { listCompanies } from "../api/companies";
import { listAllDailyPrices } from "../api/marketData";
import type { Company, DailyPrice } from "../types";

interface CompanySummary {
  latestClose: number | null;
  latestDate: string | null;
  dayChangePct: number | null;
  volatility: number;
  totalVolume: number;
  days: number;
}

type SummaryMap = Record<number, CompanySummary>;

function summarize(prices: DailyPrice[]): SummaryMap {
  // Group by company id, compute latest close, change vs prior day,
  // and a simple volatility measure (stdev of daily % change).
  const byCompany: Record<number, DailyPrice[]> = {};
  for (const row of prices) {
    (byCompany[row.company] ||= []).push(row);
  }

  const summaries: SummaryMap = {};
  for (const [companyIdStr, rows] of Object.entries(byCompany)) {
    const companyId = Number(companyIdStr);
    const sorted = rows.slice().sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
    const closes = sorted.map((r) => Number(r.close));
    const changes: number[] = [];
    for (let i = 1; i < closes.length; i++) {
      if (closes[i - 1] > 0) changes.push((closes[i] - closes[i - 1]) / closes[i - 1]);
    }
    const mean = changes.reduce((a, b) => a + b, 0) / (changes.length || 1);
    const variance = changes.reduce((a, b) => a + (b - mean) ** 2, 0) / (changes.length || 1);
    const volatility = Math.sqrt(variance);

    const latest = sorted[sorted.length - 1];
    const prev = sorted[sorted.length - 2];
    const dayChangePct =
      prev && Number(prev.close) > 0 ? ((Number(latest.close) - Number(prev.close)) / Number(prev.close)) * 100 : null;
    const totalVolume = sorted.reduce((a, r) => a + Number(r.volume), 0);

    summaries[companyId] = {
      latestClose: latest ? Number(latest.close) : null,
      latestDate: latest ? latest.date : null,
      dayChangePct,
      volatility,
      totalVolume,
      days: sorted.length,
    };
  }
  return summaries;
}

interface RankResult {
  company: Company;
  value: number;
}

function rank(companies: Company[], summaries: SummaryMap, key: keyof CompanySummary, descending: boolean): RankResult | null {
  let best: RankResult | null = null;
  for (const c of companies) {
    const s = summaries[c.id];
    if (!s) continue;
    const value = s[key];
    if (typeof value !== "number" || Number.isNaN(value)) continue;
    if (!best || (descending ? value > best.value : value < best.value)) {
      best = { company: c, value };
    }
  }
  return best;
}

export default function DashboardPage() {
  const [companies, setCompanies] = useState<Company[]>([]);
  const [summaries, setSummaries] = useState<SummaryMap>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    Promise.all([listCompanies(), listAllDailyPrices()])
      .then(([companiesData, pricesData]) => {
        if (cancelled) return;
        setCompanies(companiesData);
        setSummaries(summarize(pricesData));
      })
      .catch((err: unknown) => {
        if (!cancelled) setError(err);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const mostVolatile = useMemo(() => rank(companies, summaries, "volatility", true), [companies, summaries]);
  const mostActive = useMemo(() => rank(companies, summaries, "totalVolume", true), [companies, summaries]);
  const topGainer = useMemo(() => rank(companies, summaries, "dayChangePct", true), [companies, summaries]);

  if (loading) return <div className="page-loading">Loading watchlist…</div>;

  if (error) {
    return (
      <div className="empty-state error">
        Couldn't reach the backend at the configured API URL. Confirm the Django server is
        running and <code>VITE_API_BASE_URL</code> is set correctly.
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-header">
        <h1>Watchlist</h1>
        <p className="page-subtitle">{companies.length} tracked companies</p>
      </div>

      <section className="highlight-row">
        <HighlightCard
          title="Most volatile"
          item={mostVolatile}
          metricLabel="σ daily change"
          formatter={(v) => `${(v * 100).toFixed(2)}%`}
        />
        <HighlightCard
          title="Most active (volume)"
          item={mostActive}
          metricLabel="total volume"
          formatter={(v) => v.toLocaleString()}
        />
        <HighlightCard
          title="Top mover today"
          item={topGainer}
          metricLabel="day change"
          formatter={(v) => `${v.toFixed(2)}%`}
        />
      </section>

      <div className="table-wrap">
        <table className="data-table">
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Name</th>
              <th>Sector</th>
              <th>Latest close</th>
              <th>Day change</th>
              <th>Days of data</th>
            </tr>
          </thead>
          <tbody>
            {companies.map((c) => {
              const s = summaries[c.id];
              return (
                <tr key={c.id}>
                  <td>
                    <Link to={`/companies/${c.id}`} className="table-link">
                      {c.symbol}
                    </Link>
                  </td>
                  <td>{c.name}</td>
                  <td>{c.sector}</td>
                  <td>{s?.latestClose ?? "—"}</td>
                  <td
                    className={
                      s?.dayChangePct != null ? (s.dayChangePct > 0 ? "positive" : s.dayChangePct < 0 ? "negative" : "") : ""
                    }
                  >
                    {s?.dayChangePct != null ? `${s.dayChangePct.toFixed(2)}%` : "—"}
                  </td>
                  <td>{s?.days ?? 0}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

interface HighlightCardProps {
  title: string;
  item: RankResult | null;
  metricLabel: string;
  formatter: (value: number) => string;
}

function HighlightCard({ title, item, metricLabel, formatter }: HighlightCardProps) {
  return (
    <div className="highlight-card">
      <div className="stat-label">{title}</div>
      {item ? (
        <>
          <div className="stat-value">
            <Link to={`/companies/${item.company.id}`}>{item.company.symbol}</Link>
          </div>
          <div className="stat-sub">
            {metricLabel}: {formatter(item.value)}
          </div>
        </>
      ) : (
        <div className="stat-sub">Not enough data yet</div>
      )}
    </div>
  );
}
