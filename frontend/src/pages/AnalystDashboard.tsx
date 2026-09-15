
import React from 'react';
import {
  Activity,
  LogOut,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';

const AnalystDashboard: React.FC = () => {
  const navigate = useNavigate();

  const user = JSON.parse(
    localStorage.getItem('user') || '{}'
  );

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user');

    navigate('/login', {
      replace: true,
    });
  };

  return (
    <div className="min-h-screen bg-bg-primary">

      {/* Navbar */}
      <nav className="h-16 border-b
        border-bg-border
        flex items-center justify-between
        px-6">

        <div className="flex items-center gap-3">

          <div className="w-9 h-9 rounded-lg
            bg-accent flex items-center justify-center">
            <Activity size={18} />
          </div>

          <span className="font-bold
            text-text-primary">
            StockScope
          </span>

        </div>

        <div className="flex items-center gap-5">

          <span className="text-sm
            text-text-secondary">
            Analyst
          </span>

          <span className="text-sm
            text-text-primary">
            {user.first_name ||
              user.username ||
              'Analyst'}
          </span>

          <button
            onClick={handleLogout}
            className="text-text-secondary
              hover:text-text-primary"
            title="Logout"
          >
            <LogOut size={18} />
          </button>

        </div>

      </nav>

      {/* Content */}
      <main className="flex items-center
        justify-center min-h-[calc(100vh-4rem)]">

        <div className="text-center">

          <h1 className="text-2xl font-bold
            text-text-primary">
            Analyst Dashboard
          </h1>

          <p className="mt-2
            text-text-secondary">
            Analyst features will be added here.
          </p>

        </div>

      </main>

    </div>
  );
};

export default AnalystDashboard;

