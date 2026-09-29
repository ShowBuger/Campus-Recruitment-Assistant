<script setup>
import { computed } from 'vue'
import { useAuthStore } from '@/stores/auth'
import {
  PhChartBar,
  PhFileText,
  PhHouse,
  PhKanban,
  PhNotebook,
  PhMoney,
  PhScales,
  PhTable,
  PhUserGear,
} from '@phosphor-icons/vue'
import { navigationItems } from '@/utils/navigation'

const auth = useAuthStore()
const navIcons = {
  home: PhHouse,
  board: PhKanban,
  table: PhTable,
  resume: PhFileText,
  analysis: PhChartBar,
  notes: PhNotebook,
  salary: PhMoney,
  comparison: PhScales,
  admin: PhUserGear,
}
const dockItems = computed(() => navigationItems(auth.isAdmin))
</script>

<template>
  <div class="desktop-skin-layer">
    <div class="liquid-backdrop" aria-hidden="true"><i></i><i></i><i></i></div>
    <div class="liquid-dock-glass">
      <nav class="liquid-dock" aria-label="桌面快捷导航">
        <router-link v-for="item in dockItems" :key="item.to" :to="item.to" :title="item.label">
          <component :is="navIcons[item.icon]" :size="23" weight="regular" aria-hidden="true" />
          <span>{{ item.dockLabel }}</span>
        </router-link>
      </nav>
    </div>
  </div>
</template>
