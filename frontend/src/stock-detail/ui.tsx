import type { ReactNode } from "react";
import type { Metric, Tone } from "./types";

export const toneText: Record<Tone, string> = {
  pos: "text-emerald-400",
  neg: "text-red-400",
  neutral: "text-slate-100",
};

export function Panel({
  title,
  right,
  className = "",
  children,
}: {
  title?: string;
  right?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section className={`rounded-md border border-[#16233a] bg-[#0a1220] p-3 ${className}`}>
      {(title || right) && (
        <header className="mb-2 flex items-center justify-between">
          <h2 className="text-[11px] font-bold text-slate-100">{title}</h2>
          <div className="text-[9px] text-slate-500">{right}</div>
        </header>
      )}
      {children}
    </section>
  );
}

export function Tile({ label, value, tone = "neutral", wide }: Metric) {
  return (
    <div
      className={`rounded border border-[#16233a] bg-[#0c1626] px-2.5 py-2 ${
        wide ? "col-span-2" : ""
      }`}
    >
      <div className="text-[8px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`mt-1 text-[11px] font-bold tabular-nums ${toneText[tone]}`}>{value}</div>
    </div>
  );
}