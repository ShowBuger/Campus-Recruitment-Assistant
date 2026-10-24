import test from 'node:test'
import assert from 'node:assert/strict'
import { navigationItems } from './navigation.js'

test('desktop and sidebar navigation include every user-facing page', () => {
  const routes = navigationItems(false).map(item => item.to)

  assert.deepEqual(routes, [
    '/',
    '/board',
    '/records',
    '/resumes',
    '/analysis',
    '/notes',
    '/salary',
    '/offer-comparison',
  ])
})

test('admin navigation is appended only for administrators', () => {
  assert.equal(navigationItems(false).some(item => item.to === '/admin'), false)
  assert.equal(navigationItems(true).at(-1).to, '/admin')
})
