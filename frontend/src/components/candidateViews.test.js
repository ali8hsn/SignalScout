import assert from 'node:assert/strict';
import test from 'node:test';

import { filterCandidatesByView } from './candidateViews.js';

const candidates = [
  { id: 'provider', discovery_origin: 'provider_search', source_diversity: 1 },
  { id: 'cross', discovery_origin: 'github', source_diversity: 2 },
  { id: 'legacy', discovery_origin: 'github', source_diversity: 1 },
];

test('provider view uses persisted discovery origin', () => {
  assert.deepEqual(
    filterCandidatesByView(candidates, 'provider').map((candidate) => candidate.id),
    ['provider'],
  );
});

test('cross-source view requires two independent sources', () => {
  assert.deepEqual(
    filterCandidatesByView(candidates, 'cross-source').map((candidate) => candidate.id),
    ['cross'],
  );
});

test('all view preserves the complete cohort', () => {
  assert.equal(filterCandidatesByView(candidates, 'all').length, 3);
});
