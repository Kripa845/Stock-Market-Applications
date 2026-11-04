
import apiClient from "../api/client";

export interface StockPerformance {
  status: string;
  company_id: number;
  symbol: string;
  name: string;

  change_1w: number | null;
  change_1m: number | null;
  change_3m: number | null;
  change_6m: number | null;
  change_ytd: number | null;
  change_1y: number | null;

  high_3m: number | null;
  low_3m: number | null;
  high_52w: number | null;
  low_52w: number | null;

  distance_from_52w_high: number | null;
  distance_from_52w_low: number | null;

  average_close_180: number | null;
  average_close_350: number | null;

  average_volume_1w: number | null;
  average_volume_1m: number | null;
  average_volume_6m: number | null;
  average_volume_12m: number | null;

  volatility_1m: number | null;

  beta: {
    beta: number | null;
    observations: number;
    status: string;
  } | null;
}

export const getStockPerformance = async (
  companyId: number
): Promise<StockPerformance> => {
  const response = await apiClient.get<StockPerformance>(
    `/companies/${companyId}/performance/`
  );

  return response.data;
};
