import { apiClient } from './client';
import type { CategorizationCorrection, NewsArticle, NewsStats, PaginatedResponse } from '../types';

export interface NewsQueryParams {
  page?: number;
  company_id?: number;
  search?: string;
  sentiment?: string;
  source?: string;
  needs_review?: boolean | string;
  confidence_min?: number;
  confidence_max?: number;
}

export const newsApi = {
  getNews: (params?: NewsQueryParams) =>
    apiClient
      .get<PaginatedResponse<NewsArticle>>('/news/', { params })
      .then((response) => response.data),

  getNewsById: (id: number) =>
    apiClient
      .get<NewsArticle>(`/news/${id}/`)
      .then((response) => response.data),

  getStats: () =>
    apiClient
      .get<NewsStats>('/news/stats/')
      .then((response) => response.data),

  getCorrections: (params?: { article_id?: number; company_id?: number }) =>
    apiClient
      .get<PaginatedResponse<CategorizationCorrection>>('/news/corrections/', { params })
      .then((response) => response.data),

  recategorize: (
    id: number,
    data: {
      company_id: number;
      action: 'add' | 'remove' | 'update';
      confidence?: number;
      reason: string;
    }
  ) =>
    apiClient
      .post<{ message: string; correction: CategorizationCorrection; article: NewsArticle }>(
        `/news/${id}/recategorize/`,
        data
      )
      .then((response) => response.data),

  triggerCategorize: (id: number) =>
    apiClient
      .post<{ message: string; task_id: string; article_id: number }>(
        `/news/${id}/trigger-categorize/`
      )
      .then((response) => response.data),
};