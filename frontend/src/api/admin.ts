
import { apiClient } from './client';
import type {
  User,
  AdminDashboard,
} from '../types';

export const adminApi = {
  getDashboard: () =>
    apiClient
      .get<AdminDashboard>(
        '/dashboard/admin/'
      )
      .then((response) => response.data),

  getUsers: () =>
    apiClient
      .get<User[]>('/admin/users/')
      .then((response) => response.data),

  createUser: (payload: {
    username: string;
    email: string;
    password: string;
    password_confirm: string;
    first_name: string;
    last_name: string;
    role: 'admin' | 'analyst' | 'viewer';
  }) =>
    apiClient
      .post('/admin/users/', payload)
      .then((response) => response.data),

  updateUser: (
    id: number,
    payload: Partial<User> & {
      password?: string;
    }
  ) =>
    apiClient
      .patch(`/admin/users/${id}/`, payload)
      .then((response) => response.data),

  deleteUser: (id: number) =>
    apiClient
      .delete(`/admin/users/${id}/`)
      .then((response) => response.data),
};

