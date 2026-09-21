import axios from 'axios';
import type { AxiosError, InternalAxiosRequestConfig } from 'axios';

const BASE_URL =
  import.meta.env.VITE_API_BASE_URL ??
  import.meta.env.VITE_API_URL ??
  'http://127.0.0.1:8000/api';

export const apiClient = axios.create({
  baseURL: BASE_URL,
  headers: { 'Content-Type': 'application/json' },
});

const AUTH_PATHS = ['/users/login/', '/users/token/refresh/', '/users/register/'];
const isAuthPath = (url?: string) => !!url && AUTH_PATHS.some((p) => url.includes(p));

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

let refreshPromise: Promise<string> | null = null;

function refreshAccessToken(): Promise<string> {
  if (!refreshPromise) {
    const refresh = localStorage.getItem('refresh_token');
    if (!refresh) return Promise.reject(new Error('No refresh token'));
    refreshPromise = axios
      .post(`${BASE_URL}/users/token/refresh/`, { refresh })
      .then((res) => {
        localStorage.setItem('access_token', res.data.access);
        // ROTATE_REFRESH_TOKENS + BLACKLIST_AFTER_ROTATION: the old refresh token is now dead.
        if (res.data.refresh) localStorage.setItem('refresh_token', res.data.refresh);
        return res.data.access as string;
      })
      .finally(() => { refreshPromise = null; });
  }
  return refreshPromise;
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined;
    const status = error.response?.status;

    if (status === 401 && original && !original._retry && !isAuthPath(original.url)) {
      original._retry = true;
      try {
        const token = await refreshAccessToken();
        original.headers.Authorization = `Bearer ${token}`;
        return apiClient(original);
      } catch {
        localStorage.clear();
        window.location.href = '/login';
        return Promise.reject(error);
      }
    }

    if (status === 403 && !isAuthPath(original?.url)) {
      window.dispatchEvent(new CustomEvent('auth:forbidden')); // AuthContext re-fetches permissions
    }
    return Promise.reject(error);
  },
);

export default apiClient;