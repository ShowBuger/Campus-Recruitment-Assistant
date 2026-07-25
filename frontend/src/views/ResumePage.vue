<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'

const auth = useAuthStore()
const toast = useToastStore()
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
  if (file.size > 20 * 1024 * 1024) { toast.error('文件不能超过 20MB'); return }
  uploading.value = true
  try {
    const form = new FormData()
    form.append('file', file)
    const res = await fetch('/api/resumes', { method: 'POST', headers: { Authorization: `Bearer ${auth.token}` }, body: form })
    if (!res.ok) throw new Error((await res.json()).detail || '上传失败')
    toast.success('简历已上传')
    await loadFiles()
    activeFile.value = file.name
  } catch (e) { toast.error(e.message) }
  finally { uploading.value = false; e.target.value = '' }
}

async function deleteFile(f, i) {
  if (!confirm(`确定删除简历"${f.name}"吗？`)) return
  try {
    const res = await fetch(`/api/resumes/${encodeURIComponent(f.name)}`, { method: 'DELETE', headers: { Authorization: `Bearer ${auth.token}` } })
    if (!res.ok) throw new Error('删除失败')
    if (activeFile.value === f.name) activeFile.value = ''
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
    <div class="grid-2" style="grid-template-columns:280px minmax(0,1fr)">
      <!-- Left: upload + file list -->
      <div class="card">
        <div class="card-hd"><span class="dot"></span><div class="card-title">简历文件</div></div>
        <div style="padding:12px">
          <input type="file" ref="fileInput" accept=".pdf,.docx,.doc" @change="handleUpload" style="display:none">
          <button class="btn btn-primary" @click="$refs.fileInput.click()" :disabled="uploading" style="width:100%">
            {{ uploading ? '上传中…' : '上传简历' }}
          </button>
          <p class="help" style="margin-top:6px">支持 PDF / DOCX，最大 20MB</p>
        </div>
        <div style="padding:0 12px 12px;max-height:400px;overflow:auto">
          <div v-if="!files.length" class="center muted">尚未上传简历</div>
          <div v-for="(f,i) in files" :key="f.name" class="resume-row" style="display:flex;align-items:center;justify-content:space-between;padding:8px;border-radius:8px;cursor:pointer" @click="preview(f)" :class="{ active: activeFile === f.name }">
            <div>
              <b style="font-size:13px">{{ f.name }}</b>
              <span style="display:block;font-size:10px;color:var(--sub)">{{ f.type?.toUpperCase() }} · {{ fmtSize(f.size) }}</span>
            </div>
            <button class="btn btn-danger" @click.stop="deleteFile(f,i)" style="font-size:11px;padding:2px 8px">删除</button>
          </div>
        </div>
      </div>

      <!-- Right: preview -->
      <div class="card">
        <div class="card-hd"><span class="dot"></span><div class="card-title">预览</div></div>
        <div v-if="activeFile" style="height:70vh">
          <iframe :src="previewUrl" style="width:100%;height:100%;border:0"></iframe>
        </div>
        <div v-else class="center muted" style="padding:60px 0">选择一份简历进行预览</div>
      </div>
    </div>
  </div>
</template>
