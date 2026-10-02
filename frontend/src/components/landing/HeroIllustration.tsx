// Flat "investing" illustration for the landing hero: a stream of coins arcing round a lime card,
// a large rupee coin, and a hand holding a phone with a portfolio chart. Pure SVG (no image files);
// the same picture in light and dark themes.

const INK = '#0b0a12';
const LIME = '#cdf24a';
const LIME_DARK = '#9cc21f';
const VIOLET = '#8b5cf6';
const VIOLET_DARK = '#6d28d9';
const PAPER = '#f5f3ff';
const EDGE = '#c4b5fd'; // light outline so the black hand stays readable on a dark page

// Coins stacked along a C-shaped arc, seen edge-on so they read as a flowing column.
const ARC = { cx: 262, cy: 212, r: 148, from: 128, to: 342 };
const ARC_COINS = (() => {
  const coins: { x: number; y: number; rot: number; fill: string; rim: string }[] = [];
  const n = 54;
  for (let i = 0; i < n; i++) {
    const deg = ARC.from + ((ARC.to - ARC.from) * i) / (n - 1);
    const a = (deg * Math.PI) / 180;
    // The first few coins are lime, then bands of four white and four violet.
    const band = Math.floor(i / 4) % 2;
    const lime = i < 7;
    coins.push({
      x: ARC.cx + ARC.r * Math.cos(a),
      y: ARC.cy + ARC.r * Math.sin(a),
      rot: deg,
      fill: lime ? LIME : band ? VIOLET : PAPER,
      rim: lime ? LIME_DARK : band ? VIOLET_DARK : '#ddd6fe',
    });
  }
  return coins;
})();

const sparkle = (x: number, y: number, s: number) =>
  `M${x} ${y - s} Q${x} ${y} ${x + s} ${y} Q${x} ${y} ${x} ${y + s} Q${x} ${y} ${x - s} ${y} Q${x} ${y} ${x} ${y - s}Z`;

// Small portfolio chart on the phone screen.
const CHART = [62, 58, 64, 60, 70, 66, 74, 71, 80, 77, 88];

