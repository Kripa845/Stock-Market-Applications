import { apiClient } from "./client";

export type BuiltInRole =
  | "admin"
  | "analyst"
  | "viewer";

export interface AdminUser {
  id: number;
  username: string;
  email: string;

  first_name: string;
  last_name: string;

  role: BuiltInRole;

  custom_role_id?: number | null;
  custom_role_name?: string | null;
  effective_role?: string;

  is_active: boolean;

  date_joined?: string;
  last_login?: string | null;
}

export interface UserPayload {
  username: string;
  email: string;

  first_name?: string;
  last_name?: string;

  password?: string;

  role?: BuiltInRole;

  custom_role_id?: number | null;

  is_active?: boolean;
}

interface PaginatedResponse<T> {
  count: number;
  results: T[];
}

const unwrap = <T>(
  data: T[] | PaginatedResponse<T>
): T[] => {
  return Array.isArray(data)
    ? data
    : data.results;
};

export const usersApi = {
  list: async () => {
    const response =
      await apiClient.get<
        AdminUser[] |
        PaginatedResponse<AdminUser>
      >(
        "/users/admin/users/"
      );

    return unwrap(response.data);
  },

  create: async (
    payload: UserPayload
  ) => {
    const response =
      await apiClient.post<AdminUser>(
        "/users/admin/users/",
        {
          ...payload,
          password_confirm:
            payload.password,
        }
      );

    return response.data;
  },

  update: async (
    id: number,
    payload: Partial<UserPayload>
  ) => {
    const response =
      await apiClient.patch<AdminUser>(
        `/users/admin/users/${id}/`,
        payload
      );

    return response.data;
  },

  delete: async (id: number) => {
    await apiClient.delete(
      `/users/admin/users/${id}/`
    );
  },
};