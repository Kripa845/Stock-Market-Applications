import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

export type Side = "gainer" | "loser";
type Num = number | string; // DRF may serialize Decimals as strings

export interface MoverRow {
  symbol: string;
  name: string;
  logo_url: string | null;
  close: Num;
  change: Num;
  change_pct: Num;
  sector?: string;
  adjusted?: boolean;
  volume?: number | null;
  turnover?: Num | null;
  last_updated?: string | null;
}

interface CardsResponse {
  as_of: string | null;
  reason?: string | null;
  gainers: MoverRow[];
  losers: MoverRow[];
}

export const fmt = (n: Num | null | undefined, maxDecimals = 2): string =>
  n === null || n === undefined || n === ""
    ? "—"
    : Number(n).toLocaleString("en-IN", {
        minimumFractionDigits: 0,
        maximumFractionDigits: maxDecimals,
      });

export function Logo({ url, symbol }: { url: string | null; symbol: string }) {
  return url ? (
    <img src={url} alt={symbol} className="mover-logo" loading="lazy" />
  ) : (
    <span className="mover-logo mover-logo--fallback">{symbol[0]}</span>
  );
}

interface CardProps {
  title: string;
  side: Side;
  rows: MoverRow[];
  emptyText: string;
}

function MoverCard({ title, side, rows, emptyText }: CardProps) {
  const up = side === "gainer";
  return (
    <section className="mover-card">
      <header>
        <span className={`chip ${up ? "chip--up" : "chip--down"}`}>{title}</span>
        <Link
          to={`/movers/tracked?side=${side}`}
          className="arrow-btn"
          aria-label={`View all ${title}`}
        >
          ›
        </Link>
      </header>

      <table>
        <thead>
          <tr>
            <th>SYMBOL</th>
            <th>CH</th>
            <th>CH %</th>
            <th>LTP</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.symbol}>
              <td>
                <Logo url={r.logo_url} symbol={r.symbol} />{" "}
                <Link to={`/company/${r.symbol}`}>{r.symbol}</Link>
              </td>
              <td className={up ? "pos" : "neg"}>
                {up ? "+" : ""}
                {fmt(r.change)}
              </td>
              <td>
                <span className={`pill ${up ? "pill--up" : "pill--down"}`}>
                  {up ? "↑" : "↓"} {fmt(r.change_pct)}%
                </span>
              </td>
              <td>{fmt(r.close)}</td>
            </tr>
          ))}
          {rows.length === 0 && (
            <tr>
              <td colSpan={4}>{emptyText}</td>
            </tr>
          )}
        </tbody>
      </table>
    </section>
  );
}

export default function TrackedMoverCards() {
  const [data, setData] = useState<CardsResponse | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    const ctrl = new AbortController();
    fetch("/api/market/movers/tracked/?period=1D&limit=5", { signal: ctrl.signal })
      .then((r) => {
        if (!r.ok) throw new Error(String(r.status));
        return r.json() as Promise<CardsResponse>;
      })
      .then(setData)
      .catch((e) => {
        if (e.name !== "AbortError") setError(true);
      });
    return () => ctrl.abort();
  }, []);

  if (error) return <p className="mover-error">Could not load movers.</p>;
  if (!data) return null;

  const empty = data.reason ?? "No data";
  return (
    <>
      <MoverCard title="Tracked Top Gainers" side="gainer" rows={data.gainers} emptyText={empty} />
      <MoverCard title="Tracked Top Losers" side="loser" rows={data.losers} emptyText={empty} />
    </>
  );
}