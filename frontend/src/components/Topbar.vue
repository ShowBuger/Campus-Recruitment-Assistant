<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const titleMap = {
  dashboard: '投递信息',
  board: '投递看板',
  records: '总表信息',
  resumes: '简历管理',
  analysis: '简历分析',
  admin: '管理页面'
}

const title = computed(() => {
  if (route.meta?.title) {
    return route.meta.title
  }
  const name = route.name
  return name && titleMap[name] ? titleMap[name] : '校招信息看板'
})
</script>

<template>
  <header class="topbar">
    <h1>{{ title }}</h1>
    <div class="spacer"></div>
    <button class="icon-btn" title="通知">
      🔔<span class="notification-dot"></span>
    </button>
    <button class="icon-btn" @click="$emit('open-config')" title="设置">⚙️</button>
    <button class="icon-btn" @click="$emit('toggle-theme')" title="主题">🌙</button>
  </header>
</template>
