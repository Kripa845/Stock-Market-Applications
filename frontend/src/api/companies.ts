import { apiClient } from "./client";
import type { Company } from "../types/company";

export interface CompanyQuery {
  page?: number;
  search?: string;
  sector?: string;
  status?: "active" | "inactive";
  tracking?: "tracked" | "not_tracked";
  tracked_only?: boolean;
}

export interface PaginatedCompanies {
  count: number;
  next: string | null;
  previous: string | null;
  results: Company[];
}

export async function getCompanies(
  params: CompanyQuery
) {
  const response =
    await apiClient.get<PaginatedCompanies>(
      "/companies/",
      { params }
    );

  return response.data;
}

export async function getCompany(
  id: number
) {
  const response =
    await apiClient.get<Company>(
      `/companies/${id}/`
    );

  return response.data;
}

export async function updateCompany(
  id: number,
  data: Partial<Company>
) {
  const response =
    await apiClient.patch(
      `/companies/${id}/`,
      data
    );

  return response.data;
}

export async function deleteCompany(
  id: number
) {
  await apiClient.delete(
    `/companies/${id}/`
  );
}

export async function setCompanyTracking(
  id: number,
  isTracked: boolean
) {
  const response =
    await apiClient.post(
      `/companies/${id}/toggle-track/`,
      {
        is_tracked: isTracked,
      }
    );

  return response.data;
}

export async function getCompanySectors() {
  const response =
    await apiClient.get<string[]>(
      "/companies/sectors/"
    );

  return response.data;
}