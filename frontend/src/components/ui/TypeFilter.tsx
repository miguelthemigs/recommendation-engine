interface Props {
  value: string;
  onChange: (v: string) => void;
}

const OPTIONS = [
  { label: 'All', value: 'all' },
  { label: 'Movies', value: 'movie' },
  { label: 'Shows', value: 'show' },
];

export function TypeFilter({ value, onChange }: Props) {
  return (
    <div className="flex gap-2">
      {OPTIONS.map(opt => (
        <button
          key={opt.value}
          onClick={() => onChange(opt.value)}
          className={`px-3 py-1.5 rounded-lg text-sm border transition ${
            value === opt.value
              ? 'bg-accent border-accent text-white'
              : 'bg-surface-raised border-surface-border text-text-secondary hover:text-text-primary'
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}
