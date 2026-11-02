// StockDetailRoute.tsx
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import StockDetailPage from "./StockDetailsPage";
import type { StockDetail } from "./types";

export default function StockDetailRoute() {
  const { symbol } = useParams();
  const [stock, setStock] = useState<StockDetail | null>(null);

  useEffect(() => {
    fetch(`/api/stocks/${symbol}/detail/`)
      .then((r) => r.json())
      .then(setStock);
  }, [symbol]);

  if (!stock) return <div className="p-6 text-slate-400">Loading…</div>;
  return <StockDetailPage stock={stock} />;
}