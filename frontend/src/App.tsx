import {
  Routes,
  Route,
  Navigate,
  useLocation,
} from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import PermissionRefreshOnRouteChange from './components/PermissionRefreshOnRouteChange';

import LandingPage from './pages/LandingPage';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegistrationPage';
import Layout from './components/layout/Layout';

import Dashboard from './pages/Dashboard';
import CompaniesPage from './pages/admin/CompaniesPage';
import UserManagementPage from './pages/admin/UserManagementPage';
import WatchlistPage from './pages/admin/WatchlistPage';
import RolesPermissionsPage from './pages/admin/RolesPermissionPage';
import CrawlerStatusPage from './pages/CrawlerStatus';
import MarketPage from './pages/Market';
import StockDetail from './pages/StockDetail';
import NewsPage from './pages/News';
import NewsDetail from './pages/NewsDetail';
import TradingPage from './pages/Trading';
import ReportsComingSoon from './pages/ReportsComingSoon';
import ForbiddenPage from './pages/ForbiddenPage';
import NotFound from './pages/NotFound';


// ============================================================
// PRIVATE ROUTE — must be authenticated (token present)
// ============================================================
function PrivateRoute({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem('access_token');
  const location = useLocation();

  if (!token) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}


// ============================================================
// PERMISSION ROUTE — authenticated + must hold permission(s)
// Shows 403 page on denial instead of silently redirecting.
// ============================================================
interface PermissionRouteProps {
  requiredPermissions?: string[];
  /** Require ALL listed permissions (default: ANY one suffices) */
  mode?: 'any' | 'all';
  children: React.ReactNode;
}

function PermissionRoute({
  requiredPermissions,
  mode = 'any',
  children,
}: PermissionRouteProps) {
  const { user, loading, hasAnyPermission, hasAllPermissions } =
    useAuth();

  // Show nothing while auth is initialising to avoid flash of unauthorised UI
  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-accent border-t-transparent" />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  // No restrictions declared — any authenticated user may pass
  if (!requiredPermissions || requiredPermissions.length === 0) {
    return <>{children}</>;
  }

  const allowed =
    mode === 'all'
      ? hasAllPermissions(requiredPermissions)
      : hasAnyPermission(requiredPermissions);

  if (!allowed) {
    const desc =
      requiredPermissions.length === 1
        ? requiredPermissions[0]
        : requiredPermissions.join(', ');
    return (
      <ForbiddenPage
        requiredPermission={desc}
        message={`You do not have the required permission(s): ${desc}`}
      />
    );
  }

  return <>{children}</>;
}


// ============================================================
// ROLE REDIRECT — after login, send users to /dashboard
// ============================================================
function RoleRedirect() {
  const { user, loading } = useAuth();

  if (loading) return null;
  if (!user) return <Navigate to="/login" replace />;

  // All roles now share a single /dashboard route
  return <Navigate to="/dashboard" replace />;
}


// ============================================================
// APPLICATION
// ============================================================
export default function App() {
  return (
    <AuthProvider>
      <PermissionRefreshOnRouteChange />
      <Routes>

        {/* ================================================
            PUBLIC
            ================================================ */}
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />

        {/* ================================================
            AUTHENTICATED — all roles inside a shared Layout
            ================================================ */}
        <Route
          element={
            <PrivateRoute>
              <Layout />
            </PrivateRoute>
          }
        >
          {/* Dashboard — single unified permission-driven page */}
          <Route path="/dashboard" element={<Dashboard />} />

          {/* Legacy role-prefixed dashboard redirects */}
          <Route path="/admin"    element={<RoleRedirect />} />
          <Route path="/analyst"  element={<RoleRedirect />} />
          <Route path="/viewer"   element={<RoleRedirect />} />

          {/* ---- Market Data ---- */}
          <Route
            path="/market"
            element={
              <PermissionRoute requiredPermissions={['view_market_data']}>
                <MarketPage />
              </PermissionRoute>
            }
          />
          <Route
            path="/trading"
            element={
              <PermissionRoute requiredPermissions={['view_market_data', 'view_trading_volume']}>
                <TradingPage />
              </PermissionRoute>
            }
          />

          {/* ---- Companies / Stocks ---- */}
          <Route
            path="/companies"
            element={
              <PermissionRoute requiredPermissions={['view_companies']}>
                <CompaniesPage />
              </PermissionRoute>
            }
          />
          <Route
            path="/companies/:symbol"
            element={
              <PermissionRoute requiredPermissions={['view_companies']}>
                <StockDetail />
              </PermissionRoute>
            }
          />

          {/* ---- Watchlist ---- */}
          <Route
            path="/watchlist"
            element={
              <PermissionRoute requiredPermissions={['view_watchlist']}>
                <WatchlistPage />
              </PermissionRoute>
            }
          />

          {/* ---- News ---- */}
          <Route
            path="/news"
            element={
              <PermissionRoute requiredPermissions={['view_news']}>
                <NewsPage />
              </PermissionRoute>
            }
          />
          <Route
            path="/news/:id"
            element={
              <PermissionRoute requiredPermissions={['view_news']}>
                <NewsDetail />
              </PermissionRoute>
            }
          />

          {/* ---- Crawlers ---- */}
          <Route
            path="/crawl"
            element={
              <PermissionRoute requiredPermissions={['view_crawl_runs']}>
                <CrawlerStatusPage />
              </PermissionRoute>
            }
          />

          {/* ---- Analysis / Analytics ---- */}
          <Route
            path="/analytics"
            element={
              <PermissionRoute requiredPermissions={['view_analysis']}>
                <TradingPage />
              </PermissionRoute>
            }
          />

          {/* ---- Reports ---- */}
          <Route
            path="/reports"
            element={
              <PermissionRoute requiredPermissions={['view_reports']}>
                <ReportsComingSoon />
              </PermissionRoute>
            }
          />

          {/* ---- User Management ---- */}
          <Route
            path="/users"
            element={
              <PermissionRoute requiredPermissions={['view_users']}>
                <UserManagementPage />
              </PermissionRoute>
            }
          />

          {/* ---- Roles & Permissions ---- */}
          <Route
            path="/roles-permissions"
            element={
              <PermissionRoute requiredPermissions={['view_roles']}>
                <RolesPermissionsPage />
              </PermissionRoute>
            }
          />

          {/* ---- Legacy role-namespaced paths — redirect to unified paths ---- */}
          <Route path="/admin/companies"        element={<Navigate to="/companies" replace />} />
          <Route path="/admin/watchlist"         element={<Navigate to="/watchlist" replace />} />
          <Route path="/admin/users"             element={<Navigate to="/users" replace />} />
          <Route path="/admin/roles-permissions" element={<Navigate to="/roles-permissions" replace />} />
          <Route path="/admin/news"              element={<Navigate to="/news" replace />} />
          <Route path="/admin/news/:id"          element={<Navigate to="/news/:id" replace />} />
          <Route path="/admin/crawl"             element={<Navigate to="/crawl" replace />} />
          <Route path="/admin/crawl-runs"        element={<Navigate to="/crawl" replace />} />
          <Route path="/admin/reports"           element={<Navigate to="/reports" replace />} />
          <Route path="/admin/analysts"          element={<Navigate to="/users" replace />} />

          <Route path="/analyst/market"          element={<Navigate to="/market" replace />} />
          <Route path="/analyst/companies"       element={<Navigate to="/companies" replace />} />
          <Route path="/analyst/stocks"          element={<Navigate to="/companies" replace />} />
          <Route path="/analyst/stocks/:symbol"  element={<Navigate to="/companies/:symbol" replace />} />
          <Route path="/analyst/news"            element={<Navigate to="/news" replace />} />
          <Route path="/analyst/news/:id"        element={<Navigate to="/news/:id" replace />} />
          <Route path="/analyst/trading"         element={<Navigate to="/trading" replace />} />
          <Route path="/analyst/watchlist"       element={<Navigate to="/watchlist" replace />} />
          <Route path="/analyst/analytics"       element={<Navigate to="/analytics" replace />} />
          <Route path="/analyst/reports"         element={<Navigate to="/reports" replace />} />

          <Route path="/viewer/market"           element={<Navigate to="/market" replace />} />
          <Route path="/viewer/companies"        element={<Navigate to="/companies" replace />} />
          <Route path="/viewer/stocks"           element={<Navigate to="/companies" replace />} />
          <Route path="/viewer/stocks/:symbol"   element={<Navigate to="/companies/:symbol" replace />} />
          <Route path="/viewer/news"             element={<Navigate to="/news" replace />} />
          <Route path="/viewer/news/:id"         element={<Navigate to="/news/:id" replace />} />
          <Route path="/viewer/trading"          element={<Navigate to="/trading" replace />} />
          <Route path="/viewer/watchlist"        element={<Navigate to="/watchlist" replace />} />
          <Route path="/viewer/analytics"        element={<Navigate to="/analytics" replace />} />
          <Route path="/viewer/reports"          element={<Navigate to="/reports" replace />} />

          <Route path="/stocks/:symbol"          element={<Navigate to="/companies/:symbol" replace />} />

          {/* ---- 403 Forbidden ---- */}
          <Route path="/forbidden" element={<ForbiddenPage />} />
        </Route>

        {/* 404 */}
        <Route path="*" element={<NotFound />} />

      </Routes>
    </AuthProvider>
  );
}
