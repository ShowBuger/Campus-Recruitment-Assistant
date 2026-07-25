<template>
  <div class="modal-mask" @click.self="$emit('close')">
    <div class="modal settings-modal">
      <div class="modal-hd">
        <div>
          <h2>设置</h2>
          <p>AI 配置与进度跟踪</p>
        </div>
        <button class="icon-btn" @click="$emit('close')" title="关闭">&times;</button>
      </div>

      <div class="settings-tabs" style="display:flex;gap:8px;padding:0 20px;margin-bottom:16px">
        <button class="btn" :class="{ active: tab === 'ai' }" @click="tab = 'ai'">AI 配置</button>
        <button class="btn" :class="{ active: tab === 'tracker' }" @click="tab = 'tracker'">进度跟踪</button>
      </div>

      <div class="modal-body">
        <!-- AI Config Tab -->
        <section v-if="tab === 'ai'" class="settings-page active">
          <p class="center muted">AI 配置表单 — 待迁移</p>
        </section>

        <!-- Tracker Tab -->
        <section v-if="tab === 'tracker'" class="settings-page tracker-settings">
          <p class="center muted">进度跟踪配置 — 待迁移</p>
        </section>
      </div>

      <div class="modal-ft">
        <button class="btn" @click="$emit('close')">取消</button>
        <button class="btn btn-primary">保存</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const tab = ref('ai')
</script>
