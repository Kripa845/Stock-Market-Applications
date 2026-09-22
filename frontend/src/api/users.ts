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


/*
 * =========================================================
 * USER API
 * =========================================================
 */

export const usersApi = {
  /*
   * Get all users
   */
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


  /*
   * Create user
   */
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


  /*
   * Update user
   */
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


  /*
   * Delete user
   */
  remove: async (
    id: number
  ) => {
    await apiClient.delete(
      `/users/admin/users/${id}/`
    );
  },
};


/*
 * =========================================================
 * COMPANY ACCESS TYPES
 * =========================================================
 */

export interface UserCompanyAccess {
  company_id: number;
  company_symbol: string;
  company_name: string;
  status: number;
}

export interface UserCompanyAccessResponse {
  company_access: UserCompanyAccess[];
}


/*
 * =========================================================
 * GET USER COMPANY ACCESS
 * =========================================================
 *
 * GET:
 * /users/admin/users/<userId>/company-access/
 *
 * Returns all companies available for the user and
 * their current access status.
 */

export async function getUserCompanyAccess(
  userId: number
): Promise<UserCompanyAccessResponse> {
  const response =
    await apiClient.get<UserCompanyAccessResponse>(
      `/users/admin/users/${userId}/company-access/`
    );

  return response.data;
}


/*
 * =========================================================
 * SAVE USER COMPANY ACCESS
 * =========================================================
 *
 * POST:
 * /users/admin/users/<userId>/company-access/
 *
 * Example request:
 *
 * {
 *   company_access: [
 *     {
 *       company_id: 1,
 *       status: 1
 *     },
 *     {
 *       company_id: 2,
 *       status: 0
 *     }
 *   ]
 * }
 */

export async function saveUserCompanyAccess(
  userId: number,
  companyAccess: {
    company_id: number;
    status: number;
  }[]
): Promise<UserCompanyAccessResponse> {
  const response =
    await apiClient.post<UserCompanyAccessResponse>(
      `/users/admin/users/${userId}/company-access/`,
      {
        company_access: companyAccess,
      }
    );

  return response.data;
}