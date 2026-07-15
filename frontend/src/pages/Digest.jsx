import { useEffect, useState } from 'react';
import { api } from '../api/client.js';
import ContactLinks from '../components/ContactLinks.jsx';

export default function Digest() {
  const [digest, setDigest] = useState(null);
  const [email, setEmail] = useState('');
  const [loadState, setLoadState] = useState('loading');
  const [error, setError] = useState('');

  const loadLatest = () => {
    setLoadState('loading');
    setError('');
    api.digestPreview(email)
      .then((d) => {
        setDigest(d);
        setLoadState('success');
      })
      .catch(() => {
        setLoadState('error');
        setError('The latest digest could not be loaded. Try again in a moment.');
      });
  };

  useEffect(loadLatest, []);

  return (
    <div className="max-w-2xl mx-auto">
      <div className="flex items-end justify-between mb-6">
        <div>
          <h2 className="font-display text-3xl">
            {digest ? `${digest.candidate_count} people in the next digest` : 'Next digest preview'}
          </h2>
          <p className="label-mono mt-1.5">
            Exact approved, contactable, never-sent candidates · previewing does not record sends
          </p>
        </div>
        <button onClick={loadLatest} className="border border-olive text-olive font-mono text-xs px-4 py-2 rounded-sm">
          REFRESH
        </button>
      </div>

      <div className="flex gap-2 mb-5">
        <input
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="Subscriber email (if no owner default)"
          className="flex-1 bg-card border border-line rounded-sm px-3 py-2 text-sm"
        />
        <button onClick={loadLatest} className="bg-olive text-cream font-mono text-xs px-4 rounded-sm">PREVIEW</button>
      </div>

      {error && (
        <div role="alert" className="border border-red-300 bg-red-50 rounded-sm px-4 py-3 mb-5">
          <p className="text-sm text-red-700">{error}</p>
          {loadState === 'error' && (
            <button onClick={loadLatest} className="font-mono text-[10px] tracking-widest text-red-700 underline mt-1">
              TRY AGAIN
            </button>
          )}
        </div>
      )}

      {loadState === 'loading' && (
        <p className="text-ink-faint italic">Loading the latest digest…</p>
      )}
      {loadState === 'success' && !digest && (
        <div className="bg-card border border-line rounded-md px-6 py-8 text-center">
          <p className="font-display text-xl">No approved unsent candidates remain.</p>
        </div>
      )}

      {digest?.source_mix && (
        <p className="font-mono text-[11px] text-ink-faint mb-4">
          SOURCE MIX · {Object.entries(digest.source_mix).map(([key, count]) => `${key.replaceAll('_', ' ')} ${count}`).join(' · ')}
        </p>
      )}
      {digest?.candidates.map((entry, i) => (
        <div key={entry.id} className="bg-card border border-line rounded-md px-7 py-6 mb-4">
          <div className="flex items-start justify-between">
            <span className="font-mono text-[11px] text-olive">#{String(i + 1).padStart(3, '0')}</span>
            <span className="font-mono text-sm text-olive">score {Math.round(entry.score)}</span>
          </div>
          <h3 className="font-display text-2xl mt-1">{entry.name}</h3>
          <p className="font-mono text-[11px] text-ink-faint mt-0.5">
            {[entry.school, entry.current_location || entry.origin_location].filter(Boolean).join(' · ')}
          </p>
          <p className="text-[15px] text-ink leading-relaxed mt-3">{entry.why_now}</p>
          <div className="flex flex-wrap gap-2 mt-3">
            {entry.top_signals.map((signal, j) => (
              <span key={j} className="border border-line rounded-sm px-2.5 py-1 font-mono text-[10.5px] text-ink-soft">{signal.summary}</span>
            ))}
          </div>
          {entry.connection_context && (
            <p className="text-[13px] text-ink-soft mt-3">
              <span className="font-mono text-[10px] uppercase tracking-widest text-olive mr-2">orbit</span>
              {entry.connection_context}
            </p>
          )}
          {entry.warm_intro && (
            <p className="text-[13px] text-ink-soft mt-1">
              <span className="font-mono text-[10px] uppercase tracking-widest text-olive mr-2">intro</span>
              {entry.warm_intro}
            </p>
          )}
          <ContactLinks links={entry.contact_links} className="mt-4 pt-3 border-t border-dashed border-line" />
        </div>
      ))}
    </div>
  );
}
