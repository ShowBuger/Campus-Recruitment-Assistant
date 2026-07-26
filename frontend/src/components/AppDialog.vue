<template>
  <Teleport to="body">
    <Transition name="app-dialog">
      <div
        v-if="dialog.visible"
        class="app-dialog-mask"
        role="presentation"
        @click.self="dialog.cancel()"
      >
        <section
          ref="panel"
          class="app-dialog-card"
          :class="'tone-' + dialog.tone"
          role="dialog"
          aria-modal="true"
          :aria-labelledby="titleId"
        >
          <div class="app-dialog-accent" aria-hidden="true">
            <span>{{ toneSymbol }}</span>
          </div>
          <div class="app-dialog-copy">
            <div class="app-dialog-kicker">{{ kicker }}</div>
            <h2 :id="titleId">{{ dialog.title }}</h2>
            <p>{{ dialog.message }}</p>
            <label v-if="dialog.mode === 'prompt'" class="app-dialog-input">
              <span v-if="dialog.inputLabel">{{ dialog.inputLabel }}</span>
              <input
                ref="input"
                v-model="dialog.inputValue"
                :placeholder="dialog.placeholder"
                :aria-label="dialog.inputLabel || dialog.title"
                @keydown.enter.prevent="dialog.accept()"
              >
              <small v-if="dialog.required && !dialog.inputValue.trim()">此项不能为空</small>
            </label>
          </div>
          <div class="app-dialog-actions">
            <button
              v-if="dialog.mode !== 'alert'"
              type="button"
              class="btn"
              @click="dialog.cancel()"
            >{{ dialog.cancelText }}</button>
            <button
              ref="confirmButton"
              type="button"
              class="btn"
              :class="dialog.tone === 'danger' ? 'btn-danger' : 'btn-primary'"
              :disabled="dialog.mode === 'prompt' && dialog.required && !dialog.inputValue.trim()"
              @click="dialog.accept()"
            >{{ dialog.confirmText }}</button>
          </div>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useDialogStore } from '@/stores/dialog'

const dialog = useDialogStore()
const input = ref(null)
const confirmButton = ref(null)
const panel = ref(null)
const titleId = 'app-dialog-title'

const kicker = computed(() => ({
  danger: '危险操作',
  warning: '操作确认',
  success: '操作完成',
  info: '系统提示',
}[dialog.tone] || '系统提示'))

const toneSymbol = computed(() => ({
  danger: '!',
  warning: '?',
  success: '✓',
  info: 'i',
}[dialog.tone] || 'i'))

watch(() => dialog.visible, async (visible) => {
  if (!visible) return
  await nextTick()
  if (dialog.mode === 'prompt') input.value?.focus()
  else confirmButton.value?.focus()
})

function onKeydown(event) {
  if (!dialog.visible) return
  if (event.key === 'Escape') {
    event.preventDefault()
    dialog.cancel()
  }
}

onMounted(() => window.addEventListener('keydown', onKeydown))
onUnmounted(() => window.removeEventListener('keydown', onKeydown))
</script>

<style scoped>
.app-dialog-mask {
  position: fixed;
  inset: 0;
  z-index: 40000;
  display: grid;
  place-items: center;
  padding: 20px;
  background: rgba(10, 14, 23, .62);
  backdrop-filter: blur(8px);
}

.app-dialog-card {
  --dialog-accent: var(--amber);
  display: grid;
  grid-template-columns: 58px minmax(0, 1fr);
  width: min(520px, 94vw);
  overflow: hidden;
  border: 2px solid var(--ink);
  border-radius: 16px;
  background: var(--panel);
  box-shadow: 7px 7px 0 var(--ink);
}

.app-dialog-card.tone-danger { --dialog-accent: var(--red); }
.app-dialog-card.tone-info { --dialog-accent: var(--blue); }
.app-dialog-card.tone-success { --dialog-accent: var(--green); }

.app-dialog-accent {
  display: flex;
  justify-content: center;
  padding-top: 23px;
  background: color-mix(in srgb, var(--dialog-accent) 16%, var(--panel));
  border-right: 1px solid var(--line);
}

.app-dialog-accent span {
  display: grid;
  width: 30px;
  height: 30px;
  place-items: center;
  border: 2px solid var(--ink);
  border-radius: 8px;
  background: var(--dialog-accent);
  color: #fff;
  box-shadow: 3px 3px 0 var(--ink);
  font: 900 16px var(--mono);
}

.app-dialog-copy {
  min-width: 0;
  padding: 22px 24px 18px;
}

.app-dialog-kicker {
  color: var(--dialog-accent);
  font: 900 10px var(--mono);
  letter-spacing: .12em;
}

.app-dialog-copy h2 {
  margin: 5px 0 10px;
  color: var(--ink);
  font-size: 18px;
}

.app-dialog-copy p {
  margin: 0;
  color: var(--sub);
  font-size: 13px;
  line-height: 1.75;
  white-space: pre-line;
}

.app-dialog-input {
  display: grid;
  gap: 7px;
  margin-top: 16px;
}

.app-dialog-input span {
  color: var(--ink);
  font-size: 12px;
  font-weight: 800;
}

.app-dialog-input input {
  width: 100%;
}

.app-dialog-input small {
  color: var(--red);
  font-size: 10px;
}

.app-dialog-actions {
  grid-column: 1 / -1;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 13px 18px;
  border-top: 1px solid var(--line);
  background: var(--bg);
}

.app-dialog-actions .btn {
  min-width: 88px;
}

.app-dialog-enter-active,
.app-dialog-leave-active {
  transition: opacity .2s ease;
}

.app-dialog-enter-active .app-dialog-card,
.app-dialog-leave-active .app-dialog-card {
  transition: transform .24s var(--spring), opacity .2s ease;
}

.app-dialog-enter-from,
.app-dialog-leave-to {
  opacity: 0;
}

.app-dialog-enter-from .app-dialog-card,
.app-dialog-leave-to .app-dialog-card {
  opacity: 0;
  transform: translateY(14px) scale(.98);
}

@media (max-width: 560px) {
  .app-dialog-card {
    grid-template-columns: 46px minmax(0, 1fr);
    border-radius: 12px;
    box-shadow: 5px 5px 0 var(--ink);
  }
  .app-dialog-accent { padding-top: 20px; }
  .app-dialog-accent span { width: 26px; height: 26px; }
  .app-dialog-copy { padding: 18px 16px 16px; }
  .app-dialog-actions { display: grid; grid-template-columns: 1fr 1fr; }
  .app-dialog-actions .btn { width: 100%; }
  .app-dialog-actions .btn:only-child { grid-column: 1 / -1; }
}
</style>
