import { apiClient } from "./client";

export type BuiltInRole =
  | "admin"
  | "analyst"
  | "viewer";

export interface PermissionDefinition {
  key: string;
  name: string;
}

export interface PermissionGroup {
  key: string;
  name: string;
  permissions: PermissionDefinition[];
}

export interface PermissionDefinitionsResponse {
  groups: PermissionGroup[];
}

export interface RolePermissionEntry {
  key: string;
  name: string;
}

export interface EditableRole {
  key: string;
  name: string;
  description: string;
  permissions: string[];
  editable: boolean;
}

export interface CustomRoleSummary {
  id: number;
  key: string;
  name: string;
  description: string;
  permissions: string[];
  editable: boolean;
  is_active: boolean;
  user_count: number;
}

export interface RolesResponse {
  roles: EditableRole[];
  custom_roles: CustomRoleSummary[];
}

export interface CustomRole {
  id: number;
  name: string;
  description: string;
  permissions: string[];
  is_active: boolean;
  user_count: number;
  created_at: string;
  updated_at: string;
}

export interface CreateRolePayload {
  name: string;
  description?: string;
  permissions: string[];
}

export const rolesApi = {
  getPermissionDefinitions: async () => {
    const response =
      await apiClient.get<PermissionDefinitionsResponse>(
        "/users/admin/role-permissions/"
      );

    return response.data;
  },

  getRoles: async () => {
    const response =
      await apiClient.get<RolesResponse>(
        "/users/admin/roles/"
      );

    return response.data;
  },

  getBuiltInRole: async (
    roleKey: "analyst" | "viewer"
  ) => {
    const response =
      await apiClient.get<EditableRole>(
        `/users/admin/roles/${roleKey}/`
      );

    return response.data;
  },

  updateBuiltInRole: async (
    roleKey: "analyst" | "viewer",
    permissions: string[]
  ) => {
    const response =
      await apiClient.patch<EditableRole>(
        `/users/admin/roles/${roleKey}/`,
        {
          permissions,
        }
      );

    return response.data;
  },

  listCustomRoles: async () => {
    const response =
      await apiClient.get<{
        roles: CustomRole[];
      }>("/users/admin/custom-roles/");

    return response.data.roles;
  },

  getCustomRole: async (id: number) => {
    const response =
      await apiClient.get<CustomRole>(
        `/users/admin/custom-roles/${id}/`
      );

    return response.data;
  },

  createCustomRole: async (
    payload: CreateRolePayload
  ) => {
    const response =
      await apiClient.post<CustomRole>(
        "/users/admin/custom-roles/",
        payload
      );

    return response.data;
  },

  updateCustomRole: async (
    id: number,
    payload: Partial<CreateRolePayload> & {
      is_active?: boolean;
    }
  ) => {
    const response =
      await apiClient.patch<CustomRole>(
        `/users/admin/custom-roles/${id}/`,
        payload
      );

    return response.data;
  },

  deleteCustomRole: async (id: number) => {
    await apiClient.delete(
      `/users/admin/custom-roles/${id}/`
    );
  },
};