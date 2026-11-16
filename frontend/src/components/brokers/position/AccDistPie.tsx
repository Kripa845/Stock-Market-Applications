


// import {
//   Cell,
//   Pie,
//   PieChart,
//   ResponsiveContainer,
//   Tooltip,
// } from 'recharts';

// import { formatCount } from '../../market/format';
// import {
//   seriesColor,
//   otherSeriesColor,
// } from './format';
// import { useState } from 'react';
// export interface PieSlice {
//   symbol: string;
//   slot: number;
//   value: number;
// }

// interface AccDistPieProps {
//   slices: PieSlice[];
//   side: 'bought' | 'sold';
// }

// const TOP_COMPANIES = 8;

// export default function AccDistPie({
//   slices,
//   side,
// }: AccDistPieProps) {
//   // Ignore invalid and non-positive values.
//   const validSlices = slices
//     .filter(
//       (slice) =>
//         Number.isFinite(slice.value) &&
//         slice.value > 0
//     )
//     .sort((a, b) => b.value - a.value);

//   const total = validSlices.reduce(
//     (sum, slice) => sum + slice.value,
//     0
//   );

//   if (!total) {
//     return (
//       <p className="py-16 text-center text-sm text-text-muted">
//         The broker {side} nothing in the shown stocks in this range.
//       </p>
//     );
//   }

//   const topSlices = validSlices.slice(0, TOP_COMPANIES);
//   const remainingSlices = validSlices.slice(TOP_COMPANIES);

//   const othersValue = remainingSlices.reduce(
//     (sum, slice) => sum + slice.value,
//     0
//   );

//   const donutSlices = [
//     ...topSlices,
//     ...(othersValue > 0
//       ? [
//           {
//             symbol: 'Others',
//             slot: -1,
//             value: othersValue,
//           },
//         ]
//       : []),
//   ];

//   const isOthers = (symbol: string) => symbol === 'Others';

//   const getColor = (slice: PieSlice) =>
//     isOthers(slice.symbol)
//       ? otherSeriesColor()
//       : seriesColor(slice.slot);

//   return (
//     <div className="flex flex-col items-center gap-6 py-4 xl:flex-row xl:items-start xl:justify-center xl:gap-8">

//       {/* DONUT CHART */}
//       <div className="relative h-[280px] w-[280px] shrink-0">

//         <ResponsiveContainer width="100%" height="100%">
//           <PieChart>
//             <Pie
//               data={donutSlices}
//               dataKey="value"
//               nameKey="symbol"
//               innerRadius={78}
//               outerRadius={128}
//               paddingAngle={2}
//               stroke="var(--trading-panel)"
//               strokeWidth={2}
//               isAnimationActive={false}
//             >
//               {donutSlices.map((slice) => (
//                 <Cell
//                   key={slice.symbol}
//                   fill={getColor(slice)}
//                 />
//               ))}
//             </Pie>

//             <Tooltip
//               formatter={(value, name) => {
//                 const quantity = Number(value);
//                 const percentage = (quantity / total) * 100;

//                 return [
//                   `${formatCount(quantity)} (${percentage.toFixed(1)}%)`,
//                   String(name),
//                 ];
//               }}
//               contentStyle={{
//                 background: 'var(--trading-panel)',
//                 border: '1px solid var(--trading-grid)',
//                 borderRadius: 8,
//                 fontSize: 12,
//               }}
//             />
//           </PieChart>
//         </ResponsiveContainer>

//         {/* CENTER INFORMATION */}
//         <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
//           <span className="text-[11px] text-text-muted">
//             {side === 'bought' ? 'Total bought' : 'Total sold'}
//           </span>

//           <span className="font-mono text-xl font-bold text-text-primary">
//             {formatCount(total)}
//           </span>

//           <span className="mt-1 text-xs text-text-muted">
//             {validSlices.length} companies
//           </span>
//         </div>
//       </div>

//       {/* COMPANY BREAKDOWN */}
//       <div className="w-full min-w-0 flex-1 xl:max-w-[650px]">

//         <div className="mb-3 flex items-center justify-between gap-2">
//           <h3 className="text-sm font-semibold text-text-primary">
//             Company breakdown
//           </h3>

//           <span className="text-xs text-text-muted">
//             {side === 'bought' ? 'Buying share' : 'Selling share'}
//           </span>
//         </div>

//         {/* RESPONSIVE MULTI-COLUMN COMPANY GRID */}
//         <div className="grid grid-cols-1 gap-x-4 gap-y-2 sm:grid-cols-2 2xl:grid-cols-3">

//           {validSlices.map((slice, index) => {
//             const percentage = (slice.value / total) * 100;

