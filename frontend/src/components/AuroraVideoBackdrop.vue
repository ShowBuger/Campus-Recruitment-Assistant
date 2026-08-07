<script setup>
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { getAuroraVideoUrl, restoreAuroraResource } from '@/utils/skinResources'

const video = ref(null)
const isAurora = ref(document.documentElement.dataset.style === 'aurora')
const isReady = ref(false)
const hasError = ref(false)
const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)')
const videoSource = ref(getAuroraVideoUrl())
let styleObserver

async function syncPlayback() {
  await nextTick()
  if (!video.value) return
  if (!isAurora.value || reduceMotion.matches) {
    video.value.pause()
    return
  }
  video.value.play().catch(() => {
    // Muted inline video is normally allowed; the first user gesture retries it.
  })
}

function syncStyle() {
  isAurora.value = document.documentElement.dataset.style === 'aurora'
  syncPlayback()
}

function retryPlayback() {
  if (isAurora.value && !reduceMotion.matches) syncPlayback()
}

async function syncResource(event) {
  videoSource.value = event?.detail?.videoUrl || getAuroraVideoUrl()
  isReady.value = false
  hasError.value = false
  await nextTick()
  video.value?.load()
  syncPlayback()
}

watch(isAurora, active => {
  if (!active) {
    isReady.value = false
    hasError.value = false
  }
})

onMounted(async () => {
  styleObserver = new MutationObserver(syncStyle)
  styleObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['data-style'] })
  reduceMotion.addEventListener?.('change', syncPlayback)
  window.addEventListener('pointerdown', retryPlayback, { passive: true })
  window.addEventListener('aurora-resource-ready', syncResource)
  if (!videoSource.value && await restoreAuroraResource()) videoSource.value = getAuroraVideoUrl()
  syncPlayback()
})

onUnmounted(() => {
  styleObserver?.disconnect()
  reduceMotion.removeEventListener?.('change', syncPlayback)
  window.removeEventListener('pointerdown', retryPlayback)
  window.removeEventListener('aurora-resource-ready', syncResource)
})
</script>

<template>
  <div
    v-if="isAurora"
    class="aurora-video-backdrop"
    :class="{ 'is-ready': isReady, 'has-error': hasError }"
    aria-hidden="true"
  >
    <video
      v-if="videoSource"
      ref="video"
      muted
      loop
      playsinline
      preload="auto"
      :autoplay="!reduceMotion.matches"
      @canplay="isReady = true; syncPlayback()"
      @error="hasError = true"
    >
      <source :src="videoSource" type="video/mp4">
    </video>
  </div>
</template>