export default function HeroIllustration({ className = '' }: { className?: string }) {
  const chartPts = CHART.map((v, i) => `${-42 + i * 8.4},${-4 - (v - 55) * 1.3}`);
  return (
    <svg viewBox="0 0 580 480" className={className} aria-hidden>
      <defs>
        <radialGradient id="hero-glow" cx="50%" cy="48%" r="50%">
          <stop offset="0%" stopColor="#7c3aed" stopOpacity="0.32" />
          <stop offset="100%" stopColor="#7c3aed" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="hero-chart" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={LIME} stopOpacity="0.9" />
          <stop offset="100%" stopColor={LIME} stopOpacity="0.1" />
        </linearGradient>
      </defs>
      <circle cx="280" cy="230" r="240" fill="url(#hero-glow)" />

      {/* Coin stream */}
      <g stroke={INK} strokeWidth="2">
        {ARC_COINS.map((c, i) => (
          <g key={i} transform={`translate(${c.x} ${c.y}) rotate(${c.rot})`}>
            <ellipse cx="0" cy="3" rx="34" ry="11" fill={c.rim} />
            <ellipse cx="0" cy="0" rx="34" ry="11" fill={c.fill} />
          </g>
        ))}
      </g>

      {/* Lime card */}
      <g transform="translate(168 236) rotate(-24)" stroke={INK} strokeWidth="2.5">
        <rect x="-82" y="-50" width="164" height="100" rx="12" fill={LIME_DARK} transform="translate(5 6)" />
        <rect x="-82" y="-50" width="164" height="100" rx="12" fill={LIME} />
        <rect x="-82" y="-26" width="164" height="16" fill={INK} strokeWidth="0" />
        <rect x="-64" y="2" width="28" height="20" rx="4" fill="#fde68a" />
        <path d="M-64 12h28M-50 2v20" strokeWidth="1.5" />
        <text x="66" y="38" textAnchor="end" fontSize="15" fontWeight="800" fill={INK} stroke="none" fontFamily="inherit">NPR</text>
      </g>

      {/* Big rupee coin */}
      <g transform="translate(468 104) rotate(14)" stroke={INK} strokeWidth="2.5">
        <circle cx="7" cy="6" r="44" fill="#ddd6fe" />
        <circle cx="0" cy="0" r="44" fill={PAPER} />
        <circle cx="0" cy="0" r="33" fill="none" strokeWidth="2" strokeDasharray="3 5" />
        <text x="0" y="11" textAnchor="middle" fontSize="30" fontWeight="800" fill={INK} stroke="none" fontFamily="inherit">Rs</text>
      </g>

      {/* Small loose coins */}
      <g stroke={INK} strokeWidth="2">
        <g transform="translate(92 352) rotate(-30)">
          <ellipse cx="0" cy="4" rx="20" ry="9" fill={VIOLET_DARK} />
          <ellipse cx="0" cy="0" rx="20" ry="9" fill={VIOLET} />
        </g>
        <g transform="translate(136 398) rotate(18)">
          <ellipse cx="0" cy="4" rx="16" ry="7" fill={LIME_DARK} />
          <ellipse cx="0" cy="0" rx="16" ry="7" fill={LIME} />
        </g>
      </g>

      {/* Hand holding a phone */}
      <g transform="translate(396 326) rotate(-13)">
        {/* sleeve and palm behind the phone */}
        <rect x="62" y="92" width="84" height="62" rx="10" fill={PAPER} stroke={INK} strokeWidth="2.5" transform="rotate(-28 62 92)" />
        <path d="M-40 40 C-30 110 40 140 100 112 L120 96 C110 40 70 0 40 -10 Z" fill={INK} stroke={EDGE} strokeWidth="1.5" />

        {/* phone */}
        <rect x="-64" y="-122" width="128" height="240" rx="20" fill={INK} stroke={EDGE} strokeWidth="1.5" />
        <rect x="-55" y="-111" width="110" height="218" rx="13" fill="#faf9ff" />
        <rect x="-16" y="-106" width="32" height="6" rx="3" fill={INK} />
        <text x="-44" y="-80" fontSize="11" fontWeight="800" fill={INK} fontFamily="inherit">Portfolio</text>
        <text x="-44" y="-62" fontSize="15" fontWeight="800" fill={INK} fontFamily="inherit">Rs 1,24,560</text>
        <rect x="-44" y="-54" width="40" height="14" rx="7" fill={LIME} />
        <text x="-24" y="-44" textAnchor="middle" fontSize="8.5" fontWeight="800" fill={INK} fontFamily="inherit">+2.4%</text>
        <path d={`M${chartPts[0]} L${chartPts.join(' L')} L42,16 L-42,16 Z`} fill="url(#hero-chart)" />
        <polyline points={chartPts.join(' ')} fill="none" stroke={VIOLET_DARK} strokeWidth="2.2" strokeLinejoin="round" strokeLinecap="round" />
        {[[-38, 44, 54, 30, 1], [-26, 36, 50, 26, 1], [-14, 42, 60, 30, 0], [-2, 30, 44, 22, 1], [10, 26, 40, 18, 1], [22, 30, 50, 22, 0], [34, 20, 36, 12, 1]].map(([x, top, bot, h, up], i) => (
          <g key={i}>
            <line x1={x} y1={top - 4 + 20} x2={x} y2={bot + 4 + 20} stroke={INK} strokeWidth="1" />
            <rect x={x - 3.5} y={top + 20} width="7" height={Math.max(4, bot - top - h / 3)} rx="1" fill={up ? '#16a34a' : '#e11d48'} />
          </g>
        ))}
        <rect x="-44" y="84" width="88" height="14" rx="7" fill={VIOLET} />
        <text x="0" y="94" textAnchor="middle" fontSize="8" fontWeight="700" fill="#fff" fontFamily="inherit">View analysis</text>

        {/* thumb over the left edge, fingers round the right edge */}
        <path d="M-82 54 C-86 30 -70 14 -52 20 L-30 30 C-20 36 -24 52 -36 52 L-58 48 C-66 66 -78 70 -82 54 Z" fill={INK} stroke={EDGE} strokeWidth="1.5" />
        {[-4, 22, 48].map((y) => (
          <rect key={y} x="48" y={y} width="36" height="20" rx="10" fill={INK} stroke={EDGE} strokeWidth="1.5" />
        ))}
      </g>

      {/* Sparkles */}
      <path d={sparkle(70, 120, 12)} fill={LIME} stroke={INK} strokeWidth="1.5" />
      <path d={sparkle(372, 40, 9)} fill={VIOLET} stroke={INK} strokeWidth="1.5" />
      <path d={sparkle(520, 214, 8)} fill={LIME} stroke={INK} strokeWidth="1.5" />
      <circle cx="44" cy="226" r="4" fill={VIOLET} />
      <circle cx="300" cy="438" r="3.5" fill={LIME} />
      <circle cx="232" cy="30" r="3" fill={EDGE} />
    </svg>
  );
}
