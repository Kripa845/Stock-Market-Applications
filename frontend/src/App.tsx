import {
  Routes,
  Route,
  Navigate,
} from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import PermissionRefreshOnRouteChange from './components/PermissionRefreshOnRouteChange';

import LandingPage from './pages/LandingPage';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegistrationPage';
import RolesPermissionsPage from "./pages/admin/RolesPermissionPage";
import Layout from './components/layout/Layout';
import CompaniesPage from './pages/admin/CompaniesPage';
import UserManagementPage from './pages/admin/UserManagementPage';
import WatchlistPage from './pages/admin/WatchlistPage';
import CrawlerStatusPage from './pages/CrawlerStatus';
import MarketPage from './pages/Market';
import StockDetail from './pages/StockDetail';
import NewsPage from './pages/News';
import NewsDetail from './pages/NewsDetail';
import TradingPage from './pages/Trading';

// =========================
// ADMIN PAGES
// =========================
import AdminDashboard from './pages/Dashboard';
import AnalystsPage from './pages/AnalystDashboard';

// Existing pages
import AdminNewsPage from './pages/News';

// =========================
// ANALYST / VIEWER
// =========================
import AnalystDashboard from './pages/AnalystDashboard';
import ViewerDashboard from './pages/ViewerDashboard';

import NotFound from './pages/NotFound';


// ======================================================
// PRIVATE ROUTE
// ======================================================
function PrivateRoute({
  children,
}: {
  children: React.ReactNode;
}) {
  const token = localStorage.getItem('access_token');

  if (!token) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}


// ======================================================
// PERMISSION ROUTE
// ======================================================
function PermissionRoute({
  requiredPermissions,
  children,
}: {
  requiredPermissions?: string[];
  children: React.ReactNode;
}) {
  const { user, canAccessRoute, loading } = useAuth();

  if (loading) {
    return <div className="p-6 text-center">Loading...</div>;
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (!canAccessRoute(requiredPermissions)) {
    if (user.role === 'admin') {
      return <Navigate to="/admin" replace />;
    }
    if (user.role === 'analyst') {
      return <Navigate to="/analyst" replace />;
    }
    return <Navigate to="/viewer" replace />;
  }

  return <>{children}</>;
}


// ======================================================
// APPLICATION
// ======================================================
export default function App() {
  return (
    <AuthProvider>
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
            ADMIN ROUTES
            ================================================= */}

        <Route
          element={
            <PrivateRoute>
              <Layout />
            </PrivateRoute>
          }
        >

          <Route
            path="/admin"
            element={<AdminDashboard />}
          />

          <Route
            path="/admin/companies"
            element={
              <PermissionRoute requiredPermissions={["view_companies"]}>
                <CompaniesPage />
              </PermissionRoute>
            }
          />

          <Route
            path="/admin/watchlist"
            element={
              <PermissionRoute requiredPermissions={["view_watchlist"]}>
                <WatchlistPage />
              </PermissionRoute>
            }
          />

          <Route path="/admin/crawl" element={
            <PermissionRoute requiredPermissions={["view_crawl_runs"]}>
              <CrawlerStatusPage />
            </PermissionRoute>
          } />
          <Route path="/admin/crawl-runs" element={
            <PermissionRoute requiredPermissions={["view_crawl_runs"]}>
              <CrawlerStatusPage />
            </PermissionRoute>
          } />

          <Route
            path="/admin/users"
            element={
              <PermissionRoute requiredPermissions={["view_users"]}>
                <UserManagementPage />
              </PermissionRoute>
            }
          />

          <Route
            path="/admin/analysts"
            element={
              <PermissionRoute requiredPermissions={["view_users"]}>
                <AnalystsPage />
              </PermissionRoute>
            }
          />

          <Route
            path="/admin/news"
            element={
              <PermissionRoute requiredPermissions={["view_news"]}>
                <AdminNewsPage />
              </PermissionRoute>
            }
          />
          <Route
            path="/admin/news/:id"
            element={
              <PermissionRoute requiredPermissions={["view_news"]}>
                <NewsDetail />
              </PermissionRoute>
            }
          />
          <Route
            path="/news/:id"
            element={<NewsDetail />}
          />

          <Route
            path="/admin/roles-permissions"
            element={
              <PermissionRoute requiredPermissions={["view_roles"]}>
                <RolesPermissionsPage />
              </PermissionRoute>
            }
          />

        </Route>


        {/* =================================================
            ANALYST ROUTES
            ================================================= */}

        <Route
          element={
            <PrivateRoute>
              <Layout />
            </PrivateRoute>
          }
        >

          <Route
            path="/analyst"
            element={<PermissionRoute requiredPermissions={["view_analysis"]}><AnalystDashboard /></PermissionRoute>}
          />
          <Route path="/analyst/market" element={<PermissionRoute requiredPermissions={["view_market_data"]}><MarketPage /></PermissionRoute>} />
          <Route path="/analyst/stocks" element={<MarketPage />} />
          <Route path="/analyst/stocks/:symbol" element={<StockDetail />} />
          <Route path="/stocks/:symbol" element={<StockDetail />} />
          <Route path="/analyst/news" element={<PermissionRoute requiredPermissions={["view_news"]}><NewsPage /></PermissionRoute>} />
          <Route path="/analyst/news-review" element={<PermissionRoute requiredPermissions={["correct_categories"]}><NewsPage /></PermissionRoute>} />
          <Route path="/analyst/news/:id" element={<NewsDetail />} />
          <Route path="/news/:id" element={<NewsDetail />} />
          <Route path="/analyst/trading" element={<PermissionRoute requiredPermissions={["view_market_data"]}><TradingPage /></PermissionRoute>} />

        </Route>


        {/* =================================================
            VIEWER ROUTES
            ================================================= */}

        <Route
          element={
            <PrivateRoute>
              <Layout />
            </PrivateRoute>
          }
        >

          <Route
            path="/viewer"
            element={<PermissionRoute requiredPermissions={["view_analysis"]}><ViewerDashboard /></PermissionRoute>}
          />
          <Route path="/viewer/market" element={<PermissionRoute requiredPermissions={["view_watchlist"]}><WatchlistPage /></PermissionRoute>} />
          <Route path="/viewer/stocks" element={<MarketPage />} />
          <Route path="/viewer/stocks/:symbol" element={<StockDetail />} />
          <Route path="/stocks/:symbol" element={<StockDetail />} />
          <Route path="/viewer/news" element={<PermissionRoute requiredPermissions={["view_news"]}><NewsPage /></PermissionRoute>} />
          <Route path="/viewer/news/:id" element={<NewsDetail />} />
          <Route path="/news/:id" element={<NewsDetail />} />
          <Route path="/viewer/trading" element={<PermissionRoute requiredPermissions={["view_market_data"]}><TradingPage /></PermissionRoute>} />

        </Route>


        {/* =================================================
            404
            ================================================= */}
        <Route
          path="*"
          element={<NotFound />}
        />

      </Routes>
    </AuthProvider>
  );
}
