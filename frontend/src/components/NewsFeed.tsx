import { useEffect, useState } from "react";
import { listNewsForCompany, recategorizeArticle } from "../api/news";
import { isNotImplemented } from "../api/client";
import RoleGate from "./RoleGate";
import type { NewsArticle, PaginatedResponse } from "../types";

interface NewsFeedProps {
  companyId: number | string;
}

interface NewsState {
  loading: boolean;
  notImplemented: boolean;
  error: unknown;
  items: NewsArticle[];
}

function isPaginated(data: NewsArticle[] | PaginatedResponse<NewsArticle>): data is PaginatedResponse<NewsArticle> {
  return !Array.isArray(data);
}

export default function NewsFeed({ companyId }: NewsFeedProps) {
  const [state, setState] = useState<NewsState>({
    loading: true,
    notImplemented: false,
    error: null,
    items: [],
  });

  useEffect(() => {
    let cancelled = false;
    setState({ loading: true, notImplemented: false, error: null, items: [] });

    listNewsForCompany(companyId)
      .then((data) => {
        if (cancelled) return;
        const items = isPaginated(data) ? data.results : data;
        setState({ loading: false, notImplemented: false, error: null, items });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        if (isNotImplemented(err)) {
          setState({ loading: false, notImplemented: true, error: null, items: [] });
        } else {
          setState({ loading: false, notImplemented: false, error: err, items: [] });
        }
      });

    return () => {
      cancelled = true;
    };
  }, [companyId]);

  if (state.loading) return <div className="empty-state small">Loading news…</div>;

  if (state.notImplemented) {
    return (
      <div className="empty-state small">
        The categorized news feed API (<code>GET /api/news/?company_id=</code>) isn't wired up on
        the backend in this snapshot yet — this panel will populate automatically once it is.
      </div>
    );
  }

  if (state.error) {
    return <div className="empty-state small error">Couldn't load news right now.</div>;
  }

  if (state.items.length === 0) {
    return <div className="empty-state small">No categorized news for this company yet.</div>;
  }

  const handleCorrect = async (articleId: number): Promise<void> => {
    const companyIdInput = prompt("Correct company_id for this article:");
    if (!companyIdInput) return;
    try {
      await recategorizeArticle(articleId, { company_id: companyIdInput, action: "update" });
      alert("Correction submitted.");
    } catch {
      alert("Couldn't submit correction (endpoint may not be live yet).");
    }
  };

  return (
    <ul className="news-list">
      {state.items.map((item) => (
        <li key={item.id} className="news-item">
          <div className="news-headline">{item.headline}</div>
          <div className="news-meta">
            <span>{item.source}</span>
            <span>{item.published_at}</span>
            {typeof item.confidence === "number" && (
              <span className="badge">{Math.round(item.confidence * 100)}% confidence</span>
            )}
          </div>
          <RoleGate roles={["admin", "analyst"]}>
            <button className="btn btn-ghost btn-xs" onClick={() => handleCorrect(item.id)}>
              Correct tag
            </button>
          </RoleGate>
        </li>
      ))}
    </ul>
  );
}
