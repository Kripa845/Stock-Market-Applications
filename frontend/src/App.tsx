import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
} from 'react-router-dom';

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
// import CrawlRunsPage from './pages/admin/CrawlRunsPage';
// import CrawlRunDetailPage from './pages/admin/CrawlRunDetailPage';
import AnalystsPage from './pages/AnalystDashboard';
// import SettingsPage from './pages/admin/SettingsPage';

// Existing pages
import AdminNewsPage from './pages/News';

// =========================
// ANALYST / VIEWER
// =========================
import AnalystDashboard from './pages/AnalystDashboard';
import ViewerDashboard from './pages/ViewerDashboard';

import NotFound from './pages/NotFound';


// ======================================================
// GET CURRENT USER
// ======================================================
function getUser() {
  const value = localStorage.getItem('user');

  if (!value) {
    return null;
  }

  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}


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
// ROLE ROUTE
// ======================================================
function RoleRoute({
  role,
  children,
}: {
  role: string;
  children: React.ReactNode;
}) {
  const user = getUser();

  // No logged-in user
  if (!user) {
    return <Navigate to="/login" replace />;
  }

  // User does not have permission for this route
  if (user.role !== role) {
    if (user.role === 'admin') {
      return <Navigate to="/admin" replace />;
    }

    if (user.role === 'analyst') {
      return <Navigate to="/analyst" replace />;
    }

    if (user.role === 'viewer') {
      return <Navigate to="/viewer" replace />;
    }

    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}


// ======================================================
// APPLICATION
// ======================================================
export default function App() {
  return (
    <BrowserRouter>
      <Routes>

        {/* =================================================
            PUBLIC ROUTES
            ================================================= */}

        {/* Landing page */}
        <Route
          path="/"
          element={<LandingPage />}
        />

        {/* Login */}
        <Route
          path="/login"
          element={<LoginPage />}
        />

        {/* Registration */}
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
              <RoleRoute role="admin">
                <Layout />
              </RoleRoute>
            </PrivateRoute>
          }
        >

          {/* -----------------------------------------------
              ADMIN DASHBOARD
              URL: /admin
              ----------------------------------------------- */}
          <Route
            path="/admin"
            element={<AdminDashboard />}
          />


          {/* -----------------------------------------------
              COMPANIES
              URL: /admin/companies
              ----------------------------------------------- */}
          <Route
            path="/admin/companies"
            element={<CompaniesPage />}
          />

          <Route
            path="/admin/watchlist"
            element={<WatchlistPage />}
          />


          {/* -----------------------------------------------
              CRAWL RUNS
              URL: /admin/crawl-runs
              ----------------------------------------------- */}
          <Route path="/admin/crawl" element={<CrawlerStatusPage />} />
          <Route path="/admin/crawl-runs" element={<CrawlerStatusPage />} />


          {/* -----------------------------------------------
              CRAWL RUN DETAIL
              URL: /admin/crawl-runs/:id
              ----------------------------------------------- */}
          {/* <Route
            path="/admin/crawl-runs/:id"
            element={<CrawlRunDetailPage />}
          /> */}


          {/* -----------------------------------------------
              USERS
              URL: /admin/users
              ----------------------------------------------- */}
          <Route
            path="/admin/users"
            element={<UserManagementPage />}
          />


          {/* -----------------------------------------------
              ANALYSTS
              URL: /admin/analysts
              ----------------------------------------------- */}
          <Route
            path="/admin/analysts"
            element={<AnalystsPage />}
          />


          {/* -----------------------------------------------
              NEWS REVIEW
              URL: /admin/news
              ----------------------------------------------- */}
          <Route
            path="/admin/news"
            element={<AdminNewsPage />}
          />
          <Route
            path="/admin/news/:id"
            element={<NewsDetail />}
          />
          <Route
            path="/news/:id"
            element={<NewsDetail />}
          />


          {/* -----------------------------------------------
              SETTINGS
              URL: /admin/settings
              ----------------------------------------------- */}
          {/* <Route
            path="/admin/settings"
            element={<SettingsPage />}
          /> */}

          {/* -----------------------------------------------
              ROLES & PERMISSIONS
              URL: /admin/roles-permissions
              ----------------------------------------------- */}
          <Route
            path="/admin/roles-permissions"
            element={<RolesPermissionsPage />}
          />

        </Route>


        {/* =================================================
            ANALYST ROUTES
            ================================================= */}

        <Route
          element={
            <PrivateRoute>
              <RoleRoute role="analyst">
                <Layout />
              </RoleRoute>
            </PrivateRoute>
          }
        >

          <Route
            path="/analyst"
            element={<AnalystDashboard />}
          />
          <Route path="/analyst/market" element={<MarketPage />} />
          <Route path="/analyst/stocks" element={<MarketPage />} />
          <Route path="/analyst/stocks/:symbol" element={<StockDetail />} />
          <Route path="/stocks/:symbol" element={<StockDetail />} />
          <Route path="/analyst/news" element={<NewsPage />} />
          <Route path="/analyst/news-review" element={<NewsPage />} />
          <Route path="/analyst/news/:id" element={<NewsDetail />} />
          <Route path="/news/:id" element={<NewsDetail />} />
          <Route path="/analyst/trading" element={<TradingPage />} />

        </Route>


        {/* =================================================
            VIEWER ROUTES
            ================================================= */}

        <Route
          element={
            <PrivateRoute>
              <RoleRoute role="viewer">
                <Layout />
              </RoleRoute>
            </PrivateRoute>
          }
        >

          <Route
            path="/viewer"
            element={<ViewerDashboard />}
          />
          <Route path="/viewer/market" element={<WatchlistPage />} />
          <Route path="/viewer/stocks" element={<MarketPage />} />
          <Route path="/viewer/stocks/:symbol" element={<StockDetail />} />
          <Route path="/stocks/:symbol" element={<StockDetail />} />
          <Route path="/viewer/news" element={<NewsPage />} />
          <Route path="/viewer/news/:id" element={<NewsDetail />} />
          <Route path="/news/:id" element={<NewsDetail />} />
          <Route path="/viewer/trading" element={<TradingPage />} />

        </Route>



        {/* =================================================
            404
            ================================================= */}
        <Route
          path="*"
          element={<NotFound />}
        />

      </Routes>
    </BrowserRouter>
  );
}