const CATEGORY_ICONS = {
  competition: '\u2606', // star outline
  code: '\u2318',
  research: '\u00a7',
  hackathon: '\u2692',
  connection: '\u26AD',
  fellowship: '\u272A',
  debate: '\u275E',
};

export default function SignalBadge({ signal }) {
  const icon = CATEGORY_ICONS[signal.category] || '\u2022';
  return (
    <span className="inline-flex items-center gap-1.5 border border-line rounded-sm px-2.5 py-1 font-mono text-[11px] text-ink-soft bg-card">
      <span className="text-olive">{icon}</span>
      {signal.summary || signal.type}
    </span>
  );
}
