
import axios from 'axios';

const BASE_URL =
  import.meta.env.VITE_API_BASE_URL ??
  import.meta.env.VITE_API_URL ??
  'http://127.0.0.1:8000/api';

export const apiClient = axios.create({
  baseURL: BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Attach JWT access token
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');

  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }

  return config;
});

// Automatically refresh expired access token
apiClient.interceptors.response.use(
  (response) => response,

  async (error) => {
    const originalRequest = error.config;

    if (
      error.response?.status === 401 &&
      !originalRequest?._retry
    ) {
      originalRequest._retry = true;

      const refreshToken =
        localStorage.getItem('refresh_token');

      if (!refreshToken) {
        localStorage.clear();
        window.location.href = '/login';
        return Promise.reject(error);
      }

      try {
        const response = await axios.post(
          `${BASE_URL}/users/token/refresh/`,
          {
            refresh: refreshToken,
          }
        );

        const newAccessToken = response.data.access;

        localStorage.setItem(
          'access_token',
          newAccessToken
        );

        originalRequest.headers.Authorization =
          `Bearer ${newAccessToken}`;

        return apiClient(originalRequest);
      } catch {
        localStorage.clear();
        window.location.href = '/login';
      }
    }

    return Promise.reject(error);
  }
);

export default apiClient;

