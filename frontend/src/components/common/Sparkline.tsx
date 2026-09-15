interface SparklineProps {
  data: number[];
  width?: number;
  height?: number;
  positive?: boolean;
}

export default function Sparkline({ data, width = 80, height = 28, positive = true }: SparklineProps) {
  if (!data || data.length < 2) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const pad = 2;
  const pts = data.map((v, i) => {
    const x = pad + (i / (data.length - 1)) * (width - pad * 2);
    const y = pad + ((max - v) / range) * (height - pad * 2);
    return `${x},${y}`;
  });
  const color = positive ? '#22C55E' : '#EF4444';
  const fill  = positive ? 'rgba(34,197,94,0.08)' : 'rgba(239,68,68,0.08)';
  const last  = pts[pts.length - 1].split(',');
  const polyFill = `${pts.join(' ')} ${last[0]},${height} ${pad},${height}`;

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      <polyline fill={fill} stroke="none" points={polyFill} />
      <polyline fill="none" stroke={color} strokeWidth={1.5} strokeLinejoin="round" points={pts.join(' ')} />
    </svg>
  );
}
