const BUCKETS = 10;

function histogram(scores) {
  const counts = Array(BUCKETS).fill(0);
  scores.forEach((s) => {
    counts[Math.min(BUCKETS - 1, Math.floor(s / (100 / BUCKETS)))] += 1;
  });
  return counts;
}

export default function ScoreDistribution({ founderScores, controlScores, threshold }) {
  const founders = histogram(founderScores || []);
  const controls = histogram(controlScores || []);
  const maxCount = Math.max(...founders, ...controls, 1);

  return (
    <div className="bg-card border border-line rounded-md p-6">
      <div className="flex items-end gap-1.5 h-40 relative">
        {founders.map((f, i) => (
          <div key={i} className="flex-1 flex items-end gap-0.5 h-full relative">
            <div
              className="flex-1 bg-line rounded-t-sm"
              style={{ height: `${(controls[i] / maxCount) * 100}%` }}
              title={`controls ${i * 10}–${i * 10 + 10}: ${controls[i]}`}
            />
            <div
              className="flex-1 bg-olive rounded-t-sm"
              style={{ height: `${(f / maxCount) * 100}%` }}
              title={`founders ${i * 10}–${i * 10 + 10}: ${f}`}
            />
          </div>
        ))}
        <div
          className="absolute top-0 bottom-0 w-px bg-ink"
          style={{ left: `${threshold}%` }}
        >
          <span className="absolute -top-1 left-1.5 font-mono text-[9px] uppercase tracking-widest text-ink">
            threshold
          </span>
        </div>
      </div>
      <div className="flex justify-between font-mono text-[10px] text-ink-faint mt-2">
        <span>0</span><span>score</span><span>100</span>
      </div>
      <div className="flex gap-5 mt-3 font-mono text-[10px]">
        <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 bg-olive rounded-sm" /> founders (pre-breakout)</span>
        <span className="flex items-center gap-1.5"><span className="w-2.5 h-2.5 bg-line rounded-sm" /> controls</span>
      </div>
    </div>
  );
}
