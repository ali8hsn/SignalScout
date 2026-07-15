import { sourceLabel } from './SignalBadge.jsx';

// Stable palette so each source keeps its color across renders.
const SOURCE_COLORS = {
  github: '#6B6B32',
  pdl: '#4E5D3A',
  coresignal: '#7A6B4E',
  semantic_scholar: '#5D6B6B',
  devpost: '#8A7A2E',
  graph: '#75664D',
};

export default function SourceMix({ mix }) {
  if (!mix || Object.keys(mix).length === 0) return null;
  const entries = Object.entries(mix).sort((a, b) => b[1] - a[1]);
  const total = entries.reduce((sum, [, count]) => sum + count, 0) || 1;

  return (
    <div className="bg-card border border-line rounded-md px-5 py-4 mb-4">
      <div className="flex items-center justify-between mb-2">
        <span className="label-mono">signal source mix</span>
        <span className="label-mono text-ink-faint">{total} signals</span>
      </div>
      <div className="flex h-2 w-full overflow-hidden rounded-sm bg-line/40">
        {entries.map(([source, count]) => (
          <div
            key={source}
            style={{ width: `${(100 * count) / total}%`, background: SOURCE_COLORS[source] || '#8A8574' }}
            title={`${sourceLabel(source)}: ${count} (${((100 * count) / total).toFixed(1)}%)`}
          />
        ))}
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1 mt-3">
        {entries.map(([source, count]) => (
          <span key={source} className="flex items-center gap-1.5 font-mono text-[10px] text-ink-soft">
            <span
              className="inline-block w-2 h-2 rounded-full"
              style={{ background: SOURCE_COLORS[source] || '#8A8574' }}
            />
            {sourceLabel(source)} {((100 * count) / total).toFixed(0)}%
          </span>
        ))}
      </div>
    </div>
  );
}
