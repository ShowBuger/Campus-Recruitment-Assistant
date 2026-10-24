import test from 'node:test'
import assert from 'node:assert/strict'
import { calculateOffer, hasOfferInfo, weightedOfferScore } from './offerComparison.js'

test('calculateOffer includes first-year cash, discounted equity, benefits and perks', () => {
  const result = calculateOffer({ offer_details: {
    base_annual: 240000, signing_bonus: 20000, annual_bonus: 30000,
    equity_total: 200000, equity_years: 4, equity_discount: 50,
    benefits_annual: 10000, perks_annual: 5000,
  } })
  assert.equal(result.annualEquity, 25000)
  assert.equal(result.ongoing, 310000)
  assert.equal(result.yearOne, 330000)
  assert.equal(result.fourYear, 1260000)
})

test('hasOfferInfo recognizes structured offers', () => {
  assert.equal(hasOfferInfo({ offer_details: { signing_bonus: 10000 } }), true)
  assert.equal(hasOfferInfo({ offer_details: {} }), false)
})

test('weightedOfferScore follows user priorities', () => {
  const result = weightedOfferScore({ offer_details: {
    growth_score: 9, work_life_score: 5, culture_score: 6,
    manager_score: 6, stability_score: 6, location_score: 7,
  } }, { compensation: 0, growth: 100, workLife: 0, culture: 0, location: 0 }, 2)
  assert.equal(result.score, 9)
})
