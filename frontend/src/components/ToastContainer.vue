<template>
  <TransitionGroup name="toast" tag="div" class="toast-container">
    <div v-for="t in store.toasts" :key="t.id"
         class="toast"
         :class="'toast-' + t.type"
         @click="store.remove(t.id)">
      {{ t.message }}
    </div>
  </TransitionGroup>
</template>

<script setup>
import { useToastStore } from '@/stores/toast'

const store = useToastStore()
</script>

<style scoped>
.toast-container {
  position: fixed;
  top: 20px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 30000;
  display: flex;
  flex-direction: column;
  gap: 8px;
  pointer-events: none;
}

.toast {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 18px;
  border-radius: 999px;
  background: var(--ink);
  color: var(--bg);
  font-weight: 800;
  font-size: 13px;
  white-space: nowrap;
  pointer-events: auto;
  cursor: pointer;
}

.toast-success {
  background: var(--green, #059669);
  color: #fff;
}

.toast-error {
  background: var(--red, #e11d48);
  color: #fff;
}

.toast-info {
  background: var(--blue, #2563eb);
  color: #fff;
}

.toast-enter-active {
  transition: all 0.3s ease;
}

.toast-leave-active {
  transition: all 0.2s ease;
}

.toast-enter-from {
  opacity: 0;
  transform: translateY(-12px);
}

.toast-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
