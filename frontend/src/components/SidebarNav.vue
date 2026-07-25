<script setup>
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
</script>

<template>
  <aside class="sidebar">
    <div class="brand">
      <div class="mark"></div>
      <div>
        <b>校招信息看板</b>
        <span>Campus Recruitment</span>
      </div>
    </div>
    <div class="nav-sec">功能</div>
    <router-link to="/">投递信息</router-link>
    <router-link to="/board">投递看板</router-link>
    <router-link to="/records">总表信息</router-link>
    <router-link to="/resumes">简历管理</router-link>
    <router-link to="/analysis">简历分析</router-link>
    <router-link to="/admin" v-if="auth.isAdmin">管理页面</router-link>
    <div class="sidebar-foot">
      <span class="conn"><span class="pulse"></span> 已连接</span>
    </div>
  </aside>
</template>
