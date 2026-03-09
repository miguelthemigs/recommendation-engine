import type { MediaItem } from '../../api/types';
import { MediaCard } from './MediaCard';

interface Props {
  items: MediaItem[];
  highlightIds?: Set<string>;
}

export function MediaGrid({ items, highlightIds }: Props) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-4">
      {items.map(item => (
        <MediaCard
          key={item.id}
          item={item}
          highlight={highlightIds?.has(String(item.id))}
        />
      ))}
    </div>
  );
}
