import { useMemo } from 'react';
import type { VolumeAnomaly } from '../../api/analysis';

interface VolumeAnomalyChartProps {
  data: VolumeAnomaly[];
  loading?: boolean;
  error?: string;
}

const formatVolume = (volume: number | null) =>
  volume === null ? '—' : new Intl.NumberFormat().format(Math.round(volume));

const flagStyle: Record<NonNullable<VolumeAnomaly['anomaly_flag']>, string> = {
  Normal: 'text-text-secondary',
  Anomaly: 'text-down font-semibold',
};

export default function VolumeAnomalyChart({ data, loading = false, error }: VolumeAnomalyChartProps) {
  const rows = useMemo(() => [...data].sort((a, b) => b.date.localeCompare(a.date)), [data]);

  return (
    <section className="card space-y-4" aria-label="Volume anomaly analysis">
      <div>
        <h3 className="text-sm font-semibold text-text-primary">Volume Anomaly Detection</h3>
        <p className="mt-1 text-xs text-text-muted">
          Baseline = SMA of the prior 20 trading sessions (current day excluded). Flag an anomaly when current volume is at least 2.5× the baseline. Incomplete baselines are unclassified.
        </p>
      </div>

      {loading ? (
        <p className="py-8 text-center text-xs text-text-muted">Loading volume history…</p>
      ) : error ? (
        <p className="py-8 text-center text-xs text-down">{error}</p>
      ) : rows.length === 0 ? (
        <p className="py-8 text-center text-xs text-text-muted">No volume history available for this company.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-bg-border text-left text-text-muted">
                <th className="py-2 pr-4 font-medium">Date</th>
                <th className="py-2 pr-4 text-right font-medium">Volume</th>
                <th className="py-2 pr-4 text-right font-medium">20-day Average Volume</th>
                <th className="py-2 pr-4 text-right font-medium">RVOL</th>
                <th className="py-2 text-right font-medium">Anomaly Flag</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(row => (
                <tr key={row.date} className="border-b border-bg-border/60 last:border-0">
                  <td className="py-2 pr-4 font-mono text-text-primary">{row.date}</td>
                  <td className="py-2 pr-4 text-right font-mono">{formatVolume(row.volume)}</td>
                  <td className="py-2 pr-4 text-right font-mono">{formatVolume(row.average_volume_20d)}</td>
                  <td className="py-2 pr-4 text-right font-mono">{row.rvol === null ? '—' : `${row.rvol.toFixed(2)}×`}</td>
                  <td className={`py-2 text-right ${row.anomaly_flag ? flagStyle[row.anomaly_flag] : 'text-text-muted'}`}>
                    {row.anomaly_flag ?? 'Insufficient history'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
