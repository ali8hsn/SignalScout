const STAGE_LABELS = {
  scrape: 'Scrape',
  resolve: 'Resolve',
  enrich: 'Enrich',
  score: 'Score',
};

const STAGE_HINTS = {
  scrape: 'fetching seed follows + profiles',
  resolve: 'dedupe vs known, keep unknowns',
  enrich: 'contacts + locations',
  score: 'calibrated founder-likeness rank',
};

function countLabel(name, count) {
  switch (name) {
    case 'scrape':
      return count ? `${count} profiles` : 'profiles';
    case 'resolve':
      return count ? `${count} unknowns` : 'unknowns';
    case 'enrich':
      return count ? `${count} enriched` : 'enriched';
    case 'score':
      return 'scored';
    default:
      return '';
  }
}

function Dot({ status }) {
  const base = 'w-3 h-3 rounded-full border';
  if (status === 'done') return <span className={`${base} bg-olive border-olive`} />;
  if (status === 'active') return <span className={`${base} bg-olive/40 border-olive animate-pulse`} />;
  if (status === 'error') return <span className={`${base} bg-red-400 border-red-500`} />;
  return <span className={`${base} bg-transparent border-line`} />;
}

export default function PipelineProgress({ status }) {
  if (!status || status.state === 'idle') return null;
  const stages = status.stages || [];

  return (
    <div className="bg-card border border-line rounded-md px-8 py-6 max-w-2xl mx-auto mb-8">
      <div className="flex items-center justify-between mb-5">
        <p className="label-mono">live discovery pipeline</p>
        <span className="font-mono text-[10px] tracking-widest text-ink-faint">
          {status.state === 'running' && 'RUNNING…'}
          {status.state === 'done' && `DONE · ${status.discovered_count} new`}
          {status.state === 'error' && 'ERROR'}
        </span>
      </div>

      <div className="flex items-stretch">
        {stages.map((stage, i) => (
          <div key={stage.name} className="flex items-stretch flex-1">
            <div className="flex flex-col items-center flex-1">
              <Dot status={stage.status} />
              <p
                className={`font-mono text-xs mt-2 ${
                  stage.status === 'pending' ? 'text-ink-faint' : 'text-ink'
                }`}
              >
                {STAGE_LABELS[stage.name]}
              </p>
              <p className="font-mono text-[10px] text-olive mt-1 h-3">
                {stage.status !== 'pending' ? countLabel(stage.name, stage.count) : ''}
              </p>
              <p className="font-mono text-[9px] text-ink-faint mt-1 text-center leading-tight px-1">
                {STAGE_HINTS[stage.name]}
              </p>
            </div>
            {i < stages.length - 1 && (
              <div className="flex items-center pt-1">
                <span
                  className={`block w-8 h-px ${
                    stages[i + 1].status !== 'pending' || stage.status === 'done'
                      ? 'bg-olive'
                      : 'bg-line'
                  }`}
                />
              </div>
            )}
          </div>
        ))}
      </div>

      {status.error && (
        <p className="font-mono text-[11px] text-red-500 mt-5 text-center">{status.error}</p>
      )}
    </div>
  );
}
