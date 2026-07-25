<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const titleMap = { dashboard: '投递信息', board: '投递看板', records: '总表信息', resumes: '简历管理', analysis: '简历分析', admin: '管理页面' }
const title = computed(() => titleMap[route.name] || '校招信息看板')
</script>

<template>
  <div class="topbar">
    <h1>{{ title }}</h1>
    <div class="spacer"></div>
    <button class="icon-btn" @click="$emit('open-chat')" title="站内聊天">✉</button>
    <button class="icon-btn" @click="$emit('open-config')" title="AI 配置">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M12 15.25A3.25 3.25 0 1 0 12 8.75a3.25 3.25 0 0 0 0 6.5Z" stroke="currentColor" stroke-width="1.8"/><path d="M19.4 13.5a7.8 7.8 0 0 0 .05-1.5 7.8 7.8 0 0 0-.05-1.5l2-1.55-2-3.46-2.48 1a7.7 7.7 0 0 0-2.57-1.5L14 2.35h-4L9.65 5a7.7 7.7 0 0 0-2.57 1.5l-2.48-1-2 3.46 2 1.55a7.8 7.8 0 0 0-.05 1.5c0 .51.02 1.01.05 1.5l-2 1.55 2 3.46 2.48-1a7.7 7.7 0 0 0 2.57 1.5l.35 2.64h4l.35-2.64a7.7 7.7 0 0 0 2.57-1.5l2.48 1 2-3.46-2-1.55Z" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>
    </button>
  </div>
</template>
