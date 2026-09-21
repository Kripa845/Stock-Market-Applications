// src/App.tsx

import React from 'react';
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
import CompanyAnalysisDashboard from './pages/CompanyAnalysisDashboard';

import CompaniesPage from './pages/admin/CompaniesPage';
import UserManagementPage from './pages/admin/UserManagementPage';
import WatchlistComparison from './pages/WatchlistComparison';
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

import type { RouteRule } from './config/routePermissions';
import { ROUTE_RULES } from './config/routePermissions';


/* =========================================================
   PRIVATE ROUTE
========================================================= */

function PrivateRoute({
  children,
}: {
  children: React.ReactNode;
}) {
  const token = localStorage.getItem('access_token');
  const location = useLocation();

  if (!token) {
    return (
      <Navigate
        to="/login"
        state={{ from: location }}
        replace
      />
    );
  }

  return <>{children}</>;
}


/* =========================================================
   ROLE REDIRECT
========================================================= */

function RoleRedirect() {
  const { user, loading } = useAuth();

  if (loading) {
    return null;
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return <Navigate to="/dashboard" replace />;
}


/* =========================================================
   PERMISSION ROUTE
========================================================= */

function PermissionRoute({
  rule,
  children,
}: {
  rule?: RouteRule;
  children: React.ReactNode;
}) {
  const {
    user,
    loading,
    hasAnyPermission,
    hasAllPermissions,
  } = useAuth();

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

  /*
   * No rule means the route does not require
   * an application permission.
   */
  if (!rule || rule.permissions.length === 0) {
    return <>{children}</>;
  }

  const allowed =
    rule.mode === 'all'
      ? hasAllPermissions(rule.permissions)
      : hasAnyPermission(rule.permissions);

  if (!allowed) {
    const description = rule.permissions.join(', ');

    return (
      <ForbiddenPage
        requiredPermission={description}
        message={`You do not have the required permission(s): ${description}`}
      />
    );
  }

  return <>{children}</>;
}


/* =========================================================
   APPLICATION
========================================================= */

function AppRoutes() {
  return (
    <>
      <PermissionRefreshOnRouteChange />

      <Routes>

        {/* =================================================
            PUBLIC ROUTES
        ================================================= */}

        <Route
          path="/"
          element={<LandingPage />}
        />

        <Route
          path="/login"
          element={<LoginPage />}
        />

        <Route
          path="/register"
          element={<RegisterPage />}
        />


        {/* =================================================
            ROLE / AUTH REDIRECT
        ================================================= */}

        <Route
          path="/role-redirect"
          element={<RoleRedirect />}
        />


        {/* =================================================
            PROTECTED APPLICATION ROUTES
        ================================================= */}

        <Route
          element={
            <PrivateRoute>
              <Layout />
            </PrivateRoute>
          }
        >

          {/* -----------------------------------------------
              DASHBOARD
          ----------------------------------------------- */}

          <Route
            path="/dashboard"
            element={<Dashboard />}
          />


          {/* -----------------------------------------------
              MARKET
          ----------------------------------------------- */}

          <Route
            path="/market"
            element={
              <PermissionRoute
                rule={ROUTE_RULES['/market']}
              >
                <MarketPage />
              </PermissionRoute>
            }
          />


          {/* -----------------------------------------------
              COMPANIES
          ----------------------------------------------- */}

          <Route
            path="/companies"
            element={
              <PermissionRoute
                rule={ROUTE_RULES['/companies']}
              >
                <CompaniesPage />
              </PermissionRoute>
            }
          />

          <Route
            path="/companies/:symbol"
            element={
              <PermissionRoute
                rule={ROUTE_RULES['/companies/:symbol']}
              >
                <StockDetail />
              </PermissionRoute>
            }
          />


          {/* -----------------------------------------------
              TRADING
          ----------------------------------------------- */}

          <Route
            path="/trading"
            element={
              <PermissionRoute
                rule={ROUTE_RULES['/trading']}
              >
                <TradingPage />
              </PermissionRoute>
            }
          />


          {/* -----------------------------------------------
              ANALYTICS
          ----------------------------------------------- */}

          <Route
            path="/analytics"
            element={
              <PermissionRoute
                rule={ROUTE_RULES['/analytics']}
              >
                <TradingPage />
              </PermissionRoute>
            }
          />


          {/* -----------------------------------------------
              COMPANY ANALYSIS
          ----------------------------------------------- */}

          <Route
            path="/company-analysis"
            element={
              <PermissionRoute
                rule={ROUTE_RULES['/company-analysis']}
              >
                <CompanyAnalysisDashboard />
              </PermissionRoute>
            }
          />


          {/* -----------------------------------------------
              WATCHLIST COMPARISON
          ----------------------------------------------- */}

          <Route
            path="/watchlist-comparison"
            element={
              <PermissionRoute
                rule={ROUTE_RULES['/watchlist-comparison']}
              >
                <WatchlistComparison />
              </PermissionRoute>
            }
          />


          {/* -----------------------------------------------
              WATCHLIST
          ----------------------------------------------- */}

          <Route
            path="/watchlist"
            element={
              <PermissionRoute
                rule={ROUTE_RULES['/watchlist']}
              >
                <WatchlistPage />
              </PermissionRoute>
            }
          />


          {/* -----------------------------------------------
              NEWS
          ----------------------------------------------- */}

          <Route
            path="/news"
            element={
              <PermissionRoute
                rule={ROUTE_RULES['/news']}
              >
                <NewsPage />
              </PermissionRoute>
            }
          />

          <Route
            path="/news/:id"
            element={
              <PermissionRoute
                rule={ROUTE_RULES['/news']}
              >
                <NewsDetail />
              </PermissionRoute>
            }
          />


          {/* -----------------------------------------------
              CRAWL MANAGEMENT
          ----------------------------------------------- */}

          <Route
            path="/crawl"
            element={
              <PermissionRoute
                rule={ROUTE_RULES['/crawl']}
              >
                <CrawlerStatusPage />
              </PermissionRoute>
            }
          />


          {/* -----------------------------------------------
              REPORTS
          ----------------------------------------------- */}

          <Route
            path="/reports"
            element={
              <PermissionRoute
                rule={ROUTE_RULES['/reports']}
              >
                <ReportsComingSoon />
              </PermissionRoute>
            }
          />


          {/* -----------------------------------------------
              USER MANAGEMENT
          ----------------------------------------------- */}

          <Route
            path="/users"
            element={
              <PermissionRoute
                rule={ROUTE_RULES['/users']}
              >
                <UserManagementPage />
              </PermissionRoute>
            }
          />


          {/* -----------------------------------------------
              ROLES & PERMISSIONS
          ----------------------------------------------- */}

          <Route
            path="/roles-permissions"
            element={
              <PermissionRoute
                rule={ROUTE_RULES['/roles-permissions']}
              >
                <RolesPermissionsPage />
              </PermissionRoute>
            }
          />


          {/* =================================================
              LEGACY ROUTES / REDIRECTS
          ================================================= */}

          <Route
            path="/admin"
            element={<Navigate to="/dashboard" replace />}
          />

          <Route
            path="/admin/dashboard"
            element={<Navigate to="/dashboard" replace />}
          />

          <Route
            path="/admin/users"
            element={<Navigate to="/users" replace />}
          />

          <Route
            path="/admin/companies"
            element={<Navigate to="/companies" replace />}
          />

          <Route
            path="/admin/watchlist"
            element={<Navigate to="/watchlist" replace />}
          />

          <Route
            path="/admin/news"
            element={<Navigate to="/news" replace />}
          />

          <Route
            path="/admin/crawl"
            element={<Navigate to="/crawl" replace />}
          />

          <Route
            path="/admin/reports"
            element={<Navigate to="/reports" replace />}
          />

          <Route
            path="/admin/roles-permissions"
            element={
              <Navigate
                to="/roles-permissions"
                replace
              />
            }
          />

          <Route
            path="/analyst/stocks"
            element={<Navigate to="/companies" replace />}
          />

          <Route
            path="/analyst/trading"
            element={<Navigate to="/trading" replace />}
          />

          <Route
            path="/analyst/news"
            element={<Navigate to="/news" replace />}
          />


          {/* =================================================
              FALLBACK
          ================================================= */}

          <Route
            path="*"
            element={<NotFound />}
          />

        </Route>
      </Routes>
    </>
  );
}


/* =========================================================
   APP PROVIDER
========================================================= */

export default function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  );
}