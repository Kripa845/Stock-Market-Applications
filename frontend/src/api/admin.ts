
import { apiClient } from "./client";

import type {
  AdminDashboard,
} from "../types";

import type {
  AdminUser,
  UserPayload,
} from "./users";


export const adminApi = {
  getDashboard: () =>
    apiClient
      .get<AdminDashboard>(
        "/dashboard/admin/"
      )
      .then(
        (response) =>
          response.data
      ),

  getUsers: () =>
    apiClient
      .get<AdminUser[]>(
        "/users/admin/users/"
      )
      .then(
        (response) =>
          response.data
      ),

  createUser: (
    payload: UserPayload
  ) =>
    apiClient
      .post<AdminUser>(
        "/users/admin/users/",
        {
          ...payload,
          password_confirm:
            payload.password,
        }
      )
      .then(
        (response) =>
          response.data
      ),

  updateUser: (
    id: number,
    payload: Partial<UserPayload>
  ) =>
    apiClient
      .patch<AdminUser>(
        `/users/admin/users/${id}/`,
        payload
      )
      .then(
        (response) =>
          response.data
      ),

  deleteUser: (
    id: number
  ) =>
    apiClient
      .delete(
        `/users/admin/users/${id}/`
      )
      .then(
        (response) =>
          response.data
      ),
};

