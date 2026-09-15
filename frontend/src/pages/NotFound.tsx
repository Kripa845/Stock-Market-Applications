import { useNavigate } from "react-router-dom";

export default function NotFound() {
  const navigate = useNavigate();

  const path = window.location.pathname;

  let dashboardPath = "/";

  if (path.startsWith("/admin")) {
    dashboardPath = "/admin";
  } else if (path.startsWith("/analyst")) {
    dashboardPath = "/analyst";
  } else if (path.startsWith("/viewer")) {
    dashboardPath = "/viewer";
  }

  return (
    <div className="flex h-full min-h-[calc(100vh-64px)] w-full items-center justify-center">
      <div className="flex flex-col items-center justify-center gap-4 text-center">
        <p className="font-mono text-7xl font-bold text-text-muted">
          404
        </p>

        <h1 className="text-2xl font-semibold text-text-primary">
          Page Not Found
        </h1>

        <p className="text-text-secondary">
          The page you are looking for does not exist.
        </p>

        <button
          onClick={() => navigate(dashboardPath)}
          className="btn-primary mt-2"
        >
          Go to Dashboard
        </button>
      </div>
    </div>
  );
}