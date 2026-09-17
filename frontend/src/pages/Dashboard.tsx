import RoleDashboard from '../components/dashboard/RoleDashboard';

/**
 * Single unified dashboard for all roles.
 * RoleDashboard reads the user's actual permissions from AuthContext and
 * renders only the widgets the user is permitted to see.
 */
export default function Dashboard() {
  return <RoleDashboard />;
}
