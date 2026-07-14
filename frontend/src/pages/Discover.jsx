import { useEffect, useRef, useState } from 'react';
import { api } from '../api/client.js';
import CandidateCard from '../components/CandidateCard.jsx';
import CandidateTable from '../components/CandidateTable.jsx';
import EvidencePanel from '../components/EvidencePanel.jsx';
import PipelineProgress from '../components/PipelineProgress.jsx';

const POLL_MS = 1200;

export default function Discover() {
  const [candidates, setCandidates] = useState([]);
  const [index, setIndex] = useState(0);
  const [browseAll, setBrowseAll] = useState(false);
  const [evidenceId, setEvidenceId] = useState(null);
  const [cohort, setCohort] = useState('discovery');

  const [jobStatus, setJobStatus] = useState(null);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState(null);
  const [newIds, setNewIds] = useState(new Set());
  const pollRef = useRef(null);

  const loadCandidates = (which) =>
    api.candidates(which).then((d) => {
      setCandidates(d.candidates);
      setIndex(0);
      return d.candidates;
    });

  useEffect(() => {
    loadCandidates(cohort).catch(console.error);
  }, [cohort]);

  useEffect(() => () => clearInterval(pollRef.current), []);

  const onComplete = async (priorIds) => {
    setRunning(false);
    setCohort('discovery');
    const fresh = await loadCandidates('discovery').catch(() => []);
    setNewIds(new Set(fresh.filter((c) => !priorIds.has(c.id)).map((c) => c.id)));
    setBrowseAll(true);
  };

  const runDiscovery = async () => {
    setRunError(null);
    setNewIds(new Set());
    const priorIds = new Set(candidates.map((c) => c.id));
    try {
      const res = await api.runDiscovery();
      setJobStatus(res.status);
      setRunning(true);
      clearInterval(pollRef.current);
      pollRef.current = setInterval(async () => {
        try {
          const status = await api.discoveryStatus();
          setJobStatus(status);
          if (status.state === 'done' || status.state === 'error') {
            clearInterval(pollRef.current);
            if (status.state === 'done') onComplete(priorIds);
            else setRunning(false);
          }
        } catch (err) {
          clearInterval(pollRef.current);
          setRunning(false);
          setRunError(err.message);
        }
      }, POLL_MS);
    } catch (err) {
      setRunError(err.message);
    }
  };

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
        <div className="flex items-center gap-4">
          <button
            onClick={runDiscovery}
            disabled={running}
            className="bg-olive hover:bg-olive-dark disabled:bg-ink-faint text-cream font-mono text-[10px] tracking-widest px-4 py-1.5 rounded-sm transition-colors"
          >
            {running ? 'RUNNING…' : 'RUN DISCOVERY'}
          </button>
          <button
            onClick={() => setBrowseAll(!browseAll)}
            className="font-mono text-xs text-olive hover:text-olive-dark"
          >
            {browseAll ? '← Card view' : 'Browse all →'}
          </button>
        </div>
      </div>

      {runError && (
        <p className="font-mono text-[11px] text-red-500 mb-4 text-center">{runError}</p>
      )}
      <PipelineProgress status={jobStatus} />

      {!candidates.length ? (
        <p className="font-mono text-xs text-ink-faint">loading candidates…</p>
      ) : browseAll ? (
        <CandidateTable
          candidates={candidates}
          onSelect={(c) => setEvidenceId(c.id)}
          highlightIds={newIds}
        />
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
