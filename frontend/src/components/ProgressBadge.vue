<template>
  <span class="progress-badge" :style="{ background: color }">{{ progress }}</span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  progress: {
    type: String,
    required: true,
  },
})

const colorMap = {
  '已投递': 'var(--blue)',
  '机考': 'var(--amber)',
  '面试': 'var(--cyan)',
  'OC': 'var(--green)',
  'Offer': 'var(--green)',
  '已挂': 'var(--red)',
  '放弃': 'var(--red)',
}

const color = computed(() => colorMap[props.progress] || 'var(--muted)')
</script>

<style scoped>
.progress-badge {
  display: inline-block;
  padding: 2px 7px;
  border-radius: 4px;
  color: #fff;
  font-size: 11px;
  font-weight: 800;
  white-space: nowrap;
}
</style>
