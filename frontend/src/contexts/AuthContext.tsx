import {
  createContext,
  useCallback,
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

  // ============================================================
  // LOAD USER FROM LOCAL STORAGE
  // ============================================================

  const loadUserFromStorage = (): User | null => {
    const storedUser = localStorage.getItem("user");

    if (!storedUser) {
      return null;
    }

    try {
      return JSON.parse(storedUser) as User;
    } catch {
      return null;
    }
  };

  // ============================================================
  // APPLY SERVER PERMISSIONS
  //
  // The backend is the source of truth for the user's role and
  // effective permissions.
  // ============================================================

  const applyPermissions = useCallback(
    (response: {
      permissions: string[];
      role: string;
      effective_role: string;
    }) => {
      setPermissions(response.permissions || []);
      setEffectiveRole(response.effective_role || null);

      setUser((previousUser) => {
        if (!previousUser) {
          return previousUser;
        }

        // Server role has not changed.
        if (previousUser.role === response.role) {
          return previousUser;
        }

        const nextUser: User = {
          ...previousUser,
          role: response.role as User["role"],
          effective_role: response.effective_role,
        };

        localStorage.setItem(
          "user",
          JSON.stringify(nextUser)
        );

        return nextUser;
      });
    },
    []
  );

  // ============================================================
  // INITIAL PERMISSION FETCH
  //
  // Fail closed: if permissions cannot be loaded, don't keep
  // previously cached permissions.
  // ============================================================

  const fetchPermissions = useCallback(async () => {
    try {
      const response = await authApi.permissions();

      applyPermissions(response);
    } catch (err) {
      console.error("Failed to fetch permissions:", err);

      // Fail closed.
      setPermissions([]);
      setEffectiveRole(null);
    }
  }, [applyPermissions]);

  // ============================================================
  // REFRESH PERMISSIONS
  //
  // IMPORTANT:
  // Do NOT use the `user` state here because it may be stale
  // immediately after a role change.
  //
  // The presence of an access token is enough to make the request.
  // ============================================================

  const refreshPermissions = useCallback(async () => {
    if (!localStorage.getItem("access_token")) {
      return;
    }

    try {
      const response = await authApi.permissions();

      applyPermissions(response);
    } catch (err) {
      console.error(
        "Failed to refresh permissions:",
        err
      );
    }
  }, [applyPermissions]);

  // ============================================================
  // REFRESH CURRENT USER
  // ============================================================

  const refreshUser = async () => {
    try {
      const response = await authApi.me();

      const userData: User = {
        ...response,
        permissions: [],
      };

      setUser(userData);

      localStorage.setItem(
        "user",
        JSON.stringify(userData)
      );

      // Fetch the server's current permissions and role.
      await refreshPermissions();

      setEffectiveRole(
        userData.effective_role || null
      );
    } catch (err) {
      console.error(
        "Failed to refresh user:",
        err
      );

      throw err;
    }
  };

  // ============================================================
  // LOGIN
  // ============================================================

  const login = async (
    username: string,
    password: string
  ) => {
    setError(null);
    setLoading(true);

    try {
      const response = await authApi.login(
        username,
        password
      );

      localStorage.setItem(
        "access_token",
        response.access
      );

      localStorage.setItem(
        "refresh_token",
        response.refresh
      );

      const userData: User = {
        ...response.user,
        permissions: [],
      };

      localStorage.setItem(
        "user",
        JSON.stringify(userData)
      );

      setUser(userData);

      // Login response does not necessarily contain the
      // authoritative permission set.
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
        setError(
          "Invalid username or password."
        );
      }

      throw err;
    } finally {
      setLoading(false);
    }
  };

  // ============================================================
  // REGISTER
  //
  // IMPORTANT:
  // The client no longer sends a role.
  // The backend decides the initial role.
  // ============================================================

  const register = async (data: {
    username: string;
    email: string;
    password: string;
    password_confirm: string;
    first_name: string;
    last_name: string;
  }) => {
    setError(null);
    setLoading(true);

    try {
      const response = await authApi.register(data);

      const userData: User = {
        ...response.user,
        permissions:
          response.user.permissions || [],
      };

      localStorage.setItem(
        "user",
        JSON.stringify(userData)
      );

      setUser(userData);

      setPermissions(
        userData.permissions || []
      );

      setEffectiveRole(
        userData.effective_role || null
      );
    } catch (err: any) {
      const data = err?.response?.data;

      const messages = Object.entries(
        data || {}
      ).map(
        ([key, value]) =>
          `${key}: ${
            Array.isArray(value)
              ? value.join(", ")
              : value
          }`
      );

      setError(
        messages.join("; ") ||
          "Registration failed."
      );

      throw err;
    } finally {
      setLoading(false);
    }
  };

  // ============================================================
  // LOGOUT
  // ============================================================

  const logout = () => {
    localStorage.clear();

    setUser(null);
    setPermissions([]);
    setEffectiveRole(null);
    setError(null);

    navigate("/login");
  };

  // ============================================================
  // CLEAR ERROR
  // ============================================================

  const clearError = () => {
    setError(null);
  };

  // ============================================================
  // LEGACY ROUTE CHECK
  //
  // Keep this function for components that still call
  // canAccessRoute().
  //
  // The new App.tsx route protection should use ROUTE_RULES
  // with hasAnyPermission()/hasAllPermissions().
  // ============================================================

  const canAccessRoute = (
    requiredPermissions?: string[]
  ) => {
    if (!user) {
      return false;
    }

    if (
      !requiredPermissions ||
      requiredPermissions.length === 0
    ) {
      return true;
    }

    return requiredPermissions.some(
      (permission) =>
        permissions.includes(permission)
    );
  };

  // ============================================================
  // REFRESH PERMISSIONS WHEN SERVER RETURNS 403
  //
  // This is important when an admin changes another role's
  // permissions while that user is already logged in.
  // ============================================================

  useEffect(() => {
    let lastRefresh = 0;

    const onForbidden = () => {
      const now = Date.now();

      // Prevent a burst of 403 responses from causing many
      // permission requests.
      if (now - lastRefresh < 5000) {
        return;
      }

      lastRefresh = now;

      void refreshPermissions();
    };

    window.addEventListener(
      "auth:forbidden",
      onForbidden
    );

    return () => {
      window.removeEventListener(
        "auth:forbidden",
        onForbidden
      );
    };
  }, [refreshPermissions]);

  // ============================================================
  // INITIAL AUTHENTICATION
  // ============================================================

  useEffect(() => {
    let mounted = true;

    const initAuth = async () => {
      const storedUser =
        loadUserFromStorage();

      if (storedUser && mounted) {
        setUser(storedUser);

        setEffectiveRole(
          storedUser.effective_role || null
        );

        // Fetch current server permissions.
        // This means permission changes are picked up on
        // refresh/navigation without requiring a new login.
        await fetchPermissions();
      }

      if (mounted) {
        setLoading(false);
      }
    };

    void initAuth();

    return () => {
      mounted = false;
    };
  }, [fetchPermissions]);

  // ============================================================
  // CONTEXT VALUE
  // ============================================================

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

    hasPermission:
      permissionCheck.can,

    hasAnyPermission:
      permissionCheck.hasAnyPermission,

    hasAllPermissions:
      permissionCheck.hasAllPermission,

    canCategorizeNews:
      permissionCheck.canCategorizeNews,

    canCorrectCategories:
      permissionCheck.canCorrectCategories,

    canAccessRoute,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}