import { useEffect, useState } from 'react';

// Operator ("admin") unlock. The secret is kept only in localStorage and sent
// as the X-Admin-Secret header on operator-only calls (recipe approve/run,
// digest send/generate). Without it, those controls stay hidden so the public
// Cory-facing UI can't trigger provider spend or sends.
const KEY = 'ss_admin_secret';
const listeners = new Set();

export function getAdminSecret() {
  try {
    return localStorage.getItem(KEY) || '';
  } catch {
    return '';
  }
}

export function setAdminSecret(value) {
  try {
    if (value) localStorage.setItem(KEY, value);
    else localStorage.removeItem(KEY);
  } catch {
    // ignore storage errors (private mode) — controls simply stay locked
  }
  listeners.forEach((notify) => notify());
}

export function useAdmin() {
  const [secret, setSecret] = useState(getAdminSecret());
  useEffect(() => {
    const notify = () => setSecret(getAdminSecret());
    listeners.add(notify);
    return () => listeners.delete(notify);
  }, []);
  return { secret, isAdmin: Boolean(secret), setAdminSecret };
}
