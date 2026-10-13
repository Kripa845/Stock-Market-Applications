import { useMemo } from 'react';
import clsx from 'clsx';
import type { VolumeAnomaly } from '../../api/analysis';

interface VolumeAnomalyChartProps {
  data: VolumeAnomaly[];
  loading?: boolean;
  error?: string;
}

const RECENT_ANOMALY_LIMIT = 6;

const formatVolume = (volume: number | null) =>
  volume === null ? '—' : new Intl.NumberFormat('en', { notation: 'compact', maximumFractionDigits: 1 }).format(volume);

const formatRvol = (rvol: number | null) => (rvol === null ? '—' : `${rvol.toFixed(2)}×`);

function Tile({ label, value, className }: { label: string; value: string; className?: string }) {
  return (
    <div className="bg-bg-elevated rounded-lg p-3">
      <p className="text-[10px] text-text-muted uppercase tracking-wider mb-1">{label}</p>
      <p className={clsx('text-sm font-semibold font-mono', className ?? 'text-text-primary')}>{value}</p>
    </div>
  );
}

export default function VolumeAnomalyChart({ data, loading = false, error }: VolumeAnomalyChartProps) {
  const sorted = useMemo(() => [...data].sort((a, b) => b.date.localeCompare(a.date)), [data]);
  const anomalies = useMemo(() => sorted.filter(r => r.anomaly_flag === 'Anomaly'), [sorted]);
  const latest = sorted[0];
  const latestIsAnomaly = latest?.anomaly_flag === 'Anomaly';

  return (
    <section className="card space-y-3" aria-label="Volume anomaly analysis">
      <h3
        className="text-sm font-semibold text-text-primary"
        title="Baseline = SMA of prior 20 sessions (current day excluded). Anomaly when volume ≥ 2.5× baseline."
      >
        Volume Anomalies
      </h3>

      {loading ? (
        <p className="py-4 text-center text-xs text-text-muted">Loading volume history…</p>
      ) : error ? (
        <p className="py-4 text-center text-xs text-down">{error}</p>
      ) : !latest ? (
        <p className="py-4 text-center text-xs text-text-muted">No volume history available.</p>
      ) : (
        <>
          <div className="grid grid-cols-2 xl:grid-cols-4 gap-3">
            <Tile
              label={`Latest RVOL · ${latest.date}`}
              value={latestIsAnomaly ? `⚡ ${formatRvol(latest.rvol)}` : formatRvol(latest.rvol)}
              className={latestIsAnomaly ? 'text-down' : latest.anomaly_flag === 'Normal' ? 'text-up' : 'text-text-muted'}
            />
            <Tile label="Latest Volume" value={formatVolume(latest.volume)} />
            <Tile label="20D Avg Volume" value={formatVolume(latest.average_volume_20d)} />
            <Tile
              label="Anomaly Days"
              value={`${anomalies.length} / ${sorted.length}`}
              className={anomalies.length > 0 ? 'text-down' : 'text-up'}
            />
          </div>

          {anomalies.length > 0 && (
            <div>
              <p className="text-[10px] text-text-muted uppercase tracking-wider mb-2">Recent anomaly days</p>
              <div className="grid grid-cols-2 sm:grid-cols-3 xl:grid-cols-6 gap-2">
                {anomalies.slice(0, RECENT_ANOMALY_LIMIT).map(row => (
                  <div key={row.date} className="bg-bg-elevated rounded-lg px-3 py-2 border-l-2 border-down">
                    <p className="text-[11px] font-mono text-text-secondary">{row.date}</p>
                    <p className="text-sm font-semibold font-mono text-down">{formatRvol(row.rvol)}</p>
                    <p className="text-[10px] text-text-muted">Vol {formatVolume(row.volume)}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </section>
  );
}
