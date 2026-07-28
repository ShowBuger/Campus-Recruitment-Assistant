<template>
  <div class="modal-mask show" @mousedown.self="$emit('close')">>
    <div class="modal record-detail-modal">
      <div class="modal-hd">
        <div>
          <h2 id="total-edit-title">{{ record?.company || '记录详情' }}</h2>
          <p id="total-edit-description">在一个窗口中查看和修改完整记录。</p>
        </div>
        <button class="icon-btn" @click="$emit('close')" title="关闭">&times;</button>
      </div>

      <form id="total-edit-form" @submit.prevent="handleSubmit">
        <div class="modal-body">
          <div class="grid-2">
            <input id="total-edit-id" type="hidden" :value="recordId">

            <div class="form-group">
              <label for="total-edit-company">公司</label>
              <input id="total-edit-company" required maxlength="100" v-model="form.company" ref="companyInput">
            </div>

            <div class="form-group">
              <label for="total-edit-job" id="total-edit-job-label">目标岗位（选填）</label>
              <input id="total-edit-job" maxlength="500" placeholder="可留空" v-model="form.job">
            </div>

            <div class="form-group">
              <label for="total-edit-city">城市</label>
              <input id="total-edit-city" maxlength="200" v-model="form.city">
            </div>

            <div class="form-group">
              <label for="total-edit-batch">批次</label>
              <select id="total-edit-batch" v-model="form.batch">
                <option value="秋招">秋招</option>
                <option value="提前批">提前批</option>
              </select>
            </div>

            <div class="form-group">
              <label for="total-edit-directions" id="total-edit-directions-label">方向（选填）</label>
              <input id="total-edit-directions" maxlength="500" placeholder="多个方向用逗号分隔，可留空" v-model="form.directions">
            </div>

            <div class="form-group">
              <label for="total-edit-company-type" id="total-edit-company-type-label">公司类型（选填）</label>
              <input id="total-edit-company-type" maxlength="200" placeholder="例如：互联网、车企、国企，可留空" v-model="form.company_type">
            </div>

            <div class="form-group" id="total-edit-progress-group">
              <label for="total-edit-progress">进展</label>
              <select id="total-edit-progress" v-model="form.progress">
                <option value="未投递">未投递</option>
                <option value="已投递">已投递</option>
                <option value="机考">机考</option>
                <option value="面试">面试</option>
                <option value="OC">OC</option>
                <option value="已挂">已挂</option>
                <option value="放弃">放弃</option>
              </select>
            </div>

            <div class="form-group" id="total-edit-resume-version-group" v-show="form.progress !== '未投递'">
              <label for="total-edit-resume-version">简历版本</label>
              <select id="total-edit-resume-version" v-model="form.resume_version">
                <option value=""></option>
                <option v-for="f in resumes" :key="f.name" :value="f.name">{{ f.name }}</option>
              </select>
            </div>

            <div class="form-group">
              <label for="total-edit-deadline">截止</label>
              <input id="total-edit-deadline" type="text" v-model="form.deadline" @focus="activateOptionalDate" @blur="deactivateOptionalDate">
            </div>

            <div class="form-group" style="grid-column:1/-1">
              <label for="total-edit-url">入口网址</label>
              <input id="total-edit-url" placeholder="https://..." v-model="form.url">
            </div>

            <div class="detail-section" id="total-edit-detail-section">投递流程与详细信息</div>

            <div class="form-group" id="total-edit-priority-group">
              <label for="total-edit-priority">优先级</label>
              <select id="total-edit-priority" v-model="form.priority">
                <option value="⭐⭐⭐⭐⭐">⭐⭐⭐⭐⭐</option>
                <option value="⭐⭐⭐⭐">⭐⭐⭐⭐</option>
                <option value="⭐⭐⭐">⭐⭐⭐</option>
                <option value="⭐⭐">⭐⭐</option>
                <option value="⭐">⭐</option>
              </select>
            </div>

            <div class="form-group">
              <label for="total-edit-apply-date">投递时间</label>
              <input id="total-edit-apply-date" type="text" v-model="form.apply_date" @focus="activateOptionalDate" @blur="deactivateOptionalDate">
            </div>

            <div class="form-group">
              <label for="total-edit-exam-date">机考时间</label>
              <input id="total-edit-exam-date" type="text" v-model="form.exam_date" @focus="activateOptionalDate" @blur="deactivateOptionalDate">
            </div>

            <div class="form-group">
              <label for="total-edit-interview1">一面</label>
              <input id="total-edit-interview1" type="text" v-model="form.interview1" @focus="activateOptionalDate" @blur="deactivateOptionalDate">
            </div>

            <div class="form-group">
              <label for="total-edit-interview2">二面</label>
              <input id="total-edit-interview2" type="text" v-model="form.interview2" @focus="activateOptionalDate" @blur="deactivateOptionalDate">
            </div>

            <div class="form-group">
              <label for="total-edit-interview3">三面</label>
              <input id="total-edit-interview3" type="text" v-model="form.interview3" @focus="activateOptionalDate" @blur="deactivateOptionalDate">
            </div>

            <div class="form-group">
              <label for="total-edit-warm">保温</label>
              <input id="total-edit-warm" type="text" v-model="form.warm" @focus="activateOptionalDate" @blur="deactivateOptionalDate">
            </div>

            <div class="form-group">
              <label for="total-edit-result-date">结果时间</label>
              <input id="total-edit-result-date" type="text" v-model="form.result_date" @focus="activateOptionalDate" @blur="deactivateOptionalDate">
            </div>

            <div class="detail-section" id="total-edit-offer-section">Offer 信息（用于 Offer 对比）</div>

            <div class="form-group">
              <label for="total-edit-offer-total">总包</label>
              <input id="total-edit-offer-total" maxlength="100" placeholder="如 30W / 25k×16" v-model="form.offer_total">
            </div>

            <div class="form-group">
              <label for="total-edit-offer-base">base（月/年）</label>
              <input id="total-edit-offer-base" maxlength="100" placeholder="如 20k/月" v-model="form.offer_base">
            </div>

            <div class="form-group">
              <label for="total-edit-offer-bonus">奖金/股票/补贴</label>
              <input id="total-edit-offer-bonus" maxlength="200" placeholder="如 签字费 3W、房补 2k/月" v-model="form.offer_bonus">
            </div>

            <div class="form-group">
              <label for="total-edit-offer-deadline">决策截止</label>
              <input id="total-edit-offer-deadline" type="text" v-model="form.offer_deadline" @focus="activateOptionalDate" @blur="deactivateOptionalDate">
            </div>

            <div class="form-group record-detail-textarea">
              <label for="total-edit-job-jd">岗位 JD</label>
              <textarea id="total-edit-job-jd" maxlength="10000" placeholder="填写岗位职责、任职要求等信息" v-model="form.job_jd"></textarea>
            </div>

            <div class="form-group record-detail-textarea">
              <label for="total-edit-note">备注</label>
              <textarea id="total-edit-note" maxlength="5000" placeholder="填写公司评价、流程提醒或其他备注" v-model="form.note"></textarea>
            </div>
          </div>
        </div>

        <div class="detail-actions" id="total-edit-actions" v-if="record" style="display:grid">
          <div class="detail-actions-copy">
            <b>记录管理</b>
            <span>AI 补全只填写空缺字段，备注会追加在原内容之后</span>
          </div>
          <div class="detail-action-buttons">
            <button class="btn btn-ai-enrich" id="detail-enrich-btn" type="button" @click="enrichRecord" :disabled="enriching">AI 补全</button>
            <button class="btn btn-remove-application" id="detail-remove-btn" type="button" @click="removeApplication" v-show="isAppRecord">移出投递</button>
            <button class="btn" id="detail-share-btn" type="button" @click="shareRecord" :disabled="shareDisabled" :title="shareTitle">上传共享</button>
            <button class="btn btn-danger" type="button" @click="deleteRecord">删除记录</button>
          </div>
        </div>

        <div class="modal-ft">
          <button class="btn" type="button" @click="$emit('close')">取消</button>
          <button class="btn btn-primary" id="total-edit-submit" type="submit" :disabled="submitting">{{ submitting ? '保存中…' : '保存修改' }}</button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { useDashboardStore } from '@/stores/dashboard'
