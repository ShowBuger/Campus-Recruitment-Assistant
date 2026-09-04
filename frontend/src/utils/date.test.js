import test from 'node:test'
import assert from 'node:assert/strict'

import { boardDwellChina, calendarDateChina } from './date.js'

test('calendarDateChina parses a local event date string without dropping it', () => {
  const date = calendarDateChina('2026-08-29')

  assert.ok(date instanceof Date)
  assert.equal(date.getFullYear(), 2026)
  assert.equal(date.getMonth(), 7)
  assert.equal(date.getDate(), 29)
})

test('calendarDateChina still groups UTC+8 midnight timestamps correctly', () => {
  const chinaMidnight = Date.parse('2026-08-29T00:00:00+08:00')
  const date = calendarDateChina(chinaMidnight)

  assert.equal(date.getFullYear(), 2026)
  assert.equal(date.getMonth(), 7)
  assert.equal(date.getDate(), 29)
})

test('calendarDateChina rejects invalid values', () => {
  assert.equal(calendarDateChina('not-a-date'), null)
})

test('boardDwellChina keeps showing exact days after one month', () => {
  const today = new Date()
  const entered = new Date(today.getFullYear(), today.getMonth(), today.getDate() - 45)
  const chinaMidnight = Date.UTC(entered.getFullYear(), entered.getMonth(), entered.getDate()) - 8 * 3600000

  assert.deepEqual(boardDwellChina(chinaMidnight), { text: '45 天', days: 45 })
})
