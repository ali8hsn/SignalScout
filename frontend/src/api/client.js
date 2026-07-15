async function request(path, options = {}) {
  const resp = await fetch(path, options);
  if (!resp.ok) {
    let detail = `${resp.status} ${resp.statusText}`;
    try {
      const body = await resp.json();
      if (body && body.detail) detail = body.detail;
    } catch {
      // non-JSON error body — keep the status line
    }
    const err = new Error(detail);
    err.status = resp.status;
    throw err;
  }
  return resp.json();
}

export const api = {
  overview: () => request('/api/overview'),
  candidates: (cohort = 'discovery') => request(`/api/candidates?cohort=${cohort}`),
  candidate: (id) => request(`/api/candidates/${id}`),
  backtest: () => request('/api/backtest'),
  concentrations: () => request('/api/concentrations'),
  subscribe: (payload) => request('/api/subscribers', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }),
  pageView: (payload) => request('/api/analytics/page-view', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }),
};
