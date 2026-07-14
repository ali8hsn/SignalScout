import { useEffect, useState } from 'react';
import { api } from '../api/client.js';
import EvidencePanel from '../components/EvidencePanel.jsx';
import ScoreDistribution from '../components/ScoreDistribution.jsx';

function Metric({ label, value, detail }) {
  return (
    <div className="bg-card border border-line rounded-md px-6 py-5">
      <p className="label-mono">{label}</p>
      <p className="font-mono text-4xl text-olive mt-2">{value}</p>
      {detail && <p className="text-[12px] text-ink-faint mt-1.5">{detail}</p>}
    </div>
  );
}

export default function Backtest() {
  const [report, setReport] = useState(null);
  const [evidenceId, setEvidenceId] = useState(null);

  useEffect(() => {
    api.backtest().then(setReport).catch(console.error);
  }, []);

  if (!report) return <p className="font-mono text-xs text-ink-faint">running backtest…</p>;

  return (
    <div>
      <p className="font-display text-2xl mb-1">
        Would have flagged <span className="text-olive">{report.recall_pct}%</span> of known founders{' '}
        <span className="text-olive">{report.avg_lead_months} months</span> before their breakout.
      </p>
      <p className="text-[13px] text-ink-faint mb-8 italic">
        Scored on pre-breakout evidence only, against {report.controls_total} control CS students at a {report.false_positive_pct}% false-positive rate.
      </p>

      <div className="grid grid-cols-4 gap-4 mb-8">
        <Metric label="recall" value={`${report.recall_pct}%`} detail={`${report.founders_flagged} of ${report.founders_total} founders`} />
        <Metric label="avg lead time" value={`${report.avg_lead_months}mo`} detail="before the world noticed" />
        <Metric label="false positives" value={`${report.false_positive_pct}%`} detail={`${report.false_positives} of ${report.controls_total} controls`} />
        <Metric label="pre-connected" value={report.flagged_with_seed_connection} detail="flagged founders already in a seed's orbit" />
      </div>

      <div className="grid grid-cols-2 gap-6 mb-8">
        <div>
          <h3 className="label-mono mb-3">score distribution — founders vs controls</h3>
          <ScoreDistribution
            founderScores={report.founder_scores}
            controlScores={report.control_scores}
            threshold={report.threshold}
          />
        </div>
        <div>
          <h3 className="label-mono mb-3">most predictive signal types</h3>
          <div className="bg-card border border-line rounded-md p-6 space-y-2.5">
            {report.top_signal_types.map((row) => {
              const max = report.top_signal_types[0].points;
              return (
                <div key={row.signal_type} className="flex items-center gap-3">
                  <span className="font-mono text-[11px] w-44 text-ink-soft">{row.signal_type}</span>
                  <div className="flex-1 h-3 bg-line-soft rounded-sm overflow-hidden">
                    <div className="h-full bg-olive" style={{ width: `${(row.points / max) * 100}%` }} />
                  </div>
                  <span className="font-mono text-[11px] text-ink-faint w-12 text-right">{row.points}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      <h3 className="label-mono mb-3">per-founder results (pre-breakout evidence only)</h3>
      <div className="bg-card border border-line rounded-md overflow-hidden">
        <table className="w-full text-[13px]">
          <thead>
            <tr className="border-b border-line">
              {['Score', 'Name', 'Flagged', 'Lead (months)', 'Seed connection', 'Fellowship'].map((h) => (
                <th key={h} className="text-left px-4 py-2.5 label-mono">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {report.results.map((r) => (
              <tr
                key={r.person_id}
                onClick={() => setEvidenceId(r.person_id)}
                className="border-b border-line-soft last:border-0 hover:bg-cream cursor-pointer"
              >
                <td className="px-4 py-2 font-mono text-olive">{r.score.toFixed(1)}</td>
                <td className="px-4 py-2 font-display text-[15px]">{r.name}</td>
                <td className="px-4 py-2 font-mono">{r.flagged ? <span className="text-olive">YES</span> : <span className="text-ink-faint">no</span>}</td>
                <td className="px-4 py-2 font-mono">{r.lead_months ?? '—'}</td>
                <td className="px-4 py-2 font-mono">{r.had_seed_connection ? 'Y' : '—'}</td>
                <td className="px-4 py-2 text-ink-soft">{r.fellowship || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {evidenceId && <EvidencePanel personId={evidenceId} onClose={() => setEvidenceId(null)} />}
    </div>
  );
}
