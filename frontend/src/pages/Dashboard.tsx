
import {
  Building2,
  Users,
  Activity,
  CheckCircle2,
  XCircle,
  Play,
  ArrowRight,
  Plus,
  RefreshCw,
  Clock,
  Newspaper,
  TrendingUp,
  Settings,
} from 'lucide-react';

import { useNavigate } from 'react-router-dom';
import { useEffect, useState } from 'react';

import PageHeader from '../components/common/PageHeader';
import SummaryCard from '../components/dashboard/SummaryCard';
import { dashboardApi, type AdminDashboard } from '../api/dashboard';


const ADMIN_SUMMARY = [
  ['Total Companies', Building2, 'text-accent-light'],
  ['Total Users', Users, 'text-blue-400'],
  ['Active Crawl Runs', Activity, 'text-yellow-400'],
  ['Successful Crawls', CheckCircle2, 'text-up'],
  ['Failed Crawls', XCircle, 'text-red-400'],
] as const;


// ---------------------------------------------------------
// RECENT CRAWL ACTIVITY
// ---------------------------------------------------------

// ---------------------------------------------------------
// STATUS BADGE
// ---------------------------------------------------------

function StatusBadge({
  status,
}: {
  status: string;
}) {
  const styles: Record<string, string> = {
    SUCCESS:
      'bg-green-500/10 text-green-400 border-green-500/20',

    RUNNING:
      'bg-blue-500/10 text-blue-400 border-blue-500/20',

    FAILED:
      'bg-red-500/10 text-red-400 border-red-500/20',

    PENDING:
      'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',

    CANCELLED:
      'bg-gray-500/10 text-gray-400 border-gray-500/20',
  };

  return (
    <span
      className={`
        inline-flex
        items-center
        px-2 py-1
        rounded-md
        border
        text-xs
        font-medium
        ${styles[status] || styles.CANCELLED}
      `}
    >
      {status}
    </span>
  );
}


// ---------------------------------------------------------
// ADMIN DASHBOARD
// ---------------------------------------------------------

