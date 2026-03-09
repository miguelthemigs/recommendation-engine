export function posterUrl(posterPath: string | null, size = 'w300'): string {
  if (!posterPath) return '';
  return `https://image.tmdb.org/t/p/${size}${posterPath}`;
}

export function formatScore(score: number): string {
  return (score * 100).toFixed(0) + '%';
}

export function scoreColor(score: number): string {
  if (score >= 0.7) return 'text-score-high';
  if (score >= 0.4) return 'text-score-medium';
  return 'text-score-low';
}

export function cn(...classes: (string | undefined | false | null)[]): string {
  return classes.filter(Boolean).join(' ');
}

export function releaseYear(item: { year?: number | null }): string {
  return item.year ? String(item.year) : '';
}
