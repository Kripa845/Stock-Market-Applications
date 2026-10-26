import { Minus, TrendingDown, TrendingUp } from 'lucide-react';
import type { AccumulationSignal } from '../../../api/brokerAccumulation';

// Accumulation (green) / Distribution (red) / Neutral (gray), with the top-5 buy / sell ratio.

const STYLE: Record<AccumulationSignal, { label: string; className: string; icon: typeof Minus }> = {
  accumulation: { label: 'Accumulation', className: 'border-up/30 bg-up/10 text-up', icon: TrendingUp },
  distribution: { label: 'Distribution', className: 'border-down/30 bg-down/10 text-down', icon: TrendingDown },
  neutral: { label: 'Neutral', className: 'border-bg-border bg-bg-elevated text-text-secondary', icon: Minus },
  no_data: { label: 'No data', className: 'border-bg-border bg-bg-elevated text-text-muted', icon: Minus },
};

export default function SignalBadge({ signal, ratio }: { signal: AccumulationSignal; ratio: number | null }) {
  const style = STYLE[signal];
  const Icon = style.icon;
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm font-semibold ${style.className}`}
      title="Top-5 net buying ÷ top-5 net selling"
    >
      <Icon size={15} />
      {style.label}
      {signal !== 'no_data' && (
        <span className="font-mono text-xs font-medium opacity-80">
          {ratio === null ? '· all buying' : `· ${ratio.toFixed(2)}×`}
        </span>
      )}
    </span>
  );
}
