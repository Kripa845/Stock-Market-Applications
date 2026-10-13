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

/** Broker logo with a coloured-initials fallback when there is no logo or it fails to load. */
export function BrokerLogo({ brokerCode, name, shortName, logoUrl, size = 32 }: Omit<BrokerBadgeProps, 'className'> & { size?: number }) {
  const [broken, setBroken] = useState(false);
  const label = shortName || name || `Broker ${brokerCode}`;
  const box = { width: size, height: size };
  return logoUrl && !broken
    ? <img src={logoUrl} alt="" style={box} className="shrink-0 rounded-full bg-white object-contain" onError={() => setBroken(true)} />
    : <span aria-hidden="true" className="flex shrink-0 items-center justify-center rounded-full font-semibold text-white" style={{ ...box, fontSize: Math.max(10, size * 0.32), backgroundColor: colorForCode(brokerCode) }}>{initials(label)}</span>;
}

export default function BrokerBadge({ brokerCode, name, shortName, logoUrl, className = '' }: BrokerBadgeProps) {
  const displayName = name || `Broker ${brokerCode}`;
  return <span className={`inline-flex min-w-0 items-center gap-2 ${className}`}>
    <BrokerLogo brokerCode={brokerCode} name={displayName} shortName={shortName} logoUrl={logoUrl} />
    <span className="min-w-0"><span className="block truncate font-medium text-text-primary">{displayName}</span><span className="block text-[10px] text-text-muted">#{brokerCode}</span></span>
  </span>;
}
