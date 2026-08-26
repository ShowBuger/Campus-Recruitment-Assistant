import test from 'node:test'
import assert from 'node:assert/strict'

import { parseRecordSelections, selectedRecord } from './recordSelection.js'

test('restores a selected child record when a legacy numeric id becomes a string', () => {
  const saved = parseRecordSelections('{"示例公司":42}')
  const positions = [{ record_id: '41' }, { record_id: '42' }]

  assert.equal(selectedRecord(positions, saved['示例公司']).record_id, '42')
})

test('falls back safely when the saved child record no longer exists', () => {
  const positions = [{ record_id: 'new-record', progress: ['已投递'] }]

  assert.equal(selectedRecord(positions, 'deleted-record').record_id, 'new-record')
})

test('defaults to the fastest active child record', () => {
  const positions = [
    { record_id: 'applied', progress: ['已投递'] },
    { record_id: 'interview', progress: ['面试'] },
    { record_id: 'exam', progress: ['机考'] },
  ]

  assert.equal(selectedRecord(positions, '').record_id, 'interview')
})

test('replaces a selected rejected child with the fastest active child', () => {
  const positions = [
    { record_id: 'rejected', progress: ['已挂'] },
    { record_id: 'exam', progress: ['机考'] },
    { record_id: 'offer', progress: ['OC'] },
  ]

  assert.equal(selectedRecord(positions, 'rejected').record_id, 'offer')
})

test('keeps an explicitly selected active child record', () => {
  const positions = [
    { record_id: 'applied', progress: ['已投递'] },
    { record_id: 'offer', progress: ['OC'] },
  ]

  assert.equal(selectedRecord(positions, 'applied').record_id, 'applied')
})
