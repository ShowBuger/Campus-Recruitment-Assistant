<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import $ from 'jquery'

const surface = ref(null)
const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)')
const bloomTimers = new Set()
let observer
let resizeObserver
let initialized = false
let loading = false

function enabled() {
  return document.documentElement.dataset.style === 'shuimo' && !reduceMotion.matches
}

async function start() {
  if (!surface.value || initialized || loading || !enabled()) return
  loading = true
  try {
    await import('jquery.ripples')
    if (!surface.value || !enabled()) return
    $(surface.value).ripples({
      imageUrl: '/static/themes/shuimo/monochrome-scroll-bg.png',
      resolution: 256,
      dropRadius: 15,
      perturbance: .018,
      interactive: false,
      crossOrigin: '',
    })
    initialized = true
    surface.value.classList.add('is-running')
  } catch (error) {
    surface.value?.classList.add('is-static')
    console.info('[shuimo-ripples] WebGL unavailable; using static background.', error)
  } finally {
    loading = false
  }
}

function stop() {
  for (const timer of bloomTimers) clearTimeout(timer)
  bloomTimers.clear()
  if (initialized && surface.value) {
    try { $(surface.value).ripples('destroy') } catch (_) { /* already removed */ }
  }
  initialized = false
  surface.value?.classList.remove('is-running')
}

function sync() {
  if (enabled()) start()
  else stop()
}

function drop(x, y, radius, strength) {
  if (!initialized || !surface.value) return
  try { $(surface.value).ripples('drop', x, y, radius, strength) } catch (_) { stop() }
}

function bloom(event) {
  if (!initialized || !enabled()) return
  const { x, y, radius = 10, strength = .014, seed = .5 } = event.detail || {}
  if (!Number.isFinite(x) || !Number.isFinite(y)) return
  drop(x, y, radius * .9, strength)
  const timer = setTimeout(() => {
    bloomTimers.delete(timer)
    drop(x + (seed - .5) * 8, y + (.5 - seed) * 5, radius * 1.42, strength * .48)
  }, 88 + seed * 42)
  bloomTimers.add(timer)
}

function onPointerDown(event) {
  if (enabled()) drop(event.clientX, event.clientY, 21, .026)
}

function onVisibilityChange() {
  if (!initialized || !surface.value) return
  try { $(surface.value).ripples(document.hidden ? 'pause' : 'play') } catch (_) { stop() }
}

onMounted(() => {
  observer = new MutationObserver(sync)
  observer.observe(document.documentElement, {
    attributes: true,
    attributeFilter: ['data-style'],
  })
  resizeObserver = new ResizeObserver(() => {
    if (!initialized || !surface.value) return
    try { $(surface.value).ripples('updateSize') } catch (_) { stop() }
  })
  resizeObserver.observe(document.documentElement)
  window.addEventListener('shuimo-ink-bloom', bloom)
  window.addEventListener('pointerdown', onPointerDown, { passive: true })
  document.addEventListener('visibilitychange', onVisibilityChange)
  reduceMotion.addEventListener?.('change', sync)
  sync()
})

onUnmounted(() => {
  observer?.disconnect()
  resizeObserver?.disconnect()
  window.removeEventListener('shuimo-ink-bloom', bloom)
  window.removeEventListener('pointerdown', onPointerDown)
  document.removeEventListener('visibilitychange', onVisibilityChange)
  reduceMotion.removeEventListener?.('change', sync)
  stop()
})
</script>

<template>
  <div ref="surface" class="shuimo-ripple-surface" aria-hidden="true"></div>
</template>
