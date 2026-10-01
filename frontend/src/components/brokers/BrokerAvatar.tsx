const AVATAR_COLORS = [
  'bg-blue-700',
  'bg-emerald-700',
  'bg-violet-700',
  'bg-rose-700',
  'bg-amber-700',
  'bg-cyan-700',
  'bg-indigo-700',
  'bg-teal-700',
];

interface BrokerAvatarProps {
  brokerNo: string | number;
  name: string;
}

export default function BrokerAvatar({ brokerNo, name }: BrokerAvatarProps) {
  const no = Number(brokerNo) || 0;
  const color = AVATAR_COLORS[Math.abs(no) % AVATAR_COLORS.length];
  const initial = name.trim().charAt(0).toUpperCase() || '?';

  return (
    <span
      aria-hidden="true"
      className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-bold text-white ${color}`}
    >
      {initial}
    </span>
  );
}
