
import { apiClient } from './client';
import type { User } from '../types';

export interface LoginResponse {
  access: string;
  refresh: string;
  user: User;
}

export interface RegisterPayload {
  username: string;
  email: string;
  password: string;
  password_confirm: string;
  first_name: string;
  last_name: string;
  role?: 'viewer' | 'analyst' | 'admin';
}

export interface PermissionsResponse {
  permissions: string[];
  role: string;
  effective_role: string;
}

export const authApi = {
  login: (
    username: string,
    password: string
  ) =>
    apiClient
      .post<LoginResponse>(
        '/users/login/',
        {
          username,
          password,
        }
      )
      .then((response) => response.data),

  register: (
    payload: RegisterPayload
  ) =>
    apiClient
      .post(
        '/users/register/',
        payload
      )
      .then((response) => response.data),

  me: () =>
    apiClient
      .get<User>('/users/me/')
      .then((response) => response.data),

  permissions: () =>
    apiClient
      .get<PermissionsResponse>(
        '/users/me/permissions/'
      )
      .then((response) => response.data),

  refresh: (
    refresh: string
  ) =>
    apiClient
      .post(
        '/users/token/refresh/',
        {
          refresh,
        }
      )
      .then((response) => response.data),
};

