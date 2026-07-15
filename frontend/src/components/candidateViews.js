export const CANDIDATE_VIEWS = [
  ['provider', 'Provider discoveries'],
  ['cross-source', 'Cross-source'],
  ['all', 'All candidates'],
];

export function filterCandidatesByView(candidates, view) {
  if (view === 'provider') {
    return candidates.filter((candidate) => candidate.discovery_origin === 'provider_search');
  }
  if (view === 'cross-source') {
    return candidates.filter((candidate) => (candidate.source_diversity || 0) >= 2);
  }
  return candidates;
}
