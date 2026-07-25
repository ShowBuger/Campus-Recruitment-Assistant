<template>
  <span class="tip-wrap" @mouseenter="onEnter" @mouseleave="onLeave" @mousemove="onMove">
    <span class="tip-text">{{ text }}</span>
    <Teleport to="body">
      <div v-if="show" class="px-tip-box" :style="{ left: x + 'px', top: y + 'px' }">{{ tip || text }}</div>
    </Teleport>
  </span>
</template>

<script setup>
import { ref } from 'vue'

defineProps({ text: { type: String, default: '' }, tip: { type: String, default: '' } })
const show = ref(false)
const x = ref(0)
const y = ref(0)

function onEnter(e) { show.value = true; x.value = e.clientX + 10; y.value = e.clientY + 10 }
function onLeave() { show.value = false }
function onMove(e) { if (show.value) { x.value = e.clientX + 10; y.value = e.clientY + 10 } }
</script>

<style scoped>
.tip-wrap { display: block; max-width: 100% }
.tip-text { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap }
</style>

<style>
.px-tip-box {
  position: fixed; z-index: 99999; pointer-events: none;
  padding: 4px 8px; max-width: 360px;
  background: var(--ink); color: var(--bg);
  font-family: var(--mono); font-size: 11px; font-weight: 700;
  line-height: 1.3; white-space: nowrap;
  border: 2px solid var(--line); border-radius: 0;
  box-shadow: 3px 3px 0 rgba(0,0,0,.18);
  overflow: hidden; text-overflow: ellipsis;
}
</style>
