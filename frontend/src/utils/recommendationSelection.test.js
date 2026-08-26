import test from 'node:test'
import assert from 'node:assert/strict'

import { applyRecommendationResult } from './recommendationSelection.js'

test('keeps current shared records only and sorts recommendations by score', () => {
  const shared = [
    { record_id: 'low', company: '当前低分公司', url: 'current-low', is_added: true },
    { record_id: 'high', company: '当前高分公司', url: 'current-high', is_added: false },
  ]
  const recommendations = [
    { record_id: 'low', company: '旧低分公司', recommendation_score: 65 },
    { record_id: 'deleted', recommendation_score: 99 },
    { record_id: 'high', company: '旧高分公司', recommendation_score: 92 },
  ]

  const result = applyRecommendationResult(shared, recommendations)

  assert.deepEqual(result.map(item => item.record_id), ['high', 'low'])
  assert.equal(result[0].url, 'current-high')
  assert.equal(result[1].is_added, true)
})
