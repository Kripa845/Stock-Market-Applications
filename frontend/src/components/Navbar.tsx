import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function Navbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  if (!user) return null;

  const handleLogout = (): void => {
    logout();
    navigate("/login");
  };

  return (
    <header className="navbar">
      <div className="navbar-brand">
        <span className="navbar-dot" />
        NEPSE Watch
      </div>
      <nav className="navbar-links">
        <NavLink to="/" end>
          Dashboard
        </NavLink>
        {user.role === "admin" && <NavLink to="/admin">Admin</NavLink>}
      </nav>
      <div className="navbar-user">
        <span className={`role-badge role-${user.role}`}>{user.role}</span>
        <span className="navbar-username">{user.username}</span>
        <button className="btn btn-ghost" onClick={handleLogout}>
          Log out
        </button>
      </div>
    </header>
  );
}
