<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { useDialogStore } from '@/stores/dialog'

const auth = useAuthStore()
const toast = useToastStore()
const dialog = useDialogStore()
const files = ref([])
const activeFile = ref('')
const uploading = ref(false)
const fileInput = ref(null)

const previewUrl = computed(() => {
  if (!activeFile.value) return ''
  return `/api/resumes/${encodeURIComponent(activeFile.value)}/preview?token=${encodeURIComponent(auth.token)}`
})

onMounted(() => loadFiles())

async function loadFiles() {
  try {
    const res = await fetch('/api/resumes', { headers: { Authorization: `Bearer ${auth.token}` } })
    if (!res.ok) throw new Error('加载失败')
    const data = await res.json()
    files.value = data.files || []
  } catch { files.value = [] }
}

async function handleUpload(e) {
  const file = e.target.files?.[0]
  if (!file) return
  const ext = file.name.toLowerCase().split('.').pop()
  if (ext !== 'pdf' && ext !== 'docx') { toast.error('仅支持 PDF 和 DOCX 格式'); e.target.value = ''; return }
  if (file.size > 20 * 1024 * 1024) { toast.error('简历文件不能超过 20 MB'); e.target.value = ''; return }
  uploading.value = true
  try {
    const form = new FormData()
    form.append('file', file)
    let res
    for (let attempt = 0; attempt < 2; attempt++) {
      res = await fetch('/api/resumes', { method: 'POST', headers: { Authorization: `Bearer ${auth.token}` }, body: form })
      if (![502, 503, 504].includes(res.status) || attempt === 1) break
      await new Promise(r => setTimeout(r, 650))
    }
    if (!res.ok) {
      const text = await res.text()
      let data = {}
      try { data = JSON.parse(text) } catch {}
      throw new Error(data.detail || data.error || '上传失败')
    }
    const data = await res.json()
    toast.success(data.message || '简历已上传')
    activeFile.value = data.file?.name || file.name
    await loadFiles()
  } catch (e) { toast.error(e.message) }
  finally { uploading.value = false; e.target.value = '' }
}

async function deleteFile(f) {
  const confirmed = await dialog.confirm(
    `确定删除简历“${f.name}”吗？\n已有分析历史不会被一并删除。`,
    { title: '删除简历', tone: 'danger', confirmText: '删除简历' },
  )
  if (!confirmed) return
  try {
    const res = await fetch(`/api/resumes/${encodeURIComponent(f.name)}`, { method: 'DELETE', headers: { Authorization: `Bearer ${auth.token}` } })
    if (!res.ok) throw new Error('删除失败')
    if (activeFile.value === f.name) { activeFile.value = '' }
    toast.success('简历已删除')
    await loadFiles()
  } catch (e) { toast.error(e.message) }
}

function preview(f) { activeFile.value = f.name }

function fmtSize(bytes) {
  if (!bytes) return '0 B'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1048576).toFixed(1) + ' MB'
}
</script>

<template>
  <div class="page active">
    <div class="resume-layout" style="display:grid;grid-template-columns:280px minmax(0,1fr);gap:16px">
      <div class="resume-side">
        <h2 style="font-size:18px;margin-bottom:4px">简历文件</h2>
        <div class="muted" style="font-size:12px">支持 PDF、DOCX，最大 20 MB</div>
        <input type="file" ref="fileInput" accept=".pdf,.docx" @change="handleUpload" style="display:none">
        <button class="btn btn-primary" style="margin-top:14px" @click="$refs.fileInput.click()" :disabled="uploading">
          {{ uploading ? '上传中…' : '上传简历' }}
        </button>
        <div class="resume-list" style="margin-top:12px;max-height:50vh;overflow:auto">
          <div v-if="!files.length" class="center muted" style="padding:12px">尚未上传简历</div>
          <div v-for="f in files" :key="f.name" class="resume-row" style="display:flex;align-items:center;justify-content:space-between;padding:8px 4px;border-radius:8px;cursor:pointer" @click="preview(f)" :class="{ active: activeFile === f.name }">
            <div class="resume-item" style="flex:1;min-width:0">
              <b style="font-size:13px;display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{{ f.name }}</b>
              <span style="font-size:10px;color:var(--sub)">{{ (f.type || '文件').toUpperCase() }} · {{ fmtSize(f.size) }}</span>
            </div>
            <button class="btn btn-danger resume-delete" style="font-size:11px;padding:2px 8px;flex-shrink:0" @click.stop="deleteFile(f)">删除</button>
          </div>
        </div>
      </div>
      <div class="resume-preview">
        <div v-if="activeFile && previewUrl" style="height:calc(100vh - 160px);border-radius:12px;overflow:hidden">
          <iframe :src="previewUrl" title="简历预览" style="width:100%;height:100%;border:0"></iframe>
        </div>
        <div v-else class="resume-empty center muted" style="padding:60px 0">选择一份简历进行预览</div>
      </div>
    </div>
  </div>
</template>
