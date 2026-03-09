import { useState } from 'react';
import { posterUrl } from '../../lib/utils';

interface Props {
  posterPath: string | null;
  title: string;
  className?: string;
}

export function PosterImage({ posterPath, title, className = '' }: Props) {
  const [failed, setFailed] = useState(false);
  const src = posterUrl(posterPath);

  if (!src || failed) {
    return (
      <div className={`bg-surface-raised flex items-center justify-center text-text-muted text-xs text-center p-2 ${className}`}>
        {title}
      </div>
    );
  }

  return (
    <img
      src={src}
      alt={title}
      onError={() => setFailed(true)}
      className={`object-cover ${className}`}
    />
  );
}