export default function Dashboard() {
  const navigate = useNavigate();
  const [data, setData] = useState<AdminDashboard | null>(null);
  const [error, setError] = useState('');

  const load = () => dashboardApi.admin().then(setData).catch(() => setError('Unable to load the admin dashboard.'));

  useEffect(() => { load(); }, []);

  // Get logged-in user
  const storedUser = localStorage.getItem('user');

  let userName = 'Admin';

  if (storedUser) {
    try {
      const user = JSON.parse(storedUser);

      userName =
        user.first_name ||
        user.username ||
        'Admin';
    } catch {
      userName = 'Admin';
    }
  }


  return (
    <div className="space-y-6">
      {error && <div className="text-sm text-down">{error} <button onClick={load} className="underline">Retry</button></div>}

      {/* =====================================================
          PAGE HEADER
      ====================================================== */}

      <PageHeader
        title={`Good afternoon, ${userName}`}
        subtitle="Here's what's happening with your system."
        actions={
          <>
            <button
              onClick={load}
              className="btn-ghost flex items-center gap-2"
            >
              <RefreshCw size={14} />

              Refresh
            </button>

            <button
              onClick={() => navigate('/admin/crawl')}
              className="btn-primary flex items-center gap-2"
            >
              <Play size={14} />

              Trigger Crawl
            </button>
          </>
        }
      />


      {/* =====================================================
          SUMMARY CARDS
      ====================================================== */}

      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-5 gap-4">

        {ADMIN_SUMMARY.map(([title, icon, iconColor]) => {
          const summary = data?.summary;
          const values: Record<string, number> = {
            'Total Companies': summary?.total_companies ?? 0,
            'Total Users': summary?.total_users ?? 0,
            'Active Crawl Runs': summary?.active_crawl_runs ?? 0,
            'Successful Crawls': summary?.successful_crawl_runs ?? 0,
            'Failed Crawls': summary?.failed_crawl_runs ?? 0,
          };
          return (
          <SummaryCard
            key={title}
            title={title}
            value={data ? String(values[title]) : '—'}
            change="Live database total"
            icon={icon}
            iconColor={iconColor}
          />
          );
        })}

      </div>


      {/* =====================================================
          RECENT CRAWL ACTIVITY
      ====================================================== */}

      <div
        className="
          bg-bg-secondary
          border border-bg-border
          rounded-xl
          overflow-hidden
        "
      >

        {/* Header */}

        <div
          className="
            flex
            flex-col
            sm:flex-row
            sm:items-center
            sm:justify-between
            gap-3
            px-5
            py-4
            border-b
            border-bg-border
          "
        >

          <div>

            <h2 className="text-base font-semibold text-text-primary">
              Recent Crawl Activity
            </h2>

            <p className="text-sm text-text-secondary mt-1">
              Latest crawler activity across the system.
            </p>

          </div>


          <button
            onClick={() => navigate('/admin/crawl')}
            className="
              text-sm
              text-accent-light
              hover:underline
              flex
              items-center
              gap-1
            "
          >
            View all

            <ArrowRight size={14} />
          </button>

        </div>


        {/* Table */}

        <div className="overflow-x-auto">

          <table className="w-full text-sm">

            <thead>

              <tr className="border-b border-bg-border">

                <th className="text-left px-5 py-3 text-text-secondary font-medium">
                  Crawl Type
                </th>

                <th className="text-left px-5 py-3 text-text-secondary font-medium">
                  Target
                </th>

                <th className="text-left px-5 py-3 text-text-secondary font-medium">
                  Started
                </th>

                <th className="text-left px-5 py-3 text-text-secondary font-medium">
                  Duration
                </th>

                <th className="text-left px-5 py-3 text-text-secondary font-medium">
                  Status
                </th>

                <th className="text-right px-5 py-3 text-text-secondary font-medium">
                  Action
                </th>

              </tr>

            </thead>


            <tbody>

              {(data?.recent_crawls ?? []).map((crawl) => (

                <tr
                  key={crawl.id}
                  className="
                    border-b
                    border-bg-border
                    last:border-b-0
                    hover:bg-bg-primary/40
                    transition-colors
                  "
                >

                  <td className="px-5 py-4 text-text-primary">
                    {crawl.sources.join(', ')}
                  </td>

                  <td className="px-5 py-4">

                    <span className="font-medium text-text-primary">
                      {crawl.target}
                    </span>

                  </td>

                  <td className="px-5 py-4 text-text-secondary">
                    {crawl.started_at ? new Date(crawl.started_at).toLocaleString() : 'Pending'}
                  </td>

                  <td className="px-5 py-4 text-text-secondary">

                    <span className="flex items-center gap-1.5">

                      <Clock size={13} />

                      {crawl.completed_at ? `${Math.round((new Date(crawl.completed_at).getTime() - new Date(crawl.started_at ?? crawl.completed_at).getTime()) / 1000)}s` : '—'}

                    </span>

                  </td>

                  <td className="px-5 py-4">
                    <StatusBadge status={crawl.status.toUpperCase()} />
                  </td>

                  <td className="px-5 py-4 text-right">

                    <button
                      onClick={() =>
                        navigate(
                          `/admin/crawl-runs/${crawl.id}`
                        )
                      }
                      className="
                        text-accent-light
                        hover:underline
                        text-sm
                      "
                    >
                      View
                    </button>

                  </td>

                </tr>

              ))}

            </tbody>

          </table>

        </div>

      </div>


      {/* =====================================================
          WATCHLIST + QUICK ACTIONS
      ====================================================== */}

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">


        {/* ===================================================
            WATCHLIST
        ==================================================== */}

        <div
          className="
            xl:col-span-2
            bg-bg-secondary
            border border-bg-border
            rounded-xl
            overflow-hidden
          "
        >

          <div
            className="
              flex
              items-center
              justify-between
              px-5
              py-4
              border-b
              border-bg-border
            "
          >

            <div>

              <h2 className="text-base font-semibold text-text-primary">
                Watchlist Overview
              </h2>

              <p className="text-sm text-text-secondary mt-1">
                Companies currently monitored by the system.
              </p>

            </div>


            <button
              onClick={() => navigate('/admin/companies')}
              className="
                text-sm
                text-accent-light
                hover:underline
                flex
                items-center
                gap-1
              "
            >
              View all

              <ArrowRight size={14} />
            </button>

          </div>


          <div className="overflow-x-auto">

            <table className="w-full text-sm">

              <thead>

                <tr className="border-b border-bg-border">

                  <th className="text-left px-5 py-3 text-text-secondary font-medium">
                    Symbol
                  </th>

                  <th className="text-left px-5 py-3 text-text-secondary font-medium">
                    Company
                  </th>

                  <th className="text-left px-5 py-3 text-text-secondary font-medium">
                    Sector
                  </th>

                  <th className="text-left px-5 py-3 text-text-secondary font-medium">
                    Status
                  </th>

                  <th className="text-left px-5 py-3 text-text-secondary font-medium">
                    Last Crawl
                  </th>

                </tr>

              </thead>


              <tbody>

                {(data?.tracked_companies ?? []).map((company) => (

                  <tr
                    key={company.symbol}
                    className="
                      border-b
                      border-bg-border
                      last:border-b-0
                      hover:bg-bg-primary/40
                    "
                  >

                    <td className="px-5 py-4">

                      <span
                        className="
                          font-semibold
                          text-accent-light
                        "
                      >
                        {company.symbol}
                      </span>

                    </td>


                    <td className="px-5 py-4 text-text-primary">

                      {company.name}

                    </td>


                    <td className="px-5 py-4 text-text-secondary">

                      {company.sector}

                    </td>


                    <td className="px-5 py-4">

                      <span
                        className={`
                          inline-flex
                          items-center
                          px-2
                          py-1
                          rounded-md
                          text-xs
                          font-medium
                          border
                          ${
                            company.is_active
                              ? 'bg-green-500/10 text-green-400 border-green-500/20'
                              : 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20'
                          }
                        `}
                      >
                        {company.is_active ? 'Active' : 'Inactive'}
                      </span>

                    </td>


                    <td className="px-5 py-4 text-text-secondary">

                      {company.last_crawl ? new Date(company.last_crawl).toLocaleString() : 'No crawl yet'}

                    </td>

                  </tr>

                ))}

              </tbody>

            </table>

          </div>

        </div>


        {/* ===================================================
            QUICK ACTIONS
        ==================================================== */}

        <div
          className="
            bg-bg-secondary
            border border-bg-border
            rounded-xl
            p-5
          "
        >

          <div className="flex items-center gap-2 mb-1">

            <Settings
              size={17}
              className="text-accent-light"
            />

            <h2 className="text-base font-semibold text-text-primary">
              Quick Actions
            </h2>

          </div>


          <p className="text-sm text-text-secondary mb-5">
            Common administrative tasks.
          </p>


          <div className="space-y-3">


            {/* Add Company */}

            <button
              onClick={() =>
                navigate('/admin/companies')
              }
              className="
                w-full
                flex
                items-center
                justify-between
                p-3
                rounded-lg
                border
                border-bg-border
                bg-bg-primary
                hover:border-accent-light/40
                transition-colors
              "
            >

              <span className="flex items-center gap-3">

                <span
                  className="
                    w-8
                    h-8
                    rounded-lg
                    bg-accent/10
                    flex
                    items-center
                    justify-center
                  "
                >

                  <Plus
                    size={16}
                    className="text-accent-light"
                  />

                </span>

                <span className="text-sm font-medium text-text-primary">
                  Add Company
                </span>

              </span>


              <ArrowRight
                size={15}
                className="text-text-secondary"
              />

            </button>


            {/* Trigger Crawl */}

            <button
              onClick={() =>
                navigate('/admin/crawl-runs')
              }
              className="
                w-full
                flex
                items-center
                justify-between
                p-3
                rounded-lg
                border
                border-bg-border
                bg-bg-primary
                hover:border-accent-light/40
                transition-colors
              "
            >

              <span className="flex items-center gap-3">

                <span
                  className="
                    w-8
                    h-8
                    rounded-lg
                    bg-blue-500/10
                    flex
                    items-center
                    justify-center
                  "
                >

                  <Play
                    size={16}
                    className="text-blue-400"
                  />

                </span>

                <span className="text-sm font-medium text-text-primary">
                  Trigger Crawl
                </span>

              </span>


              <ArrowRight
                size={15}
                className="text-text-secondary"
              />

            </button>


            {/* Manage Users */}

            <button
              onClick={() =>
                navigate('/admin/users')
              }
              className="
                w-full
                flex
                items-center
                justify-between
                p-3
                rounded-lg
                border
                border-bg-border
                bg-bg-primary
                hover:border-accent-light/40
                transition-colors
              "
            >

              <span className="flex items-center gap-3">

                <span
                  className="
                    w-8
                    h-8
                    rounded-lg
                    bg-yellow-500/10
                    flex
                    items-center
                    justify-center
                  "
                >

                  <Users
                    size={16}
                    className="text-yellow-400"
                  />

                </span>

                <span className="text-sm font-medium text-text-primary">
                  Manage Users
                </span>

              </span>


              <ArrowRight
                size={15}
                className="text-text-secondary"
              />

            </button>


            {/* News */}

            <button
              onClick={() =>
                navigate('/admin/news')
              }
              className="
                w-full
                flex
                items-center
                justify-between
                p-3
                rounded-lg
                border
                border-bg-border
                bg-bg-primary
                hover:border-accent-light/40
                transition-colors
              "
            >

              <span className="flex items-center gap-3">

                <span
                  className="
                    w-8
                    h-8
                    rounded-lg
                    bg-purple-500/10
                    flex
                    items-center
                    justify-center
                  "
                >

                  <Newspaper
                    size={16}
                    className="text-purple-400"
                  />

                </span>

                <span className="text-sm font-medium text-text-primary">
                  Review News
                </span>

              </span>


              <ArrowRight
                size={15}
                className="text-text-secondary"
              />

            </button>

          </div>

        </div>

      </div>


      {/* =====================================================
          MARKET INFORMATION
      ====================================================== */}

      <div
        className="
          grid
          grid-cols-1
          md:grid-cols-3
          gap-4
        "
      >

        <div
          className="
            bg-bg-secondary
            border
            border-bg-border
            rounded-xl
            p-5
          "
        >

          <div className="flex items-center gap-3">

            <div
              className="
                w-10
                h-10
                rounded-lg
                bg-blue-500/10
                flex
                items-center
                justify-center
              "
            >

              <Newspaper
                size={18}
                className="text-blue-400"
              />

            </div>

            <div>

              <p className="text-sm text-text-secondary">
                News Articles
              </p>

              <p className="text-xl font-bold text-text-primary">
                {data?.summary.total_news ?? '—'}
              </p>

            </div>

          </div>

        </div>


        <div
          className="
            bg-bg-secondary
            border
            border-bg-border
            rounded-xl
            p-5
          "
        >

          <div className="flex items-center gap-3">

            <div
              className="
                w-10
                h-10
                rounded-lg
                bg-green-500/10
                flex
                items-center
                justify-center
              "
            >

              <TrendingUp
                size={18}
                className="text-up"
              />

            </div>

            <div>

              <p className="text-sm text-text-secondary">
                Market Activity
              </p>

              <p className="text-xl font-bold text-text-primary">
                +8.42%
              </p>

            </div>

          </div>

        </div>


        <div
          className="
            bg-bg-secondary
            border
            border-bg-border
            rounded-xl
            p-5
          "
        >

          <div className="flex items-center gap-3">

            <div
              className="
                w-10
                h-10
                rounded-lg
                bg-yellow-500/10
                flex
                items-center
                justify-center
              "
            >

              <Activity
                size={18}
                className="text-yellow-400"
              />

            </div>

            <div>

              <p className="text-sm text-text-secondary">
                System Status
              </p>

              <p className="text-xl font-bold text-green-400">
                Operational
              </p>

            </div>

          </div>

        </div>

      </div>

    </div>
  );
}