//             return (
//               <div
//                 key={slice.symbol}
//                 className="min-w-0 rounded-lg border border-bg-border px-3 py-2"
//               >
//                 {/* COMPANY NAME AND RANK */}
//                 <div className="mb-2 flex min-w-0 items-center gap-2">

//                   <span className="shrink-0 text-[11px] text-text-muted">
//                     {index + 1}.
//                   </span>

                  
//                   <CompanyLogo
//                     symbol={slice.symbol}
//                     logoUrl={slice.logoUrl}
//                            />

// <span
//   className="h-2.5 w-2.5 shrink-0 rounded-sm"
//   style={{
//     background: seriesColor(slice.slot),
//   }}
// />

// <span className="min-w-0 flex-1 truncate text-xs font-semibold text-text-primary">
//   {slice.symbol}
// </span>
//                 </div>

//                 {/* QUANTITY AND PERCENTAGE */}
//                 <div className="mb-2 flex items-center justify-between gap-2">
//                   <span className="truncate font-mono text-xs text-text-secondary">
//                     {formatCount(slice.value)}
//                   </span>

//                   <span className="shrink-0 font-mono text-xs font-semibold text-text-primary">
//                     {percentage.toFixed(1)}%
//                   </span>
//                 </div>

//                 {/* SHARE BAR */}
//                 <div className="h-1.5 overflow-hidden rounded-full bg-bg-elevated">
//                   <div
//                     className="h-full rounded-full transition-all"
//                     style={{
//                       width: `${percentage}%`,
//                       background: seriesColor(slice.slot),
//                     }}
//                   />
//                 </div>
//               </div>
//             );
//           })}
//         </div>

//         {remainingSlices.length > 0 && (
//           <p className="mt-3 text-xs text-text-muted">
//             The donut groups {remainingSlices.length} smaller companies
//             into Others. All companies are displayed in the breakdown.
//           </p>
//         )}
//       </div>
//     </div>
//   );
// }
// export interface PieSlice {
//   symbol: string;
//   slot: number;
//   value: number;
//   logoUrl?: string | null;
// }
// function CompanyLogo({
//   symbol,
//   logoUrl,
// }: {
//   symbol: string;
//   logoUrl?: string | null;
// }) {
//   const [failed, setFailed] = useState(false);

//   const initials = symbol === 'Others'
//     ? 'OT'
//     : symbol.slice(0, 2).toUpperCase();

//   if (!logoUrl || failed) {
//     return (
//       <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-bg-border bg-bg-elevated text-[10px] font-bold text-text-secondary">
//         {initials}
//       </span>
//     );
//   }

//   return (
//     <img
//       src={logoUrl}
//       alt={`${symbol} logo`}
//       loading="lazy"
//       onError={() => setFailed(true)}
//       className="h-7 w-7 shrink-0 rounded-full border border-bg-border bg-white object-contain p-0.5"
//     />
//   );
// }

