import apiClient from "./client";
import type { Company } from "../types";

// GET /api/companies/  -> list of active companies
// NOTE: this requires the one-line backend fix described in the README
// (Backend/apps/companies/urls.py currently double-prefixes this route).
export async function listCompanies(): Promise<Company[]> {
  const { data } = await apiClient.get<Company[]>("/companies/");
  return data;
}

// GET /api/companies/:id/
export async function getCompany(id: number | string): Promise<Company> {
  const { data } = await apiClient.get<Company>(`/companies/${id}/`);
  return data;
}
