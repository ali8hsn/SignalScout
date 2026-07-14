import { useEffect, useState } from 'react';
import { api } from '../api/client.js';
import CandidateCard from '../components/CandidateCard.jsx';
import CandidateTable from '../components/CandidateTable.jsx';
import EvidencePanel from '../components/EvidencePanel.jsx';

export default function Discover() {
  const [candidates, setCandidates] = useState([]);
  const [index, setIndex] = useState(0);
  const [browseAll, setBrowseAll] = useState(false);
  const [evidenceId, setEvidenceId] = useState(null);
  const [cohort, setCohort] = useState('discovery');

  useEffect(() => {
    api.candidates(cohort).then((d) => {
      setCandidates(d.candidates);
      setIndex(0);
    }).catch(console.error);
  }, [cohort]);

  if (!candidates.length) return <p className="font-mono text-xs text-ink-faint">loading candidates…</p>;

  const current = candidates[index];

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div className="flex gap-1">
          {[['discovery', 'DISCOVERIES'], ['founder', 'GROUND TRUTH']].map(([value, label]) => (
            <button
              key={value}
              onClick={() => setCohort(value)}
              className={`px-3 py-1 font-mono text-[10px] tracking-widest border rounded-sm ${
                cohort === value ? 'border-olive text-olive' : 'border-line text-ink-faint hover:text-ink-soft'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
        <button
          onClick={() => setBrowseAll(!browseAll)}
          className="font-mono text-xs text-olive hover:text-olive-dark"
        >
          {browseAll ? '← Card view' : 'Browse all →'}
        </button>
      </div>

      {browseAll ? (
        <CandidateTable candidates={candidates} onSelect={(c) => setEvidenceId(c.id)} />
      ) : (
        <>
          <CandidateCard
            candidate={current}
            rank={index + 1}
            onViewEvidence={() => setEvidenceId(current.id)}
          />
          <div className="flex items-center justify-center gap-6 mt-6 font-mono text-xs">
            <button
              onClick={() => setIndex(Math.max(0, index - 1))}
              disabled={index === 0}
              className="text-ink-soft disabled:text-line hover:text-olive"
            >
              ← Previous
            </button>
            <span className="text-ink-faint">{index + 1} of {candidates.length}</span>
            <button
              onClick={() => setIndex(Math.min(candidates.length - 1, index + 1))}
              disabled={index === candidates.length - 1}
              className="text-ink-soft disabled:text-line hover:text-olive"
            >
              Next →
            </button>
          </div>
        </>
      )}

      {evidenceId && <EvidencePanel personId={evidenceId} onClose={() => setEvidenceId(null)} />}
    </div>
  );
}
