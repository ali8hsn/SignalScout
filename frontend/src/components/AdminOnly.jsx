import { useAdmin } from '../hooks/useAdmin.js';

// Renders its children only when the operator secret is unlocked. Used to hide
// spend/send controls (recipe approve/run, digest send/generate) from the
// public product surface.
export default function AdminOnly({ children }) {
  const { isAdmin } = useAdmin();
  return isAdmin ? children : null;
}
