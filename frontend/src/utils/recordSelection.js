export function normalizeRecordId(value) {
  return value === null || value === undefined ? '' : String(value)
}

export function parseRecordSelections(raw) {
  try {
    const value = JSON.parse(raw || '{}')
    if (!value || typeof value !== 'object' || Array.isArray(value)) return {}
    return Object.fromEntries(
      Object.entries(value)
        .map(([company, recordId]) => [company, normalizeRecordId(recordId)])
        .filter(([company, recordId]) => company && recordId),
    )
  } catch (_) {
    return {}
  }
}

const PROGRESS_RANK = {
  '未投递': 0,
  '已投递': 1,
  '机考': 2,
  '面试': 3,
  'OC': 4,
  '放弃': -1,
}

function recordProgress(record) {
  const value = record?.progress
  return String(Array.isArray(value) ? (value[0] || '') : (value || ''))
}

export function fastestActiveRecord(positions) {
  return (positions || []).reduce((fastest, record) => {
    if (recordProgress(record) === '已挂') return fastest
    if (!fastest) return record
    const rank = PROGRESS_RANK[recordProgress(record)] ?? 0
    const fastestRank = PROGRESS_RANK[recordProgress(fastest)] ?? 0
    return rank > fastestRank ? record : fastest
  }, null)
}

export function selectedRecord(positions, selectedId) {
  const normalizedId = normalizeRecordId(selectedId)
  const selected = positions.find(item => normalizeRecordId(item?.record_id) === normalizedId)
  if (selected && recordProgress(selected) !== '已挂') return selected
  return fastestActiveRecord(positions) || positions[0]
}
