import { useState } from 'react';
import { ALL_NEWS_ID, type NewsSource } from '../../config/newsSources';

interface SourceFilterProps {
  sources: NewsSource[];
  active: string;
  onChange: (id: string) => void;
  className?: string;
}

function SourceLogo({ source }: { source: NewsSource }) {
  const [failed, setFailed] = useState(false);
  const isAll = source.id === ALL_NEWS_ID;
  const showImage = !isAll && source.logoUrl && !failed;

  return (
    <span
      className="flex h-7 w-7 shrink-0 items-center justify-center overflow-hidden rounded-full text-xs font-bold"
      style={{
        border: `1.5px solid ${source.brandColor}`,
        background: isAll ? '#d1d5db' : '#ffffff',
        color: isAll ? '#1a1d24' : source.brandColor,
      }}
      aria-hidden="true"
    >
      {showImage ? (
        <img
          src={source.logoUrl}
          alt=""
          loading="lazy"
          referrerPolicy="no-referrer"
          onError={() => setFailed(true)}
          className="h-full w-full object-contain p-0.5"
        />
      ) : (
        // Initial letter when there's no logo or it failed to load
        source.name.charAt(0).toUpperCase()
      )}
    </span>
  );
}

// Single-select news source picker: a 2-column panel on desktop (lg+),
// a horizontally scrollable chip row below 1024px.
export default function SourceFilter({ sources, active, onChange, className = '' }: SourceFilterProps) {
  return (
    <nav aria-label="Filter news by source" className={`font-mulish ${className}`}>
      <div className="flex gap-2 overflow-x-auto pb-1 lg:grid lg:grid-cols-2 lg:overflow-visible lg:rounded-xl lg:bg-[#1a1d24] lg:p-2 lg:pb-2">
        {sources.map((source) => {
          const isActive = source.id === active;
          return (
            <button
              key={source.id}
              type="button"
              title={source.name}
              aria-pressed={isActive}
              onClick={() => onChange(source.id)}
              className={`flex h-[46px] min-w-0 shrink-0 items-center gap-2.5 rounded-lg border px-2.5 text-left text-sm font-medium transition-colors duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#2dd4bf] focus-visible:ring-offset-2 focus-visible:ring-offset-[#151515] max-lg:max-w-[11rem] ${
                isActive
                  ? 'border-[#1f6f6b] bg-[#0f3b3b] text-white'
                  : 'border-white/[0.08] bg-[#1a1d24] text-[#d1d5db] hover:border-white/20 hover:bg-[#22262f]'
              }`}
            >
              <SourceLogo source={source} />
              <span className="min-w-0 truncate">{source.name}</span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
