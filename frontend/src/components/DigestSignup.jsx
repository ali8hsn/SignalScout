import { useState } from 'react';
import { api } from '../api/client.js';

const EMPTY_FORM = {
  email: '',
  frequency: 'daily',
  signalInterests: '',
  seedAccounts: '',
};

export default function DigestSignup() {
  const [form, setForm] = useState(EMPTY_FORM);
  const [status, setStatus] = useState('idle');
  const [message, setMessage] = useState('');

  const update = (field) => (event) => {
    setForm((current) => ({ ...current, [field]: event.target.value }));
    if (status === 'error') setStatus('idle');
  };

  const submit = async (event) => {
    event.preventDefault();
    if (!form.email.trim()) {
      setStatus('error');
      setMessage('Add an email address to join the digest.');
      return;
    }
    setStatus('loading');
    setMessage('');
    try {
      const result = await api.subscribe({
        email: form.email.trim(),
        frequency: form.frequency,
        signal_interests: form.signalInterests.trim(),
        seed_accounts: form.seedAccounts.trim(),
      });
      setStatus('success');
      setMessage(result.message);
    } catch {
      setStatus('error');
      setMessage('We could not save your signup. Check the email and try again.');
    }
  };

  if (status === 'success') {
    return (
      <section className="bg-olive text-cream border border-olive-dark rounded-md px-6 py-5 mb-8">
        <p className="font-mono text-[10px] tracking-widest uppercase text-cream/70">Digest confirmed</p>
        <h2 className="font-display text-2xl mt-1">Early signals, delivered.</h2>
        <p className="text-sm mt-2 text-cream/90">{message}</p>
        <button
          type="button"
          onClick={() => {
            setForm(EMPTY_FORM);
            setStatus('idle');
          }}
          className="font-mono text-[10px] tracking-widest underline mt-3"
        >
          USE ANOTHER EMAIL
        </button>
      </section>
    );
  }

  return (
    <section className="bg-card border border-olive/60 rounded-md px-6 py-5 mb-8">
      <div className="mb-4">
        <p className="font-mono text-[10px] tracking-widest uppercase text-olive">Signal Scout digest</p>
        <h2 className="font-display text-2xl mt-1">Meet exceptional people before breakout.</h2>
        <p className="text-sm text-ink-soft mt-1">
          Get evidence-backed candidates with exact signals and direct profile links.
        </p>
      </div>
      <form onSubmit={submit} className="grid gap-3">
        <div className="grid sm:grid-cols-[1fr_150px] gap-3">
          <label>
            <span className="label-mono block mb-1">Email</span>
            <input
              type="email"
              value={form.email}
              onChange={update('email')}
              placeholder="you@firm.com"
              autoComplete="email"
              disabled={status === 'loading'}
              className="w-full bg-cream border border-line rounded-sm px-3 py-2 text-sm focus:outline-none focus:border-olive"
            />
          </label>
          <label>
            <span className="label-mono block mb-1">Frequency</span>
            <select
              value={form.frequency}
              onChange={update('frequency')}
              disabled={status === 'loading'}
              className="w-full bg-cream border border-line rounded-sm px-3 py-2 text-sm focus:outline-none focus:border-olive"
            >
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
            </select>
          </label>
        </div>
        <label>
          <span className="label-mono block mb-1">Signals you care about · optional</span>
          <input
            value={form.signalInterests}
            onChange={update('signalInterests')}
            placeholder="AI research, open source traction, hackathon wins"
            disabled={status === 'loading'}
            className="w-full bg-cream border border-line rounded-sm px-3 py-2 text-sm focus:outline-none focus:border-olive"
          />
        </label>
        <label>
          <span className="label-mono block mb-1">Seed accounts · optional, comma-separated</span>
          <input
            value={form.seedAccounts}
            onChange={update('seedAccounts')}
            placeholder="https://x.com/example, https://linkedin.com/in/example"
            disabled={status === 'loading'}
            className="w-full bg-cream border border-line rounded-sm px-3 py-2 text-sm focus:outline-none focus:border-olive"
          />
        </label>
        <div className="flex flex-col sm:flex-row sm:items-center gap-3">
          <button
            type="submit"
            disabled={status === 'loading'}
            className="bg-olive hover:bg-olive-dark disabled:bg-ink-faint text-cream font-mono text-[10px] tracking-widest px-5 py-2.5 rounded-sm"
          >
            {status === 'loading' ? 'SIGNING UP…' : 'JOIN THE DIGEST'}
          </button>
          {status === 'error' && (
            <p role="alert" className="font-mono text-[11px] text-red-600">{message}</p>
          )}
        </div>
      </form>
    </section>
  );
}
