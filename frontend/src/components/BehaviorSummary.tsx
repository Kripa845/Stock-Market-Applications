import { useEffect, useState } from "react";
import { getBehaviorSummary } from "../api/analysis";
import { isNotImplemented } from "../api/client";
import type { BehaviorSummaryData, Pressure } from "../types";

interface BehaviorSummaryProps {
  companyId: number | string;
}

interface BehaviorState {
  loading: boolean;
  notImplemented: boolean;
  error: unknown;
  data: BehaviorSummaryData | null;
}

const PRESSURE_LABEL: Record<Pressure, string> = {
  buying: "Buying pressure",
  selling: "Selling pressure",
  neutral: "Neutral",
};

export default function BehaviorSummary({ companyId }: BehaviorSummaryProps) {
  const [state, setState] = useState<BehaviorState>({
    loading: true,
    notImplemented: false,
    error: null,
    data: null,
  });

  useEffect(() => {
    let cancelled = false;
    setState({ loading: true, notImplemented: false, error: null, data: null });

    getBehaviorSummary(companyId)
      .then((data) => {
        if (!cancelled) setState({ loading: false, notImplemented: false, error: null, data });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        if (isNotImplemented(err)) {
          setState({ loading: false, notImplemented: true, error: null, data: null });
        } else {
          setState({ loading: false, notImplemented: false, error: err, data: null });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [companyId]);

  if (state.loading) return <div className="empty-state small">Loading behavior analysis…</div>;

  if (state.notImplemented) {
    return (
      <div className="empty-state small">
        The behavior-analysis API (<code>GET /api/companies/:id/behaviorsummary</code>) isn't
        wired up on the backend in this snapshot — the <code>DailyAnalysis</code> model already
        exists, so this panel just needs the view + URL added.
      </div>
    );
  }

  if (state.error) return <div className="empty-state small error">Couldn't load analysis right now.</div>;

  const d = state.data;
  if (!d) return null;

  return (
    <div className="stat-grid">
      <div className="stat-card">
        <div className="stat-label">VWAP vs Close</div>
        <div className="stat-value">
          {d.vwap ?? "—"} <span className="stat-sub">/ {d.close_price ?? "—"}</span>
        </div>
      </div>
      <div className="stat-card">
        <div className="stat-label">Pressure</div>
        <div className={`stat-value pressure-${d.pressure}`}>{PRESSURE_LABEL[d.pressure] || d.pressure}</div>
      </div>
      <div className="stat-card">
        <div className="stat-label">Volume anomaly</div>
        <div className="stat-value">{d.volume_anomaly ? "Flagged" : "Normal"}</div>
      </div>
      <div className="stat-card">
        <div className="stat-label">News count (day)</div>
        <div className="stat-value">{d.news_count ?? 0}</div>
      </div>
    </div>
  );
}
