
import { apiClient } from './client';

export const tradingApi = {
  getDailyAnalysis: (companyId?: number) =>
    apiClient
      .get('/analysis/daily/', {
        params: companyId
          ? { company_id: companyId }
          : undefined,
      })
      .then((response) => response.data),

  getCrossCompanyAnalysis: () =>
    apiClient
      .get('/analysis/cross-company/')
      .then((response) => response.data),

  getDashboardSummary: () =>
    apiClient
      .get('/analysis/dashboard-summary/')
      .then((response) => response.data),

  getBehaviorSummary: (companyId: number) =>
    apiClient
      .get(
        `/companies/${companyId}/behavior-summary/`
      )
      .then((response) => response.data),

  getNewsPriceCorrelation: (companyId: number) =>
    apiClient
      .get(
        `/companies/${companyId}/news-price-correlation/`
      )
      .then((response) => response.data),
};

