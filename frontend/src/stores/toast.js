import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useToastStore = defineStore('toast', () => {
  const toasts = ref([])
  let _id = 0

  function add(message, type = 'info', duration = 4000) {
    const id = ++_id
    toasts.value.push({ id, message, type, duration })
    if (duration > 0) setTimeout(() => remove(id), duration)
    return id
  }

  function remove(id) {
    toasts.value = toasts.value.filter(t => t.id !== id)
  }

  function success(msg, duration) { return add(msg, 'success', duration) }
  function error(msg, duration) { return add(msg, 'error', duration ?? 6000) }
  function info(msg, duration) { return add(msg, 'info', duration) }

  return { toasts, add, remove, success, error, info }
})
