export const DEFAULT_OFFER_WEIGHTS = {
  compensation: 25,
  growth: 25,
  workLife: 20,
  culture: 20,
  location: 10,
}

export const OFFER_DETAIL_DEFAULTS = {
  currency: 'CNY', decision_deadline: '', base_annual: 0, signing_bonus: 0, annual_bonus: 0,
  commission: 0, relocation: 0, equity_type: '', equity_total: 0,
  equity_years: 4, equity_discount: 50, benefits_annual: 0, perks_annual: 0,
  vacation_days: 0, remote_savings: 0, learning_budget: 0, tax_rate: 0,
  weekly_hours: 40, commute_minutes: 0, remote_policy: '',
  growth_score: 5, work_life_score: 5, culture_score: 5,
  location_score: 5, manager_score: 5, stability_score: 5,
  equity_notes: '', benefits_notes: '', role_scope: '', risks: '',
  red_flags: '', questions: '', negotiation: '', gut_feeling: '',
}

export function normalizeOfferDetails(value) {
  return { ...OFFER_DETAIL_DEFAULTS, ...(value && typeof value === 'object' ? value : {}) }
}

export function hasOfferInfo(record) {
  if (!record) return false
  const details = normalizeOfferDetails(record.offer_details)
  return Object.keys(OFFER_DETAIL_DEFAULTS).some(key => {
    const value = details[key]
    const fallback = OFFER_DETAIL_DEFAULTS[key]
    return typeof value === 'string' ? value.trim() !== String(fallback).trim() : Number(value) !== Number(fallback)
  })
}

function amount(value) {
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 0
}

export function calculateOffer(record) {
  const details = normalizeOfferDetails(record?.offer_details)
  const base = amount(details.base_annual)
  const signing = amount(details.signing_bonus)
  const bonus = amount(details.annual_bonus)
  const commission = amount(details.commission)
  const relocation = amount(details.relocation)
  const equityYears = Math.max(1, amount(details.equity_years) || 4)
  const equityDiscount = Math.min(100, Math.max(0, Number(details.equity_discount) || 0)) / 100
  const annualEquity = amount(details.equity_total) / equityYears * (1 - equityDiscount)
  const benefits = amount(details.benefits_annual)
  const perks = amount(details.perks_annual) + amount(details.remote_savings) + amount(details.learning_budget)
  let ongoing = base + bonus + commission + annualEquity + benefits + perks
  let yearOne = ongoing + signing + relocation
  const taxRate = Math.min(100, Math.max(0, Number(details.tax_rate) || 0)) / 100
  return {
    details, base, signing, bonus, commission, relocation, annualEquity, benefits, perks,
    yearOne, ongoing, fourYear: yearOne + ongoing * 3,
    netYearOne: yearOne * (1 - taxRate), netOngoing: ongoing * (1 - taxRate),
  }
}

export function weightedOfferScore(record, weights = DEFAULT_OFFER_WEIGHTS, compensationScore = 0) {
  const details = normalizeOfferDetails(record?.offer_details)
  const normalized = { ...DEFAULT_OFFER_WEIGHTS, ...weights }
  const totalWeight = Object.values(normalized).reduce((sum, value) => sum + Math.max(0, Number(value) || 0), 0) || 1
  const culture = (amount(details.culture_score) + amount(details.manager_score) + amount(details.stability_score)) / 3
  const factors = {
    compensation: compensationScore,
    growth: amount(details.growth_score),
    workLife: amount(details.work_life_score),
    culture,
    location: amount(details.location_score),
  }
  const score = Object.entries(normalized).reduce((sum, [key, weight]) => {
    return sum + (factors[key] || 0) * Math.max(0, Number(weight) || 0)
  }, 0) / totalWeight
  return { score, factors }
}

export function splitNotes(value) {
  return String(value || '').split(/[\n；;]/).map(item => item.trim()).filter(Boolean)
}
