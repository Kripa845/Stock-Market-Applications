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
import TechnicalCharts from './pages/TechnicalCharts';
import FloorsheetPage from './pages/FloorsheetPage';
import TopBrokerStocksPage from './pages/TopBrokerStocksPage';
import BrokerAnalysisPage, { BrokerDetailPage } from './pages/BrokerAnalysisPage';
import TopBrokerPage from './pages/TopBrokerPage';

import CompaniesPage from './pages/admin/CompaniesPage';
import UserManagementPage from './pages/admin/UserManagementPage';
import WatchlistComparison from './pages/WatchlistComparison';
import AdminWatchlistPage from './pages/admin/WatchlistPage';
import WatchlistPage from './pages/WatchlistPage';
import MyWatchlistPage from './pages/MyWatchlistPage';
import RolesPermissionsPage from './pages/admin/RolesPermissionPage';

import CrawlerStatusPage from './pages/CrawlerStatus';
import MarketPage from './pages/Market';
import TopMoversPage from './pages/TopMoversPage';
import DividendsPage from './pages/DividendsPage';
import IndicesPage from './pages/IndicesPage';
import TopActivityPage from './pages/TopActivityPage';
import StockDetail from './pages/StockDetail';
import NewsPage from './pages/News';
import NewsDetail from './pages/NewsDetail';
import ExportPage from './pages/ExportPage';

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


function LiveTradingPageWrapper() {
  const { user } = useAuth();
  return user?.role === 'admin' ? <AdminWatchlistPage /> : <WatchlistPage />;
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
            TECHNICAL CHARTS — full-screen terminal, outside the
            app Layout (no sidebar / header / footer)
        ================================================= */}

        <Route
          path="/technical-charts"
          element={
            <PrivateRoute>
              <PermissionRoute
                rule={ROUTE_RULES['/technical-charts']}
              >
                <TechnicalCharts />
              </PermissionRoute>
            </PrivateRoute>
          }
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


          <Route
            path="/market/indices"
            element={
              <PermissionRoute
                rule={ROUTE_RULES['/market/indices']}
              >
                <IndicesPage />
              </PermissionRoute>
            }
          />

          <Route
            path="/market/dividends"
            element={
              <PermissionRoute
                rule={ROUTE_RULES['/market/dividends']}
              >
                <DividendsPage />
              </PermissionRoute>
            }
          />

          <Route
            path="/market/gainers"
            element={
              <PermissionRoute
                rule={ROUTE_RULES['/market/gainers']}
              >
                <TopMoversPage key="gainers" side="gainers" />
              </PermissionRoute>
            }
          />

          <Route
            path="/market/losers"
            element={
              <PermissionRoute
                rule={ROUTE_RULES['/market/losers']}
              >
                <TopMoversPage key="losers" side="losers" />
              </PermissionRoute>
            }
          />

          <Route
            path="/market/turnover"
            element={
              <PermissionRoute
                rule={ROUTE_RULES['/market/turnover']}
              >
                <TopActivityPage key="turnover" metric="turnover" />
              </PermissionRoute>
            }
          />

          <Route
            path="/market/volume"
            element={
              <PermissionRoute
                rule={ROUTE_RULES['/market/volume']}
              >
                <TopActivityPage key="volume" metric="volume" />
              </PermissionRoute>
            }
          />

          <Route
            path="/market/transactions"
            element={
              <PermissionRoute
                rule={ROUTE_RULES['/market/transactions']}
              >
                <TopActivityPage key="transactions" metric="transactions" />
              </PermissionRoute>
            }
          />


          {/* Tracked Companies page was removed; keep old links working. */}
          <Route
            path="/tracked"
            element={<Navigate to="/companies" replace />}
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
              FLOORSHEET
          ----------------------------------------------- */}

          <Route
            path="/floorsheet"
            element={
              <PermissionRoute
                rule={ROUTE_RULES['/floorsheet']}
              >
                <FloorsheetPage />
              </PermissionRoute>
            }
          />

          {/* -----------------------------------------------
              COMPANY ANALYSIS (full dashboard; not in the sidebar for now)
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

          <Route
            path="/broker-analysis"
            element={<PermissionRoute rule={ROUTE_RULES['/broker-analysis']}><BrokerAnalysisPage /></PermissionRoute>}
          />
          <Route
            path="/broker-analysis/:brokerId"
            element={<PermissionRoute rule={ROUTE_RULES['/broker-analysis']}><BrokerDetailPage /></PermissionRoute>}
          />
          <Route
            path="/top-brokers"
            element={<PermissionRoute rule={ROUTE_RULES['/top-brokers']}><TopBrokerPage /></PermissionRoute>}
          />
          <Route
            path="/top-brokers/:broker"
            element={<PermissionRoute rule={ROUTE_RULES['/top-brokers']}><TopBrokerStocksPage /></PermissionRoute>}
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
                <MyWatchlistPage />
              </PermissionRoute>
            }
          />

          <Route
            path="/live-trading"
            element={
              <PermissionRoute
                rule={ROUTE_RULES['/live-trading']}
              >
                <LiveTradingPageWrapper />
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
                <ExportPage />
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
            element={<Navigate to="/technical-charts" replace />}
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
