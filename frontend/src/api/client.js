async function request(path, options) {
  const resp = await fetch(path, options);
  if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);
  return resp.json();
}

export const api = {
  overview: () => request('/api/overview'),
  candidates: (cohort = 'discovery') => request(`/api/candidates?cohort=${cohort}`),
  candidate: (id) => request(`/api/candidates/${id}`),
  backtest: () => request('/api/backtest'),
  concentrations: () => request('/api/concentrations'),
  latestDigest: () => request('/api/digests/latest'),
  generateDigest: () => request('/api/digests/generate', { method: 'POST' }),
  sendDigest: () => request('/api/digests/send', { method: 'POST' }),
};
