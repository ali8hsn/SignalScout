const CATEGORY_COLORS = {
  competition: '#6B6B32',
  code: '#8A7A2E',
  research: '#4E5D3A',
  hackathon: '#7A6B4E',
  connection: '#5D6B6B',
  fellowship: '#6B5D32',
  debate: '#75664D',
};

export default function SignalTimeline({ timeline, breakout }) {
  if (!timeline?.length) return <p className="text-ink-faint text-sm">No signals.</p>;

  const dates = timeline.map((t) => new Date(t.date).getTime());
  const min = Math.min(...dates);
  const max = Math.max(...dates, breakout ? new Date(breakout).getTime() : 0);
  const span = Math.max(max - min, 1);
  const pos = (d) => 4 + 92 * ((new Date(d).getTime() - min) / span);

  return (
    <div className="bg-card border border-line rounded-md px-6 pt-8 pb-2">
      <div className="relative h-10">
        <div className="absolute left-0 right-0 top-1/2 h-px bg-line" />
        {timeline.map((t, i) => (
          <div
            key={i}
            className="absolute top-1/2 -translate-y-1/2 group"
            style={{ left: `${pos(t.date)}%` }}
          >
            <div
              className="w-3 h-3 rounded-full border-2 border-card cursor-default"
              style={{ background: CATEGORY_COLORS[t.category] || '#8A8574' }}
            />
            <div className="absolute bottom-5 left-1/2 -translate-x-1/2 hidden group-hover:block bg-ink text-cream font-mono text-[10px] px-2.5 py-1.5 rounded-sm whitespace-nowrap z-10">
              {t.date} — {t.summary || t.type}
            </div>
          </div>
        ))}
        {breakout && (
          <div className="absolute top-0 bottom-0" style={{ left: `${pos(breakout)}%` }}>
            <div className="w-px h-full bg-olive" />
            <span className="absolute -top-6 left-1/2 -translate-x-1/2 font-mono text-[9px] uppercase tracking-widest text-olive whitespace-nowrap">
              breakout
            </span>
          </div>
        )}
      </div>
      <div className="flex justify-between font-mono text-[10px] text-ink-faint mt-2 pb-2">
        <span>{timeline[0].date}</span>
        <span>{breakout || timeline[timeline.length - 1].date}</span>
      </div>
    </div>
  );
}
