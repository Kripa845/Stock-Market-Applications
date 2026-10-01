import { useEffect, useState } from 'react';

interface CompanyLogoProps {
  symbol: string;
  name?: string;
  logoUrl?: string | null;
  size?: 'sm' | 'md' | 'lg';
}

const sizeClasses = {
  sm: 'h-7 w-7 text-[10px]',
  md: 'h-9 w-9 text-xs',
  lg: 'h-12 w-12 text-sm',
};

export default function CompanyLogo({ symbol, name, logoUrl, size = 'md' }: CompanyLogoProps) {
  const [broken, setBroken] = useState(false);

  useEffect(() => setBroken(false), [logoUrl]);

  const classes = `flex shrink-0 items-center justify-center rounded-lg bg-accent/20 font-bold text-accent-light ${sizeClasses[size]}`;

  return logoUrl && !broken ? (
    <img
      src={logoUrl}
      alt={`${name || symbol} logo`}
      className={`shrink-0 rounded-lg bg-white object-contain p-0.5 ${sizeClasses[size]}`}
      onError={() => setBroken(true)}
    />
  ) : (
    <span aria-hidden="true" className={classes}>
      {symbol.slice(0, 1).toUpperCase() || '?'}
    </span>
  );
}
