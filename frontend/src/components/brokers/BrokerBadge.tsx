import { useState } from 'react';

export interface BrokerBadgeProps {
  brokerCode: string;
  name?: string | null;
  shortName?: string | null;
  logoUrl?: string | null;
  className?: string;
}

const initials = (value: string) => value.trim().split(/\s+/).slice(0, 2).map(part => part[0]).join('').toUpperCase() || '?';

function colorForCode(code: string) {
  let hash = 0;
  for (let i = 0; i < code.length; i += 1) hash = (hash * 31 + code.charCodeAt(i)) >>> 0;
  return `hsl(${hash % 360} 48% 34%)`;
}

export default function BrokerBadge({ brokerCode, name, shortName, logoUrl, className = '' }: BrokerBadgeProps) {
  const [broken, setBroken] = useState(false);
  const displayName = name || `Broker ${brokerCode}`;
  const imageUrl = logoUrl;
  return <span className={`inline-flex min-w-0 items-center gap-2 ${className}`}>
    {imageUrl && !broken ? <img src={imageUrl} alt="" className="h-8 w-8 shrink-0 rounded-full object-contain" onError={() => setBroken(true)} />
      : <span aria-hidden="true" className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[10px] font-semibold text-white" style={{ backgroundColor: colorForCode(brokerCode) }}>{initials(shortName || displayName)}</span>}
    <span className="min-w-0"><span className="block truncate font-medium text-text-primary">{displayName}</span><span className="block text-[10px] text-text-muted">#{brokerCode}</span></span>
  </span>;
}
