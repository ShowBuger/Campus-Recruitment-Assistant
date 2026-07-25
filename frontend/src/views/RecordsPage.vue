<script setup>
import { ref } from 'vue'

const showShared = ref(false)
</script>

<template>
  <div class="page">
    <div class="card">
      <div class="card-hd">
        <span class="dot"></span>
        <div class="card-title">总表信息</div>
        <div style="display:flex;gap:8px;margin-left:auto">
          <button class="btn" :class="{ active: !showShared }" @click="showShared=false">个人总表</button>
          <button class="btn" :class="{ active: showShared }" @click="showShared=true">共享总表</button>
        </div>
      </div>
      <p class="center muted">{{ showShared ? '共享总表 — 待迁移' : '个人总表 — 待迁移' }}</p>
    </div>
  </div>
</template>
