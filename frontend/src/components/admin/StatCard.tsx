import type { LucideIcon } from "lucide-react";

interface Props {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: LucideIcon;
}

export default function StatCard({
  title,
  value,
  subtitle,
  icon: Icon,
}: Props) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-5 shadow-sm">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm text-slate-400">
            {title}
          </p>

          <p className="mt-2 text-2xl font-bold text-white">
            {value}
          </p>

          {subtitle && (
            <p className="mt-1 text-xs text-slate-500">
              {subtitle}
            </p>
          )}
        </div>

        <div className="rounded-lg bg-blue-500/10 p-2.5">
          <Icon
            size={20}
            className="text-blue-400"
          />
        </div>
      </div>
    </div>
  );
}