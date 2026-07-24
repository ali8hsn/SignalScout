import { useState } from 'react';
import { useAdmin } from '../hooks/useAdmin.js';

// Discreet operator unlock. Locked by default (shows a small "operator" link);
// clicking prompts for the admin secret, which unlocks the spend/send controls
// for this browser only. Clicking again while unlocked clears it.
export default function AdminUnlock() {
  const { isAdmin, setAdminSecret } = useAdmin();
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState('');

  if (isAdmin) {
    return (
      <button
        type="button"
        onClick={() => setAdminSecret('')}
        title="Lock operator controls"
        className="font-mono text-[10px] tracking-widest text-olive hover:text-olive-dark"
      >
        OPERATOR ✓ · LOCK
      </button>
    );
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="font-mono text-[10px] tracking-widest text-ink-faint/60 hover:text-olive"
      >
        operator
      </button>
    );
  }

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        setAdminSecret(value.trim());
        setValue('');
        setOpen(false);
      }}
      className="flex items-center gap-1.5"
    >
      <input
        type="password"
        autoFocus
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder="admin secret"
        className="bg-cream border border-line rounded-sm px-2 py-1 font-mono text-[10px] w-32 focus:outline-none focus:border-olive"
      />
      <button
        type="submit"
        className="font-mono text-[10px] tracking-widest text-olive hover:text-olive-dark"
      >
        UNLOCK
      </button>
      <button
        type="button"
        onClick={() => { setOpen(false); setValue(''); }}
        className="font-mono text-[10px] tracking-widest text-ink-faint/60 hover:text-ink-soft"
      >
        ✕
      </button>
    </form>
  );
}