import { useToastStore } from '@/stores/toast'
import { useDialogStore } from '@/stores/dialog'
import { get, post } from '@/utils/api'
import { inputDateChina } from '@/utils/date'

const props = defineProps({
  recordId: { type: String, required: true }
})
const emit = defineEmits(['close', 'saved'])

const store = useDashboardStore()
const toast = useToastStore()
const dialog = useDialogStore()

const companyInput = ref(null)
const submitting = ref(false)
const enriching = ref(false)
const resumes = ref([])
const initialAiState = ref('')

// ---------- helper functions (ported from original JS) ----------

function inputDate(v) {
  return inputDateChina(v)
}

function shareMissing(r) {
  if (!r) return []
  const missing = []
  if (!String(r.company || '').trim()) missing.push('公司名称')
  if (!String(r.type || '').trim()) missing.push('公司类型')
  if (!String(r.job || '').trim()) missing.push('岗位')
  if (!Array.isArray(r.dir) || !r.dir.filter(Boolean).length) missing.push('方向')
  if (!String(r.url || '').trim()) missing.push('入口')
  return missing
}

function isApplicationRecord(r) {
  if (!r) return false
  const progress = String(Array.isArray(r.progress) ? r.progress[0] : (r.progress || '未投递'))
  return progress !== '未投递'
    || !!(r.apply_date || r.exam_date || r.interview1 || r.interview2 || r.interview3 || r.warm || r.result)
}

