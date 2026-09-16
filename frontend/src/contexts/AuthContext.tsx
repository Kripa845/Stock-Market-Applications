import {
  createContext,
  useContext,
  useEffect,
  useState,
} from "react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { authApi } from "../api/auth";
import { usePermissions as usePermissionCheck } from "../hooks/usePermissions";

interface User {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  role: "admin" | "analyst" | "viewer";
  custom_role_id?: number | null;
  custom_role_name?: string | null;
  effective_role?: string;
  is_active: boolean;
  date_joined: string;
  last_login: string | null;
  permissions?: string[];
}

interface AuthContextType {
  user: User | null;
  permissions: string[];
  effectiveRole: string | null;
  loading: boolean;
  error: string | null;
  login: (username: string, password: string) => Promise<void>;
  register: (data: {
    username: string;
    email: string;
    password: string;
    password_confirm: string;
    first_name: string;
    last_name: string;
    role?: "viewer" | "analyst" | "admin";
  }) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
  refreshPermissions: () => Promise<void>;
  clearError: () => void;
  hasPermission: (key: string) => boolean;
  hasAnyPermission: (keys: string[]) => boolean;
  hasAllPermissions: (keys: string[]) => boolean;
  canCategorizeNews: boolean;
  canCorrectCategories: boolean;
  canAccessRoute: (requiredPermissions?: string[]) => boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const navigate = useNavigate();
  const [user, setUser] = useState<User | null>(null);
  const [permissions, setPermissions] = useState<string[]>([]);
  const [effectiveRole, setEffectiveRole] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const permissionCheck = usePermissionCheck(
    user?.role,
    permissions
  );

  const loadUserFromStorage = (): User | null => {
    const storedUser = localStorage.getItem("user");
    if (!storedUser) return null;
    try {
      return JSON.parse(storedUser) as User;
    } catch {
      return null;
    }
  };

  const fetchPermissions = async () => {
    try {
      const response = await authApi.permissions();
      setPermissions(response.permissions || []);
      setEffectiveRole(response.effective_role || null);
    } catch (err) {
      console.error("Failed to fetch permissions:", err);
      setPermissions([]);
    }
  };

  const refreshUser = async () => {
    try {
      const response = await authApi.me();
      const userData: User = {
        ...response,
        permissions: [],
      };
      setUser(userData);
      localStorage.setItem("user", JSON.stringify(userData));
      await refreshPermissions();
      setEffectiveRole(userData.effective_role || null);
    } catch (err) {
      console.error("Failed to refresh user:", err);
      throw err;
    }
  };

  const refreshPermissions = async () => {
    if (!user) return;
    try {
      const response = await authApi.permissions();
      setPermissions(response.permissions || []);
      setEffectiveRole(response.effective_role || null);
    } catch (err) {
      console.error("Failed to refresh permissions:", err);
    }
  };

  const login = async (username: string, password: string) => {
    setError(null);
    setLoading(true);
    try {
      const response = await authApi.login(username, password);
      localStorage.setItem("access_token", response.access);
      localStorage.setItem("refresh_token", response.refresh);
      const userData: User = {
        ...response.user,
        permissions: [],
      };
      localStorage.setItem("user", JSON.stringify(userData));
      setUser(userData);
      // Fetch permissions separately since login response doesn't include them
      await fetchPermissions();
    } catch (err: any) {
      const data = err?.response?.data;
      if (data?.detail) {
        setError(data.detail);
      } else if (data?.non_field_errors) {
        setError(
          Array.isArray(data.non_field_errors)
            ? data.non_field_errors.join(", ")
            : String(data.non_field_errors)
        );
      } else {
        setError("Invalid username or password.");
      }
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const register = async (data: {
    username: string;
    email: string;
    password: string;
    password_confirm: string;
    first_name: string;
    last_name: string;
    role?: "viewer" | "analyst" | "admin";
  }) => {
    setError(null);
    setLoading(true);
    try {
      const response = await authApi.register(data);
      const userData: User = {
        ...response.user,
        permissions: response.user.permissions || [],
      };
      localStorage.setItem("user", JSON.stringify(userData));
      setUser(userData);
      setPermissions(userData.permissions || []);
      setEffectiveRole(userData.effective_role || null);
    } catch (err: any) {
      const data = err?.response?.data;
      const messages = Object.entries(data || {}).map(
        ([key, value]) =>
          `${key}: ${Array.isArray(value) ? value.join(", ") : value}`
      );
      setError(messages.join("; ") || "Registration failed.");
      throw err;
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    localStorage.clear();
    setUser(null);
    setPermissions([]);
    setEffectiveRole(null);
    setError(null);
    navigate("/login");
  };

  const clearError = () => {
    setError(null);
  };

  const canAccessRoute = (requiredPermissions?: string[]) => {
    if (!user) return false;
    if (user.role === "admin") return true;
    if (!requiredPermissions || requiredPermissions.length === 0) return true;
    return requiredPermissions.some((p) => permissions.includes(p));
  };

  useEffect(() => {
    const initAuth = async () => {
      const storedUser = loadUserFromStorage();
      if (storedUser) {
        setUser(storedUser);
        try {
          await fetchPermissions();
        } catch {
          // ignore
        }
      }
      setLoading(false);
    };
    initAuth();
  }, []);

  const value: AuthContextType = {
    user,
    permissions,
    effectiveRole,
    loading,
    error,
    login,
    register,
    logout,
    refreshUser,
    refreshPermissions,
    clearError,
    hasPermission: permissionCheck.can,
    hasAnyPermission: permissionCheck.hasAnyPermission,
    hasAllPermissions: permissionCheck.hasAllPermission,
    canCategorizeNews: permissionCheck.canCategorizeNews,
    canCorrectCategories: permissionCheck.canCorrectCategories,
    canAccessRoute,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}
