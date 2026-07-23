import { useCallback, useEffect, useState } from 'react';

// Small shared helper for the fetch/loading/error/reload pattern the tab pages
// all repeated. `loader` is an async function returning the data to store; the
// hook tracks a 'loading' | 'success' | 'error' state and exposes a `reload`.
export function useAsyncData(loader) {
  const [data, setData] = useState(null);
  const [state, setState] = useState('loading');

  const reload = useCallback(() => {
    setState('loading');
    return Promise.resolve()
      .then(loader)
      .then((result) => {
        setData(result);
        setState('success');
        return result;
      })
      .catch((error) => {
        setState('error');
        throw error;
      });
    // `loader` is expected to be a stable reference (defined at module or
    // component top level); callers that close over changing values should
    // trigger a manual `reload()`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    reload().catch(() => {});
  }, [reload]);

  return { data, state, reload, setData };
}
