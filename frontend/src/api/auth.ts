import apiClient, { tokenStore } from "./client";
import type { LoginPayload, RegisterPayload, TokenPair, User } from "../types";

interface RegisterResponse {
  message: string;
  user: User;
}

// POST /api/users/register/
export async function register(payload: RegisterPayload): Promise<RegisterResponse> {
  const { data } = await apiClient.post<RegisterResponse>("/users/register/", {
    username: payload.username,
    email: payload.email,
    password: payload.password,
    password_confirm: payload.passwordConfirm,
    first_name: payload.firstName || "",
    last_name: payload.lastName || "",
  });
  return data;
}

// POST /api/users/login/ (SimpleJWT TokenObtainPairView -> { access, refresh })
export async function login(payload: LoginPayload): Promise<TokenPair> {
  const { data } = await apiClient.post<TokenPair>("/users/login/", payload);
  tokenStore.setTokens(data);
  return data;
}

// GET /api/users/me/
export async function fetchMe(): Promise<User> {
  const { data } = await apiClient.get<User>("/users/me/");
  return data;
}

export function logout(): void {
  tokenStore.clear();
}
