import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useDialogStore = defineStore('dialog', () => {
  const visible = ref(false)
  const mode = ref('confirm')
  const title = ref('')
  const message = ref('')
  const tone = ref('warning')
  const confirmText = ref('确认')
  const cancelText = ref('取消')
  const inputLabel = ref('')
  const inputValue = ref('')
  const placeholder = ref('')
  const required = ref(false)
  let resolver = null

  function open(nextMode, nextMessage, options = {}) {
    if (resolver) resolver(nextMode === 'prompt' ? null : false)
    mode.value = nextMode
    title.value = options.title || (
      nextMode === 'alert' ? '提示' :
      nextMode === 'prompt' ? '请输入信息' :
      '请确认操作'
    )
    message.value = String(nextMessage || '')
    tone.value = options.tone || (nextMode === 'alert' ? 'info' : 'warning')
    confirmText.value = options.confirmText || (nextMode === 'alert' ? '知道了' : '确认')
    cancelText.value = options.cancelText || '取消'
    inputLabel.value = options.inputLabel || ''
    inputValue.value = options.initialValue || ''
    placeholder.value = options.placeholder || ''
    required.value = !!options.required
    visible.value = true
    return new Promise((resolve) => { resolver = resolve })
  }

  function confirm(nextMessage, options) {
    return open('confirm', nextMessage, options)
  }

  function alert(nextMessage, options) {
    return open('alert', nextMessage, options)
  }

  function prompt(nextMessage, options) {
    return open('prompt', nextMessage, options)
  }

  function accept() {
    if (!visible.value) return
    if (mode.value === 'prompt' && required.value && !inputValue.value.trim()) return
    const result = mode.value === 'prompt' ? inputValue.value : true
    visible.value = false
    const resolve = resolver
    resolver = null
    resolve?.(result)
  }

  function cancel() {
    if (!visible.value) return
    const result = mode.value === 'prompt' ? null : false
    visible.value = false
    const resolve = resolver
    resolver = null
    resolve?.(result)
  }

  return {
    visible, mode, title, message, tone, confirmText, cancelText,
    inputLabel, inputValue, placeholder, required,
    confirm, alert, prompt, accept, cancel,
  }
})
