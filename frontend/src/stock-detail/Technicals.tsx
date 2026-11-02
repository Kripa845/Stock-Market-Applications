import type { PivotLevel, TechRow } from "./types";

const signalClass = {
  Bullish: "text-emerald-400",
  Bearish: "text-red-400",
  Neutral: "text-slate-200",
};

export default function Technicals({ rows, pivots }: { rows: TechRow[]; pivots: PivotLevel[] }) {
  return (
    <>
      <table className="w-full text-[10px]">
        <tbody>
          {rows.map((r) => (
            <tr key={r.name} className="border-b border-[#16233a]/70 last:border-0">
              <td className="py-1.5 text-slate-300">{r.name}</td>
              <td className="py-1.5 text-center font-bold tabular-nums text-white">{r.value}</td>
              <td className={`py-1.5 text-right font-bold ${signalClass[r.signal]}`}>{r.signal}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="mt-4 text-[8px] uppercase tracking-wide text-slate-500">Pivot levels (classic)</div>
      <div className="mt-1.5 grid grid-cols-7 gap-1.5">
        {pivots.map((p) => (
          <div
            key={p.label}
            className={`rounded px-2 py-1.5 text-center ${
              p.active ? "border border-emerald-500/60 bg-emerald-950/60" : "bg-[#101c30]"
            }`}
          >
            <div className={`text-[8px] font-bold ${p.active ? "text-emerald-400" : "text-slate-400"}`}>
              {p.label}
            </div>
            <div className="text-[9px] tabular-nums text-slate-200">{p.value}</div>
          </div>
        ))}
      </div>
    </>
  );
}