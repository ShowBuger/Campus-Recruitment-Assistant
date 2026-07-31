<script setup>
import { LiquidGlass } from '@wxperia/liquid-glass-vue'

const emit = defineEmits(['open-help'])

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
    <LiquidGlass
      class-name="liquid-dock-glass"
      mode="shader"
      effect="liquidGlass"
      :displacement-scale="64"
      :blur-amount="0.02"
      :saturation="165"
      :aberration-intensity="2.4"
      :elasticity="0.28"
      :corner-radius="30"
      padding="8px"
      :style="{ position: 'absolute', top: 'calc(100% - 55px)', left: '50%' }"
    >
      <nav class="liquid-dock" aria-label="桌面快捷导航">
        <router-link v-for="item in dockItems" :key="item.to" :to="item.to">
          <b>{{ item.icon }}</b><span>{{ item.label }}</span>
        </router-link>
        <button type="button" @click="emit('open-help')"><b>?</b><span>帮助</span></button>
      </nav>
    </LiquidGlass>
  </div>
</template>