function computeAiState() {
  return JSON.stringify({
    company: form.company,
    job: form.job,
    type: form.company_type,
    directions: form.directions.split(/[,，、]/).map(s => s.trim()).filter(Boolean),
    note: form.note
  })
}

// ---------- date field activation (match original JS) ----------

function activateOptionalDate(e) {
  const input = e.target
  input.type = 'date'
  try { if (input.showPicker) input.showPicker() } catch (_) {}
}

function deactivateOptionalDate(e) {
  const input = e.target
  if (!input.value) input.type = 'text'
}

// ---------- form model ----------

const form = reactive({
  company: '',
  job: '',
  city: '',
  batch: '秋招',
  directions: '',
  company_type: '',
  progress: '未投递',
  resume_version: '',
  deadline: '',
  url: '',
  priority: '⭐⭐⭐',
  apply_date: '',
  exam_date: '',
  interview1: '',
  interview2: '',
  interview3: '',
  warm: '',
  result_date: '',
  offer_total: '',
  offer_base: '',
  offer_bonus: '',
  offer_deadline: '',
  job_jd: '',
  note: ''
})

// ---------- computed ----------

const record = computed(() => {
  return store.records.find(r => r.record_id === props.recordId) || null
})

const isAppRecord = computed(() => isApplicationRecord(record.value || {}))

const shareMissingFields = computed(() => shareMissing(record.value || {}))

const shareDisabled = computed(() => shareMissingFields.value.length > 0)

const shareTitle = computed(() => {
  return shareDisabled.value ? '需补全：' + shareMissingFields.value.join('、') : ''
})

// ---------- actions ----------

async function handleSubmit() {
  submitting.value = true
  try {
    const dirs = form.directions.split(/[,，、]/).map(s => s.trim()).filter(Boolean)
    const payload = {
      company: form.company.trim(),
      job: form.job.trim(),
      city: form.city.trim(),
      batch: form.batch,
      progress: form.progress,
      directions: dirs,
      company_type: form.company_type.trim(),
      deadline: form.deadline || null,
      url: form.url.trim(),
      priority: form.priority,
      note: form.note,
      job_jd: form.job_jd,
      apply_date: form.apply_date || null,
      exam_date: form.exam_date || null,
      interview1: form.interview1 || null,
      interview2: form.interview2 || null,
      interview3: form.interview3 || null,
      warm: form.warm || null,
      result_date: form.result_date || null,
      offer_total: form.offer_total.trim(),
      offer_base: form.offer_base.trim(),
      offer_bonus: form.offer_bonus.trim(),
      offer_deadline: form.offer_deadline || null,
      resume_version: form.resume_version
    }
    await post(`/api/dashboard/records/${encodeURIComponent(props.recordId)}/master/update`, payload)
    await store.refresh()
    toast.success('记录已更新')
    emit('saved')
    emit('close')
  } catch (err) {
    toast.error('保存失败：' + err.message)
  } finally {
    submitting.value = false
  }
}

async function enrichRecord() {
  const currentState = computeAiState()
  if (currentState !== initialAiState.value) {
    toast.error('请先保存当前手动修改，再执行 AI 补全')
    return
  }
  enriching.value = true
  toast.info('正在联网搜索公司与岗位信息…')
  try {
    const result = await post(`/api/ai/records/${encodeURIComponent(props.recordId)}/enrich`, {})
    await store.refresh()
    if (result.company_type) form.company_type = result.company_type
    if (result.directions) {
      form.directions = (Array.isArray(result.directions) ? result.directions : []).join('、')
    }
    if (result.note) form.note = result.note || ''
    initialAiState.value = computeAiState()
    const updated = result.updated_fields || []
    toast.success(
      updated.length
        ? 'AI 已补全：' + updated.join('、')
        : (result.message || '没有需要补充的新内容')
    )
  } catch (err) {
    toast.error('AI 补全失败：' + err.message)
  } finally {
    enriching.value = false
  }
}

