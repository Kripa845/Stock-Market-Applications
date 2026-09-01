import { useState } from "react";
import { triggerCrawlRun, listUsers } from "../api/admin";
import { isNotImplemented } from "../api/client";
import type { PaginatedResponse, User } from "../types";

type CrawlStatus = null | "triggering" | "not-implemented" | "error" | string;

interface UsersState {
  tried: boolean;
  notImplemented: boolean;
  users: User[];
}

function isPaginatedUsers(data: User[] | PaginatedResponse<User>): data is PaginatedResponse<User> {
  return !Array.isArray(data);
}

export default function AdminPage() {
  const [crawlStatus, setCrawlStatus] = useState<CrawlStatus>(null);
  const [usersState, setUsersState] = useState<UsersState>({ tried: false, notImplemented: false, users: [] });

  const handleTriggerCrawl = async (): Promise<void> => {
    setCrawlStatus("triggering");
    try {
      const run = await triggerCrawlRun({
        sources: ["merolagani", "sharesansar", "nepsealpha", "bizmandu"],
      });
      setCrawlStatus(`started (run #${run.id ?? "?"})`);
    } catch (err) {
      setCrawlStatus(isNotImplemented(err) ? "not-implemented" : "error");
    }
  };

  const handleLoadUsers = async (): Promise<void> => {
    try {
      const users = await listUsers();
      setUsersState({
        tried: true,
        notImplemented: false,
        users: isPaginatedUsers(users) ? users.results : users,
      });
    } catch (err) {
      setUsersState({ tried: true, notImplemented: isNotImplemented(err), users: [] });
    }
  };

  return (
    <div className="page">
      <div className="page-header">
        <h1>Admin</h1>
        <p className="page-subtitle">Manage the watchlist, trigger crawls, and manage users.</p>
      </div>

      <section className="card">
        <div className="card-header">
          <h2>Crawl runs</h2>
        </div>
        <p className="card-body-text">
          Triggers <code>POST /api/admin/crawl-runs</code>, which kicks off the Celery tasks
          already defined in <code>apps/crawler_runs/tasks.py</code>.
        </p>
        <button className="btn btn-primary" onClick={handleTriggerCrawl} disabled={crawlStatus === "triggering"}>
          {crawlStatus === "triggering" ? "Triggering…" : "Trigger crawl run"}
        </button>
        {crawlStatus === "not-implemented" && (
          <p className="form-hint">
            This endpoint isn't wired up yet — <code>apps/crawler_runs</code> has no
            <code>urls.py</code> in this backend snapshot. The Celery tasks exist and are ready to
            be called from a view.
          </p>
        )}
        {crawlStatus === "error" && <p className="form-error">Something went wrong triggering the crawl.</p>}
        {crawlStatus && !["triggering", "not-implemented", "error"].includes(crawlStatus) && (
          <p className="form-hint">Crawl run {crawlStatus}.</p>
        )}
      </section>

      <section className="card">
        <div className="card-header">
          <h2>Users & roles</h2>
        </div>
        <button className="btn btn-ghost" onClick={handleLoadUsers}>
          Load users
        </button>
        {usersState.tried && usersState.notImplemented && (
          <p className="form-hint">
            <code>GET /api/admin/users</code> isn't wired up yet on the backend.
          </p>
        )}
        {usersState.users.length > 0 && (
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Username</th>
                  <th>Email</th>
                  <th>Role</th>
                </tr>
              </thead>
              <tbody>
                {usersState.users.map((u) => (
                  <tr key={u.id}>
                    <td>{u.username}</td>
                    <td>{u.email}</td>
                    <td>{u.role}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
