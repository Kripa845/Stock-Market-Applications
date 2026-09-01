import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import * as authApi from "../api/auth";
import { tokenStore } from "../api/client";
import type { LoginPayload, RegisterPayload, Role, User } from "../types";

interface AuthContextValue {
  user: User | null;
  initializing: boolean;
  login: (credentials: LoginPayload) => Promise<User>;
  register: (payload: RegisterPayload) => Promise<{ message: string; user: User }>;
  logout: () => void;
  hasRole: (...roles: Role[]) => boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [initializing, setInitializing] = useState(true);

  const loadMe = useCallback(async () => {
    if (!tokenStore.getAccess()) {
      setUser(null);
      setInitializing(false);
      return;
    }
    try {
      const me = await authApi.fetchMe();
      setUser(me);
    } catch {
      tokenStore.clear();
      setUser(null);
    } finally {
      setInitializing(false);
    }
  }, []);

  useEffect(() => {
    loadMe();
  }, [loadMe]);

  const login = async (credentials: LoginPayload): Promise<User> => {
    await authApi.login(credentials);
    const me = await authApi.fetchMe();
    setUser(me);
    return me;
  };

  const register = async (payload: RegisterPayload) => {
    return authApi.register(payload);
  };

  const logout = (): void => {
    authApi.logout();
    setUser(null);
  };

  const hasRole = (...roles: Role[]): boolean => !!user && roles.includes(user.role);

  const value: AuthContextValue = { user, initializing, login, register, logout, hasRole };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
