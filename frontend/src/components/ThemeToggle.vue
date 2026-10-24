<template>
  <button class="icon-btn" @click="toggle" :title="isDark ? '切换到亮色' : '切换到暗色'">
    {{ isDark ? '☀️' : '🌙' }}
  </button>
</template>

<script setup>
import { ref } from 'vue'

const isDark = ref(false)

function init() {
  isDark.value = localStorage.getItem('radar_theme') === 'dark'
  apply()
}

function toggle() {
  isDark.value = !isDark.value
  apply()
  localStorage.setItem('radar_theme', isDark.value ? 'dark' : 'light')
}

function apply() {
  document.documentElement.dataset.theme = isDark.value ? 'dark' : 'light'
}

init()
</script>
