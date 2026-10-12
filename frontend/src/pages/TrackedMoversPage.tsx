import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { fmt, Logo, type MoverRow, type Side } from "./TrackedMoverCards";

interface ListResponse {
  as_of: string | null;
  period: string;
  side: Side;
  sectors: string[];
  total: number;
  page: number;
  page_size: number;
  rows: MoverRow[];
  reason?: string;
}

const EMPTY: ListResponse = {
  as_of: null,
  period: "1D",
  side: "gainer",
  sectors: [],
  total: 0,
  page: 1,
  page_size: 20,
  rows: [],
};

// [label, period key]. NEPSE trades 5 days a week, so "5 Days" and "1 Week"
// are the same 5 sessions; "1 Week" is left out on purpose.
const TABS: ReadonlyArray<readonly [string, string]> = [
  ["Today", "1D"],
  ["2 Days", "2S"],
  ["3 Days", "3S"],
  ["5 Days", "5S"],
  ["7 Days", "7S"],
  ["1 Month", "1M"],
  ["3 Months", "3M"],
  ["4 Months", "4M"],
  ["6 Months", "6M"],
  ["1 Year", "1Y"],
];

const PAGE_SIZES = [10, 20, 50, 100] as const;

// "2026-10-09, 2:59:59 PM" in Nepal time.
function fmtTime(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  const tz = "Asia/Kathmandu";
  const date = d.toLocaleDateString("en-CA", { timeZone: tz });
  const time = d.toLocaleTimeString("en-US", { timeZone: tz });
  return `${date}, ${time}`;
}

export default function TrackedMoversPage() {
  const [sp, setSp] = useSearchParams();

  const side: Side = sp.get("side") === "loser" ? "loser" : "gainer";
  const up = side === "gainer";
  const period = sp.get("period") ?? "1D";
  const sector = sp.get("sector") ?? "";
  const adjusted = sp.get("adjusted") !== "false";
  const pageSize = Number(sp.get("page_size") ?? 20);
  const page = Number(sp.get("page") ?? 1);

  const [data, setData] = useState<ListResponse>(EMPTY);
  const [loading, setLoading] = useState(false);

  // Update URL params; any filter change resets to page 1.
  const set = (patch: Record<string, string | number | null>) => {
    const next = new URLSearchParams(sp);
    Object.entries({ page: 1, ...patch }).forEach(([k, v]) => {
      if (v === null || (typeof v === "string" && v === "")) next.delete(k);
      else next.set(k, String(v));
    });
    setSp(next);
  };

  useEffect(() => {
    const ctrl = new AbortController();
    const qs = new URLSearchParams({
      side,
      period,
      adjusted: String(adjusted),
      page: String(page),
      page_size: String(pageSize),
    });
    if (sector) qs.set("sector", sector);

    setLoading(true);
    fetch(`/api/market/movers/tracked/list/?${qs}`, { signal: ctrl.signal })
      .then((r) => r.json() as Promise<ListResponse>)
      .then((d) => {
        setData(d);
        setLoading(false);
      })
      .catch((e) => {
        if (e.name !== "AbortError") setLoading(false);
      });
    return () => ctrl.abort();
  }, [side, period, sector, adjusted, page, pageSize]);

  const pages = Math.max(1, Math.ceil(data.total / pageSize));

  return (
    <div className="movers-page">
      <span className={`chip ${up ? "chip--up" : "chip--down"}`}>
        Tracked Top {up ? "Gainers" : "Losers"}
      </span>

      <div className="filters">
        <label>
          Sector
          <select value={sector} onChange={(e) => set({ sector: e.target.value })}>
            <option value="">All Sectors</option>
            {data.sectors.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>

        <label>
          Adjusted Price
          <select
            value={adjusted ? "true" : "false"}
            onChange={(e) => set({ adjusted: e.target.value })}
          >
            <option value="true">Yes</option>
            <option value="false">No</option>
          </select>
        </label>

        <label>
          Items Per Page
          <select value={pageSize} onChange={(e) => set({ page_size: Number(e.target.value) })}>
            {PAGE_SIZES.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>

        <button type="button" onClick={() => setSp({ side })}>
          Reset
        </button>
      </div>

      <div className="tabs" role="tablist">
        {TABS.map(([label, key]) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={period === key}
            className={period === key ? "active" : ""}
            onClick={() => set({ period: key })}
          >
            {label}
          </button>
        ))}
      </div>

      <table className={loading ? "is-loading" : ""}>
        <thead>
          <tr>
            <th>SYMBOL</th>
            <th>LTP</th>
            <th>CH</th>
            <th>CH %</th>
            <th>SECTOR</th>
            <th>LAST UPDATED DATE</th>
          </tr>
        </thead>
        <tbody>
          {data.rows.map((r) => (
            <tr key={r.symbol}>
              <td>
                <Logo url={r.logo_url} symbol={r.symbol} />
                <b>{r.symbol}</b>
                <div className="sub">{r.name}</div>
              </td>
              <td>{fmt(r.close)}</td>
              <td className={up ? "pos" : "neg"}>
                {up ? "+" : ""}
                {fmt(r.change)}
              </td>
              <td>
                <span
                  className={`pill ${up ? "pill--up" : "pill--down"}`}
                  title={r.adjusted ? "Based on exchange-adjusted previous close" : undefined}
                >
                  {up ? "↑" : "↓"} {fmt(r.change_pct)}%{r.adjusted ? " *" : ""}
                </span>
              </td>
              <td>{r.sector}</td>
              <td>{fmtTime(r.last_updated)}</td>
            </tr>
          ))}
          {!loading && data.rows.length === 0 && (
            <tr>
              <td colSpan={6}>{data.reason ?? "No data"}</td>
            </tr>
          )}
        </tbody>
      </table>

      <footer className="pager">
        <button type="button" disabled={page <= 1} onClick={() => set({ page: page - 1 })}>
          Prev
        </button>
        <span>
          Page {page} / {pages} · {data.total} companies
        </span>
        <button type="button" disabled={page >= pages} onClick={() => set({ page: page + 1 })}>
          Next
        </button>
      </footer>
    </div>
  );
}