async function shareRecord() {
  const r = record.value
  if (!r) return
  if (shareMissingFields.value.length) {
    toast.error('请先保存并补全：' + shareMissingFields.value.join('、'))
    return
  }
  try {
    await post(`/api/dashboard/shared/records/from-personal/${encodeURIComponent(props.recordId)}`)
    toast.success('已上传共享总表')
  } catch (err) {
    toast.error('上传共享失败：' + err.message)
  }
}

async function removeApplication() {
  const r = record.value
  if (!r) return
  const confirmed = await dialog.confirm(
    '确定将“' + (form.company || '该记录') + '”移出投递记录吗？\n关联的投递流程时间将被清空。',
    { title: '移出投递流程', tone: 'warning', confirmText: '确认移出' },
  )
  if (!confirmed) return
  try {
    await post(`/api/dashboard/records/${encodeURIComponent(props.recordId)}/remove`)
    await store.refresh()
    toast.success('已移出投递记录')
    emit('saved')
    emit('close')
  } catch (err) {
    toast.error('操作失败：' + err.message)
  }
}

async function deleteRecord() {
  const r = record.value
  if (!r) return
  const confirmed = await dialog.confirm(
    '确定永久删除“' + (form.company || '该记录') + '”吗？\n此操作不可撤销。',
    { title: '永久删除记录', tone: 'danger', confirmText: '永久删除' },
  )
  if (!confirmed) return
  try {
    await post(`/api/dashboard/records/${encodeURIComponent(props.recordId)}/permanent-delete`)
    await store.refresh()
    toast.success('记录已删除')
    emit('saved')
    emit('close')
  } catch (err) {
    toast.error('删除失败：' + err.message)
  }
}

// ---------- mount ----------

onMounted(async () => {
  const r = record.value
  if (!r) {
    toast.error('未找到对应记录')
    emit('close')
    return
  }

  form.company = r.company || ''
  form.job = r.job || ''
  form.city = r.city || ''
  form.batch = r.batch || '秋招'
  form.directions = (Array.isArray(r.dir) ? r.dir : []).join('、')
  form.company_type = r.type || ''
  form.progress = (Array.isArray(r.progress) ? r.progress[0] : r.progress) || '未投递'
  form.url = r.url || ''
  form.priority = r.priority || '⭐⭐⭐'
  form.job_jd = r.job_jd || ''
  form.note = r.note || ''
  form.offer_total = r.offer_total || ''
  form.offer_base = r.offer_base || ''
  form.offer_bonus = r.offer_bonus || ''
  form.resume_version = r.resume_version || ''

  // Set date values (all as YYYY-MM-DD strings)
  form.deadline = inputDate(r.deadline)
  form.apply_date = inputDate(r.apply_date)
  form.exam_date = inputDate(r.exam_date)
  form.interview1 = inputDate(r.interview1)
  form.interview2 = inputDate(r.interview2)
  form.interview3 = inputDate(r.interview3)
  form.warm = inputDate(r.warm)
  form.result_date = inputDate(r.result)
  form.offer_deadline = inputDate(r.offer_deadline)

  initialAiState.value = computeAiState()

  // Fetch resume list for the dropdown
  try {
    const d = await get('/api/resumes', { silent: true })
    resumes.value = d.files || []
  } catch (e) {
    // silently ignore — dropdown stays empty
  }

  nextTick(() => {
    // For date fields with values, set input type to 'date' (matching original openRecordDetails behavior)
    const TOTAL_DETAIL_DATE_IDS = [
      'total-edit-deadline', 'total-edit-apply-date', 'total-edit-exam-date',
      'total-edit-interview1', 'total-edit-interview2', 'total-edit-interview3',
      'total-edit-warm', 'total-edit-result-date', 'total-edit-offer-deadline'
    ]
    TOTAL_DETAIL_DATE_IDS.forEach(id => {
      const el = document.getElementById(id)
      if (el && el.value) el.type = 'date'
    })
    if (companyInput.value) companyInput.value.focus()
  })
})
</script>
