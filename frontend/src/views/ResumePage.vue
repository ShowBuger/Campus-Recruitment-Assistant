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
const loadingFiles = ref(true)
const loadError = ref('')
const fileInput = ref(null)

const activeFileInfo = computed(() => files.value.find(file => file.name === activeFile.value) || null)

const previewUrl = computed(() => {
  if (!activeFile.value) return ''
  return `/api/resumes/${encodeURIComponent(activeFile.value)}/preview?token=${encodeURIComponent(auth.token)}`
})

onMounted(() => loadFiles())

async function loadFiles() {
  loadingFiles.value = true
  loadError.value = ''
  try {
    const res = await fetch('/api/resumes', { headers: { Authorization: `Bearer ${auth.token}` } })
    if (!res.ok) throw new Error('加载失败')
    const data = await res.json()
    files.value = data.files || []
  } catch {
    files.value = []
    loadError.value = '简历列表加载失败，请稍后重试'
  } finally {
    loadingFiles.value = false
  }
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
function chooseFile() { fileInput.value?.click() }

function fmtSize(bytes) {
  if (!bytes) return '0 B'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1048576).toFixed(1) + ' MB'
}

function fmtDate(value) {
  if (!value) return '时间未知'
  return new Intl.DateTimeFormat('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(new Date(value))
}
</script>

<template>
  <div class="page active resume-page">
    <header class="resume-page-head">
      <div>
        <h2>管理你的简历版本</h2>
        <p>上传、预览并维护针对不同岗位的简历文件。</p>
      </div>
      <div class="resume-head-actions">
        <span class="resume-count">{{ files.length }} 份简历</span>
        <input ref="fileInput" type="file" accept=".pdf,.docx" @change="handleUpload">
        <button class="btn btn-primary resume-upload" type="button" :disabled="uploading" @click="chooseFile">
          <span v-if="uploading" class="resume-upload-spinner" aria-hidden="true"></span>
          {{ uploading ? '正在上传' : '上传简历' }}
        </button>
      </div>
    </header>

    <div class="resume-workspace">
      <aside class="resume-library" aria-label="简历文件列表">
        <div class="resume-library-head">
          <div>
            <h3>简历库</h3>
            <p>PDF 或 DOCX，单个文件最大 20 MB</p>
          </div>
          <button class="resume-refresh" type="button" :disabled="loadingFiles" @click="loadFiles">刷新</button>
        </div>

        <div class="resume-list" aria-live="polite">
          <div v-if="loadingFiles" class="resume-list-loading" aria-label="正在加载简历">
            <span v-for="item in 3" :key="item"></span>
          </div>

          <div v-else-if="loadError" class="resume-list-state resume-list-error">
            <strong>暂时无法读取简历</strong>
            <p>{{ loadError }}</p>
            <button class="btn" type="button" @click="loadFiles">重新加载</button>
          </div>

          <div v-else-if="!files.length" class="resume-list-state">
            <strong>还没有简历</strong>
            <p>上传第一份简历后，可在这里预览和管理版本。</p>
            <button class="btn" type="button" @click="chooseFile">选择文件</button>
          </div>

          <article
            v-for="f in files"
            v-else
            :key="f.name"
            class="resume-file"
            :class="{ active: activeFile === f.name }"
          >
            <button class="resume-file-main" type="button" @click="preview(f)">
              <span class="resume-type">{{ (f.type || '文件').toUpperCase() }}</span>
              <span class="resume-file-copy">
                <strong :title="f.name">{{ f.name }}</strong>
                <small>{{ fmtSize(f.size) }} / {{ fmtDate(f.modified) }}</small>
              </span>
            </button>
            <button class="resume-delete" type="button" :aria-label="`删除简历 ${f.name}`" @click="deleteFile(f)">删除</button>
          </article>
        </div>
      </aside>

      <section class="resume-preview-panel" aria-label="简历预览区域">
        <div v-if="activeFileInfo" class="resume-preview-toolbar">
          <div>
            <strong :title="activeFileInfo.name">{{ activeFileInfo.name }}</strong>
            <span>{{ (activeFileInfo.type || '文件').toUpperCase() }} / {{ fmtSize(activeFileInfo.size) }}</span>
          </div>
          <a class="btn" :href="previewUrl" target="_blank" rel="noopener">新窗口打开</a>
        </div>

        <div v-if="activeFile && previewUrl" class="resume-preview-frame">
          <iframe :src="previewUrl" :title="`简历预览：${activeFile}`"></iframe>
        </div>

        <div v-else class="resume-preview-empty">
          <div class="resume-empty-sheet" aria-hidden="true"><span></span><span></span><span></span></div>
          <h3>{{ files.length ? '选择一份简历开始预览' : '你的简历会显示在这里' }}</h3>
          <p>{{ files.length ? '从左侧简历库中选择一个文件。' : '支持 PDF 和 DOCX，上传后即可检查内容。' }}</p>
          <button v-if="!files.length" class="btn btn-primary" type="button" @click="chooseFile">上传简历</button>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.resume-page { min-width: 0; }
.resume-page-head { display: flex; align-items: flex-end; justify-content: space-between; gap: 24px; margin-bottom: 18px; }
.resume-page-head h2 { margin: 0; font-size: clamp(22px, 2.5vw, 30px); line-height: 1.2; letter-spacing: -.035em; }
.resume-page-head p { max-width: 560px; margin-top: 7px; color: var(--muted); font-size: 13px; }
.resume-head-actions { display: flex; align-items: center; gap: 10px; }
.resume-count { color: var(--muted); font-size: 12px; white-space: nowrap; }
.resume-head-actions input[type="file"] { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); clip-path: inset(50%); white-space: nowrap; }
.resume-upload { display: inline-flex; min-width: 104px; align-items: center; justify-content: center; gap: 7px; white-space: nowrap; }
.resume-upload-spinner { width: 13px; height: 13px; border: 2px solid color-mix(in srgb, #fff 42%, transparent); border-top-color: #fff; border-radius: 50%; animation: resume-spin .75s linear infinite; }
.resume-workspace { display: grid; grid-template-columns: minmax(260px, 320px) minmax(0, 1fr); min-height: calc(100vh - 188px); overflow: hidden; border: 1px solid var(--line); border-radius: 16px; background: var(--panel); box-shadow: var(--shadow); }
.resume-library { display: flex; min-width: 0; flex-direction: column; border-right: 1px solid var(--line); background: var(--panel); }
.resume-library-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; padding: 18px; border-bottom: 1px solid var(--line); }
.resume-library-head h3 { margin: 0; font-size: 14px; }
.resume-library-head p { margin-top: 4px; color: var(--sub); font-size: 10px; line-height: 1.5; }
.resume-refresh { padding: 2px 0; border: 0; background: transparent; color: var(--blue); font: 800 11px var(--font); cursor: pointer; }
.resume-refresh:hover { color: var(--blue2); text-decoration: underline; }
.resume-refresh:disabled { cursor: wait; opacity: .55; }
.resume-list { display: grid; align-content: start; gap: 8px; min-height: 0; padding: 10px; overflow: auto; }
.resume-file { display: grid; grid-template-columns: minmax(0, 1fr) auto; align-items: stretch; border: 1px solid var(--line); border-radius: 12px; background: var(--panel); transition: border-color .18s ease, background .18s ease, transform .18s ease; }
.resume-file:hover { border-color: var(--line2); transform: translateY(-1px); }
.resume-file.active { border-color: var(--blue); background: var(--blueS); box-shadow: inset 3px 0 0 var(--blue); }
.resume-file-main { display: grid; min-width: 0; grid-template-columns: 38px minmax(0, 1fr); align-items: center; gap: 10px; padding: 11px 8px 11px 12px; border: 0; background: transparent; color: var(--ink); text-align: left; cursor: pointer; }
.resume-type { display: grid; width: 36px; height: 36px; place-items: center; border: 1px solid var(--line2); border-radius: 9px; background: var(--bg); color: var(--blue); font: 900 9px var(--mono); }
.resume-file-copy { min-width: 0; }
.resume-file-copy strong, .resume-file-copy small { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.resume-file-copy strong { font-size: 12px; }
.resume-file-copy small { margin-top: 4px; color: var(--sub); font-size: 9px; }
.resume-delete { align-self: center; margin-right: 9px; padding: 5px 3px; border: 0; background: transparent; color: var(--sub); font: 800 10px var(--font); cursor: pointer; }
.resume-delete:hover { color: var(--red); }
.resume-delete:focus-visible, .resume-file-main:focus-visible, .resume-refresh:focus-visible { outline: 2px solid var(--blue); outline-offset: 2px; }
.resume-list-state { padding: 34px 18px; color: var(--muted); text-align: center; }
.resume-list-state strong { display: block; color: var(--ink); font-size: 13px; }
.resume-list-state p { margin: 7px auto 14px; font-size: 11px; line-height: 1.6; }
.resume-list-state .btn { height: 32px; }
.resume-list-error strong { color: var(--red); }
.resume-list-loading { display: grid; gap: 8px; }
.resume-list-loading span { height: 60px; border-radius: 12px; background: linear-gradient(100deg, var(--bg) 20%, var(--line) 42%, var(--bg) 64%); background-size: 220% 100%; animation: resume-shimmer 1.2s ease-in-out infinite; }
.resume-preview-panel { display: grid; min-width: 0; grid-template-rows: auto minmax(0, 1fr); background: var(--bg); }
.resume-preview-toolbar { display: flex; min-width: 0; align-items: center; justify-content: space-between; gap: 16px; padding: 11px 14px; border-bottom: 1px solid var(--line); background: var(--panel); }
.resume-preview-toolbar > div { min-width: 0; }
.resume-preview-toolbar strong, .resume-preview-toolbar span { display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.resume-preview-toolbar strong { font-size: 12px; }
.resume-preview-toolbar span { margin-top: 2px; color: var(--sub); font-size: 9px; }
.resume-preview-toolbar .btn { display: inline-flex; height: 31px; flex: 0 0 auto; align-items: center; padding: 0 10px; font-size: 10px; white-space: nowrap; }
.resume-preview-frame { min-height: 0; overflow: hidden; }
.resume-preview-frame iframe { display: block; width: 100%; height: 100%; min-height: calc(100vh - 236px); border: 0; background: var(--panel); }
.resume-preview-empty { display: grid; align-content: center; justify-items: center; min-height: 430px; padding: 48px 24px; color: var(--muted); text-align: center; }
.resume-empty-sheet { display: grid; width: 96px; height: 124px; align-content: start; gap: 10px; padding: 30px 18px 18px; border: 1px solid var(--line2); border-radius: 12px; background: var(--panel); box-shadow: 8px 9px 0 var(--blueS); }
.resume-empty-sheet span { height: 5px; border-radius: 3px; background: var(--line2); }
.resume-empty-sheet span:nth-child(2) { width: 72%; }
.resume-empty-sheet span:nth-child(3) { width: 86%; }
.resume-preview-empty h3 { margin: 24px 0 0; color: var(--ink); font-size: 16px; }
.resume-preview-empty p { margin: 7px 0 17px; font-size: 12px; }
@keyframes resume-spin { to { transform: rotate(360deg); } }
@keyframes resume-shimmer { to { background-position: -120% 0; } }
@media (max-width: 900px) {
  .resume-page-head { align-items: flex-start; flex-direction: column; }
  .resume-head-actions { width: 100%; justify-content: space-between; }
  .resume-workspace { grid-template-columns: 1fr; min-height: 0; overflow: visible; }
  .resume-library { border-right: 0; border-bottom: 1px solid var(--line); }
  .resume-list { max-height: 360px; }
  .resume-preview-frame iframe { min-height: 68vh; }
}
@media (max-width: 520px) {
  .resume-page-head p { font-size: 12px; }
  .resume-count { display: none; }
  .resume-upload { width: 100%; }
  .resume-workspace { border-radius: 12px; }
  .resume-library-head { padding: 15px; }
  .resume-preview-toolbar { align-items: flex-start; }
  .resume-preview-toolbar .btn { max-width: 96px; }
}
@media (prefers-reduced-motion: reduce) {
  .resume-upload-spinner, .resume-list-loading span { animation: none; }
  .resume-file { transition: none; }
}
</style>
