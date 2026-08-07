'use strict'

const test = require('node:test')
const assert = require('node:assert/strict')
const { externalUrlFromNavigation, isAppUrl, normalizeHttpUrl } = require('./url-routing')

const appOrigin = 'https://www.toudimianban.cloud'

test('normalizes bare domains with and without www', () => {
  assert.equal(normalizeHttpUrl('jobs.bytedance.com/campus'), 'https://jobs.bytedance.com/campus')
  assert.equal(normalizeHttpUrl('www.example.com/jobs?id=2'), 'https://www.example.com/jobs?id=2')
})

test('keeps complete HTTP URLs and rejects unsafe or internal paths', () => {
  assert.equal(normalizeHttpUrl('https://career.huawei.com/reccampportal/portal5/index.html'), 'https://career.huawei.com/reccampportal/portal5/index.html')
  assert.equal(normalizeHttpUrl('/records'), null)
  assert.equal(normalizeHttpUrl('javascript:alert(1)'), null)
})

test('distinguishes application and external origins', () => {
  assert.equal(isAppUrl(`${appOrigin}/records`, appOrigin), true)
  assert.equal(isAppUrl('https://jobs.example.com', appOrigin), false)
  assert.equal(externalUrlFromNavigation('https://jobs.example.com/campus', appOrigin), 'https://jobs.example.com/campus')
  assert.equal(externalUrlFromNavigation(`${appOrigin}/records`, appOrigin), null)
})

test('recovers a bare domain that Chromium resolved on the app origin', () => {
  assert.equal(
    externalUrlFromNavigation(`${appOrigin}/jobs.example.com/campus?source=board`, appOrigin),
    'https://jobs.example.com/campus?source=board',
  )
})
