import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";
import type { DailyPrice } from "../types";

interface PriceChartProps {
  prices: DailyPrice[];
}

interface ChartPoint {
  date: string;
  close: number;
  volume: number;
}

export default function PriceChart({ prices }: PriceChartProps) {
  if (!prices || prices.length === 0) {
    return <div className="empty-state small">No price data for this range yet.</div>;
  }

  const data: ChartPoint[] = prices.map((p) => ({
    date: p.date,
    close: Number(p.close),
    volume: Number(p.volume),
  }));

  return (
    <div className="chart-card">
      <ResponsiveContainer width="100%" height={320}>
        <ComposedChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
          <XAxis dataKey="date" tick={{ fontSize: 12 }} minTickGap={24} />
          <YAxis yAxisId="price" tick={{ fontSize: 12 }} domain={["auto", "auto"]} />
          <YAxis yAxisId="volume" orientation="right" tick={{ fontSize: 12 }} />
          <Tooltip />
          <Legend />
          <Bar yAxisId="volume" dataKey="volume" fill="var(--accent-muted)" name="Volume" radius={[3, 3, 0, 0]} />
          <Line
            yAxisId="price"
            type="monotone"
            dataKey="close"
            stroke="var(--accent)"
            strokeWidth={2}
            dot={false}
            name="Close"
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
