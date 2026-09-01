import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { getCompany } from "../api/companies";
import { listPricesForCompany, listFloorsheet } from "../api/marketData";
import PriceChart from "../components/PriceChart";
import FloorsheetTable from "../components/FloorsheetTable";
import NewsFeed from "../components/NewsFeed";
import BehaviorSummary from "../components/BehaviorSummary";
import type { Company, DailyPrice, FloorsheetTransaction } from "../types";

interface RangeOption {
  label: string;
  days: number | null;
}

const RANGE_OPTIONS: RangeOption[] = [
  { label: "7D", days: 7 },
  { label: "30D", days: 30 },
  { label: "All", days: null },
];

interface FloorsheetState {
  rows: FloorsheetTransaction[];
  loading: boolean;
}

export default function CompanyDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [company, setCompany] = useState<Company | null>(null);
  const [prices, setPrices] = useState<DailyPrice[]>([]);
  const [rangeDays, setRangeDays] = useState<number | null>(30);
  const [floorsheet, setFloorsheet] = useState<FloorsheetState>({ rows: [], loading: true });
  const [floorsheetDate, setFloorsheetDate] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    setLoading(true);
    setError(null);

    Promise.all([getCompany(id), listPricesForCompany(id, { rangeDays })])
      .then(([companyData, priceData]) => {
        if (cancelled) return;
        setCompany(companyData);
        setPrices(priceData);
      })
      .catch((err: unknown) => !cancelled && setError(err))
      .finally(() => !cancelled && setLoading(false));

    return () => {
      cancelled = true;
    };
  }, [id, rangeDays]);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    setFloorsheet((s) => ({ ...s, loading: true }));

    const params: Record<string, string> = { company: id, ordering: "-date" };
    if (floorsheetDate) params.date = floorsheetDate;

    listFloorsheet(params)
      .then((data) => {
        if (cancelled) return;
        setFloorsheet({ rows: data.results, loading: false });
      })
      .catch(() => !cancelled && setFloorsheet({ rows: [], loading: false }));

    return () => {
      cancelled = true;
    };
  }, [id, floorsheetDate]);

  if (loading) return <div className="page-loading">Loading company…</div>;

  if (error || !company || !id) {
    return (
      <div className="empty-state error">
        Couldn't load this company. <Link to="/">Back to dashboard</Link>
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>
            {company.symbol} <span className="page-subtitle">{company.name}</span>
          </h1>
          <p className="page-subtitle">{company.sector}</p>
        </div>
        <Link to="/" className="btn btn-ghost">
          ← Back
        </Link>
      </div>

      <section className="card">
        <div className="card-header">
          <h2>Price & volume</h2>
          <div className="range-toggle">
            {RANGE_OPTIONS.map((opt) => (
              <button
                key={opt.label}
                className={`btn btn-xs ${rangeDays === opt.days ? "btn-primary" : "btn-ghost"}`}
                onClick={() => setRangeDays(opt.days)}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
        <PriceChart prices={prices} />
      </section>

      <section className="card">
        <div className="card-header">
          <h2>Behavior analysis</h2>
        </div>
        <BehaviorSummary companyId={id} />
      </section>

      <div className="two-col">
        <section className="card">
          <div className="card-header">
            <h2>Categorized news</h2>
          </div>
          <NewsFeed companyId={id} />
        </section>

        <section className="card">
          <div className="card-header">
            <h2>Floorsheet</h2>
            <input type="date" value={floorsheetDate} onChange={(e) => setFloorsheetDate(e.target.value)} />
          </div>
          <FloorsheetTable rows={floorsheet.rows} loading={floorsheet.loading} />
        </section>
      </div>
    </div>
  );
}
