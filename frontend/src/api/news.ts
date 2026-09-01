import apiClient from "./client";
import type { NewsArticle, PaginatedResponse, RecategorizePayload } from "../types";

// --- Not yet implemented on the backend -------------------------------
// apps/news/urls.py currently exports an empty urlpatterns list, even
// though the RawArticle / NewsArticle / ArticleCompanyTag /
// CategorizationCorrection models and the categorizer services already
// exist. These calls are written against the spec's documented shape
// (Section 7 of the assignment) so the frontend needs zero changes once
// the routes are added -- callers should catch the resulting 404 via
// isNotImplemented() and show an empty/coming-soon state.
// ------------------------------------------------------------------------

export interface NewsQueryParams {
  [key: string]: string | number | undefined;
}

// GET /api/news/?company_id=
export async function listNewsForCompany(
  companyId: number | string,
  params: NewsQueryParams = {}
): Promise<NewsArticle[] | PaginatedResponse<NewsArticle>> {
  const { data } = await apiClient.get<NewsArticle[] | PaginatedResponse<NewsArticle>>("/news/", {
    params: { company_id: companyId, ...params },
  });
  return data;
}

// POST /api/news/:id/recategorize
// Analyst/Admin correction of a mis-tagged article.
export async function recategorizeArticle(
  articleId: number | string,
  payload: RecategorizePayload
): Promise<unknown> {
  const { data } = await apiClient.post(`/news/${articleId}/recategorize/`, payload);
  return data;
}
