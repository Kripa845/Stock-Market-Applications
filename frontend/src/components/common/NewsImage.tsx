import { useState } from 'react';

// Lead image of a crawled article, loaded straight from the source portal.
// Renders nothing when the article has no image or the image fails to load,
// so a removed or blocked picture never shows as a broken icon.
export default function NewsImage({ src, className = '' }: { src?: string | null; className?: string }) {
  const [failed, setFailed] = useState(false);
  if (!src || failed) return null;
  return (
    <img
      src={src}
      alt=""
      loading="lazy"
      decoding="async"
      referrerPolicy="no-referrer"
      onError={() => setFailed(true)}
      className={`block object-cover bg-bg-elevated ${className}`}
    />
  );
}
