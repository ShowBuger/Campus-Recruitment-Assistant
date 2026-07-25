<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
const auth = useAuthStore()
const version = ref('')
onMounted(async () => {
  try { const r = await fetch('/api/version'); const d = await r.json(); version.value = d.version || '' } catch {}
})
</script>

<template>
  <aside class="sidebar">
    <div class="brand"><div class="mark"></div><div><b>校招信息看板</b><span>投递进度工作台</span></div></div>
    <div class="nav-sec">工作台</div>
    <router-link to="/">投递信息</router-link>
    <router-link to="/board">投递看板</router-link>
    <router-link to="/records">总表信息</router-link>
    <router-link to="/resumes">简历管理</router-link>
    <router-link to="/analysis">简历分析</router-link>
    <router-link to="/admin" v-if="auth.isAdmin">管理页面</router-link>
    <div class="sidebar-foot">
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;padding:4px 0">
        <span style="font-weight:800;font-size:13px">{{ auth.user?.username || '—' }}</span>
        <button class="btn" style="height:28px;padding:0 10px;font-size:11px" @click="auth.logout()">退出</button>
      </div>
      <div class="conn" style="display:flex;align-items:center;gap:6px">
        <span class="pulse"></span><span>云端存储</span>
        <span v-if="version" style="margin-left:auto;font-size:10px;color:var(--muted)">v{{ version }}</span>
      </div>
    </div>
  </aside>
</template>
