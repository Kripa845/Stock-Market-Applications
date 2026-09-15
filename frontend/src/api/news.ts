import { apiClient } from './client';
import type { NewsArticle, PaginatedResponse } from '../types';

export const newsApi = {
  getNews: (params?: { page?: number; company_id?: number; search?: string; sentiment?: string; source?: string }) =>
    apiClient
      .get<PaginatedResponse<NewsArticle>>('/news/', { params })
      .then((response) => response.data),

  getNewsById: (id: number) =>
    apiClient
      .get<NewsArticle>(`/news/${id}/`)
      .then((response) => response.data),

  recategorize: (id: number, data: {
    company_id: number;
    action: 'add' | 'remove' | 'update';
    confidence?: number;
    reason: string;
  }) =>
    apiClient
      .post(`/news/${id}/recategorize/`, data)
      .then((response) => response.data),
};