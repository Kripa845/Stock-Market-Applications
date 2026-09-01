import apiClient from "./client";
import type { DailyPrice, FloorsheetQueryParams, FloorsheetTransaction, PaginatedResponse } from "../types";

// GET /api/market-data/
// The current backend view (CompanyPriceList) returns ALL DailyPrice rows
// for every active company in one flat, unpaginated array -- it does not
// yet accept a ?company_id= or ?range= query param, even though that's
// what the spec's /api/companies/:id/prices?range=30d implies.
// We fetch the full set once and filter/slice client-side so the app
// works today; see README for the small backend change that would let
// this filter server-side instead.
export async function listAllDailyPrices(): Promise<DailyPrice[]> {
  const { data } = await apiClient.get<DailyPrice[]>("/market-data/");
  return data;
}

export interface PriceRangeOptions {
  rangeDays?: number | null;
}

export async function listPricesForCompany(
  companyId: number | string,
  { rangeDays }: PriceRangeOptions = {}
): Promise<DailyPrice[]> {
  const all = await listAllDailyPrices();
  let rows = all.filter((row) => String(row.company) === String(companyId));
  rows = rows.slice().sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
  if (rangeDays) {
    rows = rows.slice(-rangeDays);
  }
  return rows;
}

// GET /api/market-data/floorsheet/?company=&date=&buyer_broker=&seller_broker=&search=&ordering=
// This endpoint IS paginated (DRF PageNumberPagination, page_size=20):
// { count, next, previous, results: [...] }
export async function listFloorsheet(
  params: FloorsheetQueryParams = {}
): Promise<PaginatedResponse<FloorsheetTransaction>> {
  const { data } = await apiClient.get<PaginatedResponse<FloorsheetTransaction>>(
    "/market-data/floorsheet/",
    { params }
  );
  return data;
}
