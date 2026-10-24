export function applyRecommendationResult(sharedRecords, recommendationItems) {
  const sharedById = new Map(
    (sharedRecords || []).map(record => [record.record_id, record]),
  )
  return (recommendationItems || [])
    .map(recommendation => {
      const shared = sharedById.get(recommendation.record_id)
      return shared ? { ...recommendation, ...shared } : null
    })
    .filter(Boolean)
    .sort((left, right) => (
      Number(right.recommendation_score || 0) - Number(left.recommendation_score || 0)
    ))
}
