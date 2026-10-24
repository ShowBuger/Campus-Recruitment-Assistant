<script setup>
import { computed, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { post } from '@/utils/api'
import UserAvatar from '@/components/UserAvatar.vue'

const emit = defineEmits(['close', 'saved'])
const auth = useAuthStore()
const toast = useToastStore()
const options = [
  ['indigo', '靛蓝少年'], ['sunset', '落日长发'], ['forest', '森林守望'], ['ocean', '海浪旅人'],
  ['cherry', '樱花双叶'], ['mono', '黑白机器人'], ['cosmos', '星际来客'], ['spark', '闪光星星'],
]
const selected = ref(auth.user?.avatar_key === 'custom' ? 'indigo' : (auth.user?.avatar_key || 'indigo'))
const image = ref(null)
const imageUrl = ref('')
const zoom = ref(1)
const offset = ref({ x: 0, y: 0 })
const saving = ref(false)
let dragStart = null
const CROP = 280

const imageSize = computed(() => {
  if (!image.value) return { width: CROP, height: CROP }
  const scale = Math.max(CROP / image.value.naturalWidth, CROP / image.value.naturalHeight) * zoom.value
  return { width: image.value.naturalWidth * scale, height: image.value.naturalHeight * scale }
})
const imageStyle = computed(() => ({
  width: `${imageSize.value.width}px`, height: `${imageSize.value.height}px`,
  transform: `translate(calc(-50% + ${offset.value.x}px), calc(-50% + ${offset.value.y}px))`,
}))

function clampOffset(next) {
  const maxX = Math.max(0, (imageSize.value.width - CROP) / 2)
  const maxY = Math.max(0, (imageSize.value.height - CROP) / 2)
  offset.value = { x: Math.max(-maxX, Math.min(maxX, next.x)), y: Math.max(-maxY, Math.min(maxY, next.y)) }
}
function onZoom() { clampOffset(offset.value) }
function startDrag(e) { dragStart = { x: e.clientX, y: e.clientY, ox: offset.value.x, oy: offset.value.y }; e.currentTarget.setPointerCapture(e.pointerId) }
function moveDrag(e) { if (dragStart) clampOffset({ x: dragStart.ox + e.clientX - dragStart.x, y: dragStart.oy + e.clientY - dragStart.y }) }
function endDrag() { dragStart = null }

function chooseFile(e) {
  const file = e.target.files?.[0]
  if (!file) return
  if (!file.type.startsWith('image/')) return toast.error('请选择图片文件')
  if (file.size > 10 * 1024 * 1024) return toast.error('原图不能超过 10MB')
  if (imageUrl.value) URL.revokeObjectURL(imageUrl.value)
  imageUrl.value = URL.createObjectURL(file)
  const next = new Image()
  next.onload = () => { image.value = next; zoom.value = 1; offset.value = { x: 0, y: 0 } }
  next.onerror = () => toast.error('图片无法读取')
  next.src = imageUrl.value
}

async function saveBuiltIn() {
  saving.value = true
  try {
    const data = await post('/api/auth/profile', { nickname: auth.user?.nickname || auth.user?.username, avatar_key: selected.value })
    auth.setUser(data.user); toast.success('头像已更新'); emit('saved'); emit('close')
  } catch (e) { toast.error(e.message) }
  finally { saving.value = false }
}

async function saveCrop() {
  if (!image.value) return
  saving.value = true
  try {
    const canvas = document.createElement('canvas'); canvas.width = 512; canvas.height = 512
    const ctx = canvas.getContext('2d'); const factor = 512 / CROP
    const dw = imageSize.value.width * factor, dh = imageSize.value.height * factor
    ctx.drawImage(image.value, (512 - dw) / 2 + offset.value.x * factor, (512 - dh) / 2 + offset.value.y * factor, dw, dh)
    const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', .9))
    const form = new FormData(); form.append('file', blob, 'avatar.jpg')
    const response = await fetch('/api/auth/avatar', { method: 'POST', headers: { Authorization: `Bearer ${auth.token}` }, body: form })
    const data = await response.json()
    if (!response.ok) throw new Error(data.detail || '头像上传失败')
    auth.setUser({ ...data.user, avatar_url: `${data.user.avatar_url}?t=${Date.now()}` })
    toast.success(data.message || '头像已更新'); emit('saved'); emit('close')
  } catch (e) { toast.error(e.message) }
  finally { saving.value = false }
}
</script>

<template>
  <Teleport to="body"><div class="modal-mask show avatar-picker-mask" @mousedown.self="emit('close')">
    <div class="modal avatar-picker-modal">
      <div class="modal-hd"><div><h2>更换头像</h2><p>{{ image ? '拖动和缩放图片，调整圆形框内的内容' : '选择内置头像或上传本地图片' }}</p></div><button class="icon-btn" type="button" title="关闭" @click="emit('close')">&times;</button></div>
      <div class="modal-body">
        <template v-if="!image">
          <div class="avatar-library">
            <button v-for="option in options" :key="option[0]" type="button" :class="{ selected: selected === option[0] }" @click="selected = option[0]"><UserAvatar :avatar-key="option[0]" :label="option[1]"/><span>{{ option[1] }}</span></button>
          </div>
          <label class="avatar-upload"><input type="file" accept="image/*" @change="chooseFile"><span>选择本地图片</span><small>JPG、PNG、WebP 等，原图最大 10MB</small></label>
        </template>
        <template v-else>
          <div class="crop-stage" @pointerdown="startDrag" @pointermove="moveDrag" @pointerup="endDrag" @pointercancel="endDrag"><img :src="imageUrl" :style="imageStyle" alt="头像裁剪预览"><div class="crop-shade"></div></div>
          <div class="crop-tools"><span>缩放</span><input v-model.number="zoom" type="range" min="1" max="3" step="0.01" @input="onZoom"><button class="btn" type="button" @click="image = null">重选</button></div>
        </template>
      </div>
      <div class="modal-ft"><button class="btn" type="button" @click="emit('close')">取消</button><button class="btn btn-primary" type="button" :disabled="saving" @click="image ? saveCrop() : saveBuiltIn()">{{ saving ? '保存中' : '保存头像' }}</button></div>
    </div>
  </div></Teleport>
</template>

<style scoped>
.avatar-picker-mask{z-index:22000}.avatar-picker-modal{width:min(560px,calc(100vw - 28px))}.avatar-library{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.avatar-library button{display:flex;min-width:0;flex-direction:column;align-items:center;gap:7px;padding:10px 5px;border:1px solid var(--line);border-radius:6px;background:var(--panel);color:var(--muted);font-size:10px;cursor:pointer}.avatar-library button:hover,.avatar-library button.selected{border-color:var(--ink);color:var(--ink)}.avatar-library button.selected{box-shadow:2px 2px 0 var(--ink)}.avatar-library .user-avatar{width:58px;height:58px}.avatar-upload{display:flex;align-items:center;justify-content:center;flex-direction:column;gap:4px;margin-top:16px;padding:15px;border:1px dashed var(--line2);border-radius:6px;background:var(--bg);cursor:pointer}.avatar-upload:hover{border-color:var(--blue)}.avatar-upload input{display:none}.avatar-upload span{font-weight:800}.avatar-upload small{color:var(--muted)}
.crop-stage{position:relative;width:280px;height:280px;margin:0 auto;overflow:hidden;background:#17191d;cursor:grab;touch-action:none}.crop-stage:active{cursor:grabbing}.crop-stage img{position:absolute;left:50%;top:50%;max-width:none;pointer-events:none;user-select:none}.crop-shade{position:absolute;inset:0;border-radius:50%;box-shadow:0 0 0 80px rgba(0,0,0,.55);outline:2px solid rgba(255,255,255,.9);outline-offset:-2px;pointer-events:none}.crop-tools{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:12px;margin-top:16px}.crop-tools span{font-size:12px;font-weight:800}.crop-tools input{width:100%}
@media(max-width:520px){.avatar-library{grid-template-columns:repeat(2,minmax(0,1fr))}.crop-stage{width:min(280px,calc(100vw - 72px));height:min(280px,calc(100vw - 72px))}}
</style>
