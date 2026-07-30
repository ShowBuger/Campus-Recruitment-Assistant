<script setup>
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'
import animeAssistant from '@/assets/skins/anime-assistant.png'

const route = useRoute()
const bubbleOpen = ref(true)
const emit = defineEmits(['open-help'])

const routeCopy = {
  dashboard: ['投递情报已整理', '先处理临近截止和等待反馈的记录吧。'],
  board: ['流程推进中', '拖动卡片就能更新当前投递阶段。'],
  records: ['资料库已打开', '这里适合做筛选、比较和批量整理。'],
  resumes: ['简历装备区', '针对目标岗位调整版本，会更容易命中关键词。'],
  analysis: ['AI 分析就绪', '选择简历和岗位，让我帮你检查匹配度。'],
  admin: ['管理控制台', '系统状态和用户配置都集中在这里。'],
}
const assistantCopy = computed(() => routeCopy[route.name] || ['今天也要加油', '每次投递都让目标更近一点。'])

const dockItems = [
  { to: '/', label: '投递', icon: '⌂' },
  { to: '/board', label: '看板', icon: '◇' },
  { to: '/records', label: '总表', icon: '▤' },
  { to: '/resumes', label: '简历', icon: '▱' },
  { to: '/analysis', label: '分析', icon: '✦' },
]
</script>

<template>
  <div class="desktop-skin-layer">
    <div class="liquid-backdrop" aria-hidden="true">
      <i></i><i></i><i></i>
    </div>
    <nav class="liquid-dock" aria-label="桌面快捷导航" aria-hidden="false">
      <router-link v-for="item in dockItems" :key="item.to" :to="item.to">
        <b>{{ item.icon }}</b><span>{{ item.label }}</span>
      </router-link>
      <button type="button" @click="emit('open-help')"><b>?</b><span>帮助</span></button>
    </nav>

    <aside class="anime-assistant" :class="{ collapsed: !bubbleOpen }" aria-hidden="false">
      <button class="anime-dialog" type="button" @click="bubbleOpen = !bubbleOpen">
        <small>CAMPUS GUIDE</small>
        <strong>{{ assistantCopy[0] }}</strong>
        <span>{{ assistantCopy[1] }}</span>
      </button>
      <img :src="animeAssistant" alt="原创校园招聘助手角色">
      <button class="anime-help" type="button" title="打开帮助" @click="emit('open-help')">?</button>
    </aside>
  </div>
</template>
