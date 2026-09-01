import axios, { AxiosError, type InternalAxiosRequestConfig } from "axios";
import type { TokenPair } from "../types";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

const ACCESS_KEY = "nepse_access_token";
const REFRESH_KEY = "nepse_refresh_token";

export const tokenStore = {
  getAccess: (): string | null => localStorage.getItem(ACCESS_KEY),
  getRefresh: (): string | null => localStorage.getItem(REFRESH_KEY),
  setTokens: ({ access, refresh }: Partial<TokenPair>): void => {
    if (access) localStorage.setItem(ACCESS_KEY, access);
    if (refresh) localStorage.setItem(REFRESH_KEY, refresh);
  },
  clear: (): void => {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
  },
};

export const apiClient = axios.create({
  baseURL: BASE_URL,
});

// Attach access token to every request
apiClient.interceptors.request.use((config) => {
  const token = tokenStore.getAccess();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Retry flag lives on the config object we pass back through axios.
interface RetryableRequestConfig extends InternalAxiosRequestConfig {
  _retry?: boolean;
}

// Handle expired access tokens: try one silent refresh, then retry.
let refreshInFlight: Promise<{ data: { access: string } }> | null = null;

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as RetryableRequestConfig | undefined;
    const status = error.response ? error.response.status : null;

    const isAuthRoute =
      originalRequest?.url?.includes("/users/login") ||
      originalRequest?.url?.includes("/users/token/refresh") ||
      originalRequest?.url?.includes("/users/register");

    if (status === 401 && originalRequest && !originalRequest._retry && !isAuthRoute) {
      originalRequest._retry = true;
      const refresh = tokenStore.getRefresh();

      if (!refresh) {
        tokenStore.clear();
        return Promise.reject(error);
      }

      try {
        if (!refreshInFlight) {
          refreshInFlight = axios
            .post<{ access: string }>(`${BASE_URL}/users/token/refresh/`, { refresh })
            .finally(() => {
              refreshInFlight = null;
            });
        }
        const { data } = await refreshInFlight;
        tokenStore.setTokens({ access: data.access });
        originalRequest.headers.Authorization = `Bearer ${data.access}`;
        return apiClient(originalRequest);
      } catch (refreshError) {
        tokenStore.clear();
        window.location.href = "/login";
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

// Helper: true when the failure looks like "this backend route doesn't
// exist yet" (404/501) rather than a real error — several endpoints in
// the spec (news, analysis, admin crawl-runs) aren't wired up on the
// backend yet. Pages use this to show a graceful "coming soon" state
// instead of an error banner.
export function isNotImplemented(error: unknown): boolean {
  if (!axios.isAxiosError(error)) return false;
  const status = error.response?.status;
  return status === 404 || status === 501;
}

export default apiClient;
