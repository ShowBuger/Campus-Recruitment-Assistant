<template>
  <span ref="wrap" class="tip-cell" @mouseenter="onEnter" @mouseleave="onLeave" @mousemove="onMove">
    <span class="tip-text">{{ text }}</span>
  </span>
  <Teleport to="body" v-if="show">
    <div class="px-tip-box" :style="{ left: x + 'px', top: y + 'px' }">{{ tip || text }}</div>
  </Teleport>
</template>

<script setup>
import { ref, nextTick } from 'vue'

defineProps({ text: { type: String, default: '' }, tip: { type: String, default: '' } })
const wrap = ref(null)
const show = ref(false)
const x = ref(0)
const y = ref(0)

function onEnter(e) {
  nextTick(() => {
    if (wrap.value) {
      const el = wrap.value.firstChild  // .tip-text
      if (el && el.scrollWidth > el.clientWidth) {
        show.value = true
        x.value = e.clientX + 10; y.value = e.clientY + 10
      }
    }
  })
}
function onLeave() { show.value = false }
function onMove(e) { if (show.value) { x.value = e.clientX + 10; y.value = e.clientY + 10 } }
</script>

<style scoped>
.tip-cell { display: block; overflow: hidden }
.tip-text { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap }
</style>

<style>
.px-tip-box {
  position: fixed; z-index: 99999; pointer-events: none;
  padding: 4px 8px; max-width: 480px;
  background: var(--ink); color: var(--bg);
  font-family: var(--mono); font-size: 11px; font-weight: 700;
  line-height: 1.4; white-space: normal; word-break: break-word;
  border: 2px solid var(--line); border-radius: 0;
  box-shadow: 3px 3px 0 rgba(0,0,0,.18);
}
</style>
