import type { FinQuarter, FinRow } from "./types";

const cellClass = {
  better: "bg-emerald-950/70 text-slate-100",
  worse: "bg-red-900/50 text-slate-100",
  flat: "bg-emerald-950/40 text-slate-100",
};

export default function KeyFinancials({ quarters, rows }: { quarters: FinQuarter[]; rows: FinRow[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[900px] border-separate border-spacing-[1px] text-[10px]">
        <thead>
          <tr>
            <th className="w-[200px] pb-1 text-left text-[8px] font-normal uppercase text-slate-500">Particulars</th>
            {quarters.map((q) => (
              <th key={q.q + q.fy} className="pb-1 text-right text-[8px] font-normal">
                <div className={q.latest ? "text-emerald-400" : "text-slate-400"}>{q.q}</div>
                <div className="text-slate-500">{q.fy}</div>
                {q.latest && <div className="text-[7px] text-emerald-500">latest</div>}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label}>
              <td className="py-1 pr-2 text-slate-300">{row.label}</td>
              {quarters.map((_, i) => {
                const cell = row.cells[i];
                return cell ? (
                  <td key={i} className={`px-2 py-1 text-right font-medium tabular-nums ${cellClass[cell.tone]}`}>
                    {cell.v}
                  </td>
                ) : (
                  <td key={i} />
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}