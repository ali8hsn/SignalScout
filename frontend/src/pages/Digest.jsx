import { useEffect, useState } from 'react';
import { api } from '../api/client.js';
import ContactLinks from '../components/ContactLinks.jsx';

export default function Digest() {
  const [digest, setDigest] = useState(null);
  const [busy, setBusy] = useState(false);
  const [sendReceipt, setSendReceipt] = useState(null);

  useEffect(() => {
    api.latestDigest().then((d) => setDigest(d.digest)).catch(console.error);
  }, []);

  const generate = async () => {
    setBusy(true);
    setSendReceipt(null);
    try {
      const d = await api.generateDigest();
      setDigest(d.digest);
    } finally {
      setBusy(false);
    }
  };

  const send = async () => {
    const d = await api.sendDigest();
    setSendReceipt(d.receipt);
  };

  return (
    <div className="max-w-2xl mx-auto">
      <div className="flex items-end justify-between mb-6">
        <div>
          <h2 className="font-display text-3xl">
            {digest ? `${digest.entries.length} people you should know` : 'The digest'}
          </h2>
          <p className="label-mono mt-1.5">
            {digest ? digest.generated_at.slice(0, 10) : 'not generated yet'} · every entry has verified contact info
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={generate}
            disabled={busy}
            className="bg-olive hover:bg-olive-dark disabled:opacity-50 text-cream font-mono text-xs px-4 py-2 rounded-sm"
          >
            {busy ? 'GENERATING…' : digest ? 'REGENERATE' : 'GENERATE'}
          </button>
          <button
            onClick={send}
            disabled={!digest}
            className="border border-line text-ink-faint font-mono text-xs px-4 py-2 rounded-sm hover:border-olive hover:text-olive disabled:opacity-40"
            title="Send is stubbed — preview only"
          >
            SEND (PREVIEW)
          </button>
        </div>
      </div>

      {sendReceipt && (
        <p className="font-mono text-[11px] text-olive border border-olive/40 rounded-sm px-3 py-2 mb-5">
          {sendReceipt.note}
        </p>
      )}

      {!digest && <p className="text-ink-faint italic">Generate the digest to see this week's discoveries.</p>}

      {digest?.entries.map((entry, i) => (
        <div key={entry.person_id} className="bg-card border border-line rounded-md px-7 py-6 mb-4">
          <div className="flex items-start justify-between">
            <span className="font-mono text-[11px] text-olive">#{String(i + 1).padStart(3, '0')}</span>
            <span className="font-mono text-xl text-olive">{Math.round(entry.score)}</span>
          </div>
          <h3 className="font-display text-2xl mt-1">{entry.name}</h3>
          <p className="font-mono text-[11px] text-ink-faint mt-0.5">
            {entry.school_line}{entry.location_line ? ` · ${entry.location_line}` : ''}
          </p>
          <p className="text-[14px] text-ink-soft leading-relaxed mt-3">{entry.thesis}</p>
          <div className="flex flex-wrap gap-2 mt-3">
            {entry.top_signals.map((t, j) => (
              <span key={j} className="border border-line rounded-sm px-2.5 py-1 font-mono text-[10.5px] text-ink-soft">{t}</span>
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
          {entry.why_now && (
            <p className="text-[13px] mt-3 pl-3 border-l-2 border-olive text-ink-soft">{entry.why_now}</p>
          )}
          <ContactLinks links={entry.contact_links} className="mt-4 pt-3 border-t border-dashed border-line" />
        </div>
      ))}
    </div>
  );
}
