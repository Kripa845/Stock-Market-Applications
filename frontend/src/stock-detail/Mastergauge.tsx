// const CX = 100;
// const CY = 100;
// const R = 78;

// const pt = (v: number, r = R) => {
//   const a = Math.PI - (v / 100) * Math.PI;
//   return [CX + r * Math.cos(a), CY - r * Math.sin(a)];
// };

// const arc = (from: number, to: number) => {
//   const [x1, y1] = pt(from);
//   const [x2, y2] = pt(to);
//   return `M ${x1} ${y1} A ${R} ${R} 0 0 1 ${x2} ${y2}`;
// };

// const SEGMENTS = [
//   { from: 0, to: 25, color: "#ef4444" },
//   { from: 25, to: 50, color: "#f59e0b" },
//   { from: 50, to: 75, color: "#84cc16" },
//   { from: 75, to: 100, color: "#10b981" },
// ];

// export default function MasterGauge({ score, label }: { score: number; label: string }) {
//   const [nx, ny] = pt(score, R - 14);
//   return (
//     <div className="flex flex-col items-center">
//       <svg viewBox="0 0 200 120" className="w-full max-w-[190px]" role="img" aria-label={`Master score ${score} of 100`}>
//         {SEGMENTS.map((s) => (
//           <path key={s.from} d={arc(s.from + 0.8, s.to - 0.8)} stroke={s.color} strokeWidth={9} fill="none" />
//         ))}
//         {[0, 25, 50, 75, 100].map((t) => {
//           const [x, y] = pt(t, R + 12);
//           return (
//             <text key={t} x={x} y={y + 3} fontSize={7} fill="#64748b" textAnchor="middle">
//               {t}
//             </text>
//           );
//         })}
//         <line x1={CX} y1={CY} x2={nx} y2={ny} stroke="#e2e8f0" strokeWidth={2} strokeLinecap="round" />
//         <circle cx={CX} cy={CY} r={4} fill="#e2e8f0" />
//       </svg>
//       <div className="-mt-1 text-2xl font-extrabold tabular-nums text-white">{score.toFixed(1)}</div>
//       <div className="mt-0.5 text-center text-[9px] font-semibold text-amber-400">{label}</div>
//       <div className="mt-1 text-center text-[8px] text-slate-500">Mechanical 0–100 technical ranking.</div>
//       <a href="#methodology" className="text-[8px] text-emerald-400 hover:underline">
//         Methodology
//       </a>
//     </div>
//   );
// }
const CX = 100;
const CY = 100;
const R = 78;

const pt = (v: number, r = R) => {
  const a = Math.PI - (v / 100) * Math.PI;
  return [CX + r * Math.cos(a), CY - r * Math.sin(a)];
};

const arc = (from: number, to: number) => {
  const [x1, y1] = pt(from);
  const [x2, y2] = pt(to);
  return `M ${x1} ${y1} A ${R} ${R} 0 0 1 ${x2} ${y2}`;
};

const SEGMENTS = [
  { from: 0, to: 25, color: "#ef4444" },
  { from: 25, to: 50, color: "#f59e0b" },
  { from: 50, to: 75, color: "#84cc16" },
  { from: 75, to: 100, color: "#10b981" },
];

// CHANGED: label color follows the score instead of always amber
const toneFor = (v: number) =>
  v < 25 ? "text-red-400" : v < 50 ? "text-amber-400" : v < 75 ? "text-lime-400" : "text-emerald-400";

export default function MasterGauge({ score, label }: { score: number; label: string }) {
  // CHANGED: clamp so a bad value can't push the needle off the dial
  const s = Math.min(100, Math.max(0, score));
  const [nx, ny] = pt(s, R - 14);

  return (
    <div className="flex flex-col items-center">
      <svg viewBox="0 0 200 120" className="w-full max-w-[190px]" role="img" aria-label={`Master score ${score} of 100`}>
        {SEGMENTS.map((seg) => (
          <path key={seg.from} d={arc(seg.from + 0.8, seg.to - 0.8)} stroke={seg.color} strokeWidth={9} fill="none" />
        ))}
        {[0, 25, 50, 75, 100].map((t) => {
          const [x, y] = pt(t, R + 12);
          return (
            <text key={t} x={x} y={y + 3} fontSize={7} fill="#64748b" textAnchor="middle">
              {t}
            </text>
          );
        })}
        <line x1={CX} y1={CY} x2={nx} y2={ny} stroke="#e2e8f0" strokeWidth={2} strokeLinecap="round" />
        <circle cx={CX} cy={CY} r={4} fill="#e2e8f0" />
      </svg>
      <div className="-mt-1 text-2xl font-extrabold tabular-nums text-white">{score.toFixed(1)}</div>
      <div className={`mt-0.5 text-center text-[9px] font-semibold ${toneFor(score)}`}>{label}</div>
      <div className="mt-1 text-center text-[8px] text-slate-500">Mechanical 0–100 technical ranking.</div>
      <a href="#methodology" className="text-[8px] text-emerald-400 hover:underline">
        Methodology
      </a>
    </div>
  );
}