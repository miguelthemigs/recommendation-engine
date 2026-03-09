import { formatScore, scoreColor, cn } from '../../lib/utils';

interface Props {
  score: number;
  label?: string;
}

export function ScorePill({ score, label }: Props) {
  return (
    <span className={cn('text-xs font-mono font-semibold', scoreColor(score))}>
      {label && <span className="text-text-muted mr-1">{label}</span>}
      {formatScore(score)}
    </span>
  );
}
