import apiClient from "./client";
import type { BehaviorSummaryData, NewsPriceCorrelation } from "../types";

// --- Not yet implemented on the backend -------------------------------
// apps/analysis/urls.py is currently an empty urlpatterns list, even
// though the DailyAnalysis model (vwap, pressure, volume_anomaly,
// news_count) already exists. Written against the spec's documented
// shape so it "lights up" once the routes are added.
// ------------------------------------------------------------------------

// GET /api/companies/:id/behaviorsummary
export async function getBehaviorSummary(companyId: number | string): Promise<BehaviorSummaryData> {
  const { data } = await apiClient.get<BehaviorSummaryData>(`/companies/${companyId}/behaviorsummary`);
  return data;
}

// GET /api/companies/:id/news-pricecorrelation
export async function getNewsPriceCorrelation(companyId: number | string): Promise<NewsPriceCorrelation> {
  const { data } = await apiClient.get<NewsPriceCorrelation>(
    `/companies/${companyId}/news-pricecorrelation`
  );
  return data;
}
