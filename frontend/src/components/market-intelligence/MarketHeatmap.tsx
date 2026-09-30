import { useEffect, useState } from 'react';
import { marketIntelligenceApi, type MarketTile } from '../../api/marketIntelligence';

function numeric(value: number | string | null) {
  return value == null ? null : Number(value);
}

export default function MarketHeatmap() {
  const [group, setGroup] = useState<'sector' | 'company'>('sector');
  const [tiles, setTiles] = useState<MarketTile[]>([]);
  const [date, setDate] = useState<string | null>(null);
  const [updated, setUpdated] = useState<string | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    setError(false);
    marketIntelligenceApi.getHeatmap(group)
      .then((response) => { setTiles(response.tiles); setDate(response.date); setUpdated(response.computed_at); })
      .catch(() => setError(true));
  }, [group]);

  const maxTurnover = Math.max(1, ...tiles.map((tile) => numeric(tile.turnover) ?? 0));
  return (
    <section className="card space-y-3 p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-text-primary">Turnover heatmap</h2>
          <p className="text-[11px] text-text-muted">Tile size: turnover · color: daily change · tracked stocks</p>
        </div>
        <div className="flex gap-1">
          {(['sector', 'company'] as const).map((value) => (
            <button key={value} onClick={() => setGroup(value)}
              className={`rounded px-2 py-1 text-xs capitalize ${group === value ? 'bg-accent text-white' : 'text-text-secondary hover:bg-bg-elevated'}`}>
              {value}
            </button>
          ))}
        </div>
      </div>
      {error && <p className="text-xs text-text-secondary">Heatmap data is unavailable.</p>}
      {!error && tiles.length === 0 && <p className="text-xs text-text-secondary">No heatmap data for this session.</p>}
      <div className="flex min-h-28 flex-wrap gap-1.5">
        {tiles.map((tile) => {
          const change = numeric(tile.change_pct);
          const turnover = numeric(tile.turnover) ?? 0;
          const strength = change == null ? 0.08 : Math.min(0.32, 0.1 + Math.abs(change) / 50);
          const background = change == null ? 'rgba(148,163,184,0.08)'
            : change >= 0 ? `rgba(34,197,94,${strength})` : `rgba(239,68,68,${strength})`;
          const title = `${tile.sector}${change == null ? '' : ` · ${change.toFixed(2)}%`}`;
          return (
            <div key={tile.symbol ?? tile.sector} title={title}
              className="min-w-[100px] flex-1 rounded border border-bg-border p-2"
              style={{ flexGrow: Math.max(1, turnover / maxTurnover * 8), background }}>
              <p className="truncate text-xs font-semibold text-text-primary">{tile.symbol ?? tile.sector}</p>
              {tile.symbol && <p className="truncate text-[10px] text-text-muted">{tile.sector}</p>}
              <p className={`font-mono text-xs ${change == null ? 'text-text-muted' : change >= 0 ? 'text-up' : 'text-down'}`}>
                {change == null ? '—' : `${change > 0 ? '+' : ''}${change.toFixed(2)}%`}
                {(tile.possible_corporate_action || (tile.excluded_count ?? 0) > 0) ? ' *' : ''}
              </p>
              <p className="font-mono text-[10px] text-text-secondary">Rs {turnover.toLocaleString(undefined, { maximumFractionDigits: 0 })}</p>
            </div>
          );
        })}
      </div>
      {tiles.some((tile) => tile.possible_corporate_action || (tile.excluded_count ?? 0) > 0) &&
        <p className="text-[10px] text-text-muted">* Possible corporate-action sessions are excluded from change calculations.</p>}
      <p className="text-[10px] text-text-muted">{date ? `Session ${date}` : ''}{updated ? ` · computed ${new Date(updated).toLocaleString()}` : ''}</p>
    </section>
  );
}