import { useState } from 'react';
import {
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';

import { formatCount } from '../../market/format';
import {
  seriesColor,
  otherSeriesColor,
} from './format';

export interface PieSlice {
  symbol: string;
  slot: number;
  value: number;
  logoUrl?: string | null;
}

interface AccDistPieProps {
  slices: PieSlice[];
  side: 'bought' | 'sold';
}

const TOP_COMPANIES = 8;

/** Company logo with initials fallback. */
function CompanyLogo({
  symbol,
  logoUrl,
}: {
  symbol: string;
  logoUrl?: string | null;
}) {
  const [failed, setFailed] = useState(false);

  if (!logoUrl || failed) {
    return (
      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-bg-border bg-bg-elevated text-[10px] font-bold text-text-secondary">
        {symbol === 'Others'
          ? 'OT'
          : symbol.slice(0, 2).toUpperCase()}
      </span>
    );
  }

  return (
    <img
      src={logoUrl}
      alt={`${symbol} logo`}
      loading="lazy"
      onError={() => setFailed(true)}
      className="h-7 w-7 shrink-0 rounded-full border border-bg-border bg-white object-contain p-0.5"
    />
  );
}

export default function AccDistPie({
  slices,
  side,
}: AccDistPieProps) {
  // Ignore invalid and non-positive values.
  const validSlices = slices
    .filter(
      (slice) =>
        Number.isFinite(slice.value) &&
        slice.value > 0
    )
    .sort((a, b) => b.value - a.value);

  const total = validSlices.reduce(
    (sum, slice) => sum + slice.value,
    0
  );

  if (!total) {
    return (
      <p className="py-16 text-center text-sm text-text-muted">
        The broker {side} nothing in the shown stocks in this range.
      </p>
    );
  }

  const topSlices = validSlices.slice(0, TOP_COMPANIES);
  const remainingSlices = validSlices.slice(TOP_COMPANIES);

  const othersValue = remainingSlices.reduce(
    (sum, slice) => sum + slice.value,
    0
  );

  const donutSlices = [
    ...topSlices,
    ...(othersValue > 0
      ? [
          {
            symbol: 'Others',
            slot: -1,
            value: othersValue,
          },
        ]
      : []),
  ];

  const isOthers = (symbol: string) => symbol === 'Others';

  const getColor = (slice: PieSlice) =>
    isOthers(slice.symbol)
      ? otherSeriesColor()
      : seriesColor(slice.slot);

  return (
    <div className="flex flex-col items-center gap-6 py-4 xl:flex-row xl:items-start xl:justify-center xl:gap-8">

      {/* DONUT CHART */}
      <div className="relative h-[280px] w-[280px] shrink-0">

        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={donutSlices}
              dataKey="value"
              nameKey="symbol"
              innerRadius={78}
              outerRadius={128}
              paddingAngle={2}
              stroke="var(--trading-panel)"
              strokeWidth={2}
              isAnimationActive={false}
            >
              {donutSlices.map((slice) => (
                <Cell
                  key={slice.symbol}
                  fill={getColor(slice)}
                />
              ))}
            </Pie>

            <Tooltip
              formatter={(value, name) => {
                const quantity = Number(value);
                const percentage = (quantity / total) * 100;

                return [
                  `${formatCount(quantity)} (${percentage.toFixed(1)}%)`,
                  String(name),
                ];
              }}
              contentStyle={{
                background: 'var(--trading-panel)',
                border: '1px solid var(--trading-grid)',
                borderRadius: 8,
                fontSize: 12,
              }}
            />
          </PieChart>
        </ResponsiveContainer>

        {/* CENTER INFORMATION */}
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-[11px] text-text-muted">
            {side === 'bought' ? 'Total bought' : 'Total sold'}
          </span>

          <span className="font-mono text-xl font-bold text-text-primary">
            {formatCount(total)}
          </span>

          <span className="mt-1 text-xs text-text-muted">
            {validSlices.length} companies
          </span>
        </div>
      </div>

      {/* COMPANY BREAKDOWN */}
      <div className="w-full min-w-0 flex-1 xl:max-w-[650px]">

        <div className="mb-3 flex items-center justify-between gap-2">
          <h3 className="text-sm font-semibold text-text-primary">
            Company breakdown
          </h3>

          <span className="text-xs text-text-muted">
            {side === 'bought' ? 'Buying share' : 'Selling share'}
          </span>
        </div>

        {/* RESPONSIVE MULTI-COLUMN COMPANY GRID */}
        <div className="grid grid-cols-1 gap-x-4 gap-y-2 sm:grid-cols-2 2xl:grid-cols-3">

          {validSlices.map((slice, index) => {
            const percentage = (slice.value / total) * 100;

            return (
              <div
                key={slice.symbol}
                className="min-w-0 rounded-lg border border-bg-border px-3 py-2"
              >
                {/* COMPANY NAME AND LOGO */}
                <div className="mb-2 flex min-w-0 items-center gap-2">

                  <span className="shrink-0 text-[11px] text-text-muted">
                    {index + 1}.
                  </span>

                  <CompanyLogo
                    symbol={slice.symbol}
                    logoUrl={slice.logoUrl}
                  />

                  <span
                    className="h-2.5 w-2.5 shrink-0 rounded-sm"
                    style={{
                      background: seriesColor(slice.slot),
                    }}
                  />

                  <span className="min-w-0 flex-1 truncate text-xs font-semibold text-text-primary">
                    {slice.symbol}
                  </span>
                </div>

                {/* QUANTITY AND PERCENTAGE */}
                <div className="mb-2 flex items-center justify-between gap-2">
                  <span className="truncate font-mono text-xs text-text-secondary">
                    {formatCount(slice.value)}
                  </span>

                  <span className="shrink-0 font-mono text-xs font-semibold text-text-primary">
                    {percentage.toFixed(1)}%
                  </span>
                </div>

                {/* SHARE BAR */}
                <div className="h-1.5 overflow-hidden rounded-full bg-bg-elevated">
                  <div
                    className="h-full rounded-full transition-all"
                    style={{
                      width: `${percentage}%`,
                      background: seriesColor(slice.slot),
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>

        {remainingSlices.length > 0 && (
          <p className="mt-3 text-xs text-text-muted">
            The donut groups {remainingSlices.length} smaller companies
            into Others. All companies are displayed in the breakdown.
          </p>
        )}
      </div>
    </div>
  );
}
