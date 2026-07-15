const CATEGORY_ICONS = {
  competition: '\u2606', // star outline
  code: '\u2318',
  research: '\u00a7',
  hackathon: '\u2692',
  connection: '\u26AD',
  fellowship: '\u272A',
  debate: '\u275E',
  education: '\u2709',
  career: '\u25B8',
  network: '\u26AD',
};

// Human labels for signal provenance, shown on every badge.
export const SOURCE_LABELS = {
  github: 'GitHub',
  pdl: 'PDL',
  coresignal: 'Coresignal',
  semantic_scholar: 'Semantic Scholar',
  devpost: 'Devpost',
  graph: 'Network',
};

export function sourceLabel(source) {
  if (!source) return null;
  return SOURCE_LABELS[source] || source;
}

export default function SignalBadge({ signal }) {
  const icon = CATEGORY_ICONS[signal.category] || '\u2022';
  const source = sourceLabel(signal.source);
  return (
    <span className="inline-flex items-center gap-1.5 border border-line rounded-sm px-2.5 py-1 font-mono text-[11px] text-ink-soft bg-card">
      <span className="text-olive">{icon}</span>
      {signal.summary || signal.type}
      {source && (
        <span
          className="ml-1 pl-1.5 border-l border-line text-[9px] uppercase tracking-wider text-ink-faint"
          title={`Source: ${source}`}
        >
          {source}
        </span>
      )}
    </span>
  );
}
