import type { RangeMetric } from "./types";

const pct = (v: number, min: number, max: number) =>
  Math.min(100, Math.max(0, ((v - min) / (max - min || 1)) * 100));

export default function RangeBars({ rows }: { rows: RangeMetric[] }) {
  return (
    <div className="space-y-3">
      {rows.map((r) => (
        <div key={r.label} className="grid grid-cols-[90px_1fr_52px] items-center gap-3">
          <div className="text-[10px] text-slate-300">{r.label}</div>
          <div className="relative h-5">
            <div className="absolute left-0 right-0 top-[7px] h-[3px] rounded bg-slate-700/70" />
            {/* average marker */}
            <div
              className="absolute top-[3px] h-[11px] w-px bg-slate-400"
              style={{ left: `${pct(r.avg, r.min, r.max)}%` }}
            />
            {/* value marker */}
            <div
              className="absolute top-[3px] h-[11px] w-[7px] -translate-x-1/2 rounded-full bg-emerald-400"
              style={{ left: `${pct(r.value, r.min, r.max)}%` }}
            />
            <div className="absolute bottom-0 left-0 text-[7px] text-slate-500">min {r.min}</div>
            <div
              className="absolute bottom-0 -translate-x-1/2 text-[7px] text-slate-500"
              style={{ left: `${pct(r.avg, r.min, r.max)}%` }}
            >
              avg {r.avg}
            </div>
            <div className="absolute bottom-0 right-0 text-[7px] text-slate-500">max {r.max}</div>
          </div>
          <div className="text-right text-[11px] font-bold tabular-nums text-white">{r.value}</div>
        </div>
      ))}
    </div>
  );
}