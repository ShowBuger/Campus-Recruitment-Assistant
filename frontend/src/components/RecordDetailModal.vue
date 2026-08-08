<template>
  <div class="modal-mask show" @mousedown.self="requestBackdropClose">
    <div class="modal record-detail-modal">
      <div class="modal-hd">
        <div>
          <h2 id="total-edit-title">{{ record?.company || '记录详情' }}</h2>
          <p id="total-edit-description">在一个窗口中查看和修改完整记录。</p>
        </div>
        <div class="record-detail-hd-actions">
          <button class="btn record-timeline-open-btn" type="button" @click="openTimeline">时间线</button>
          <button class="icon-btn" @click="$emit('close')" title="关闭">&times;</button>
        </div>
      </div>

      <section class="detail-position-bar" aria-label="岗位子记录">
        <div class="detail-position-heading"><div><b>岗位子记录</b><span>{{ positionRecords.length }} 条记录独立保存进展、时间与简历</span></div><div class="detail-position-heading-actions"><strong>正在编辑：{{ record?.job || '未命名岗位' }}</strong><button class="btn btn-primary position-add-btn" type="button" :disabled="creatingPosition" @click="addPosition">{{ creatingPosition ? '创建中…' : '增加子记录' }}</button></div></div>
        <div v-if="positionRecords.length > 1" class="detail-position-list">
          <div v-for="position in positionRecords" :key="position.record_id" class="detail-position-item" :class="{ active: position.record_id === activeRecordId }">
            <button type="button" @click="switchDetailPosition(position)">
              <span class="detail-position-title"><b>{{ position.job || '未命名岗位' }}</b><small>{{ position.city || '城市未填写' }} / {{ position.batch || '批次未填写' }}</small></span>
              <span class="detail-position-meta"><em>{{ (position.progress || [])[0] || '未投递' }}</em><small>{{ position.resume_version || '未指定简历' }}</small></span>
            </button>
            <button type="button" class="detail-position-delete" :title="'删除 ' + (position.job || '该岗位')" @click="deletePosition(position)">&times;</button>
          </div>
        </div>
      </section>

      <form id="total-edit-form" @submit.prevent="handleSubmit">
        <div class="settings-tabs detail-tabs" role="tablist" aria-label="记录详情分类">
          <button
            v-for="page in detailPages"
            :id="`detail-tab-${page.id}`"
            :key="page.id"
            class="btn"
            :class="{ active: activePage === page.id }"
            type="button"
            role="tab"
            :aria-selected="activePage === page.id"
            :aria-controls="`detail-page-${page.id}`"
            :tabindex="activePage === page.id ? 0 : -1"
            @click="activePage = page.id"
            @keydown.left.prevent="selectAdjacentPage(page.id, -1)"
            @keydown.right.prevent="selectAdjacentPage(page.id, 1)"
          >{{ page.label }}</button>
        </div>

        <div class="modal-body">
          <section id="detail-page-basic" class="detail-form-section detail-page" :class="{ active: activePage === 'basic' }" role="tabpanel" aria-labelledby="detail-tab-basic">
            <div class="detail-form-heading"><h3>岗位基础信息</h3><p>公司、岗位属性与投递入口</p></div>
            <div class="detail-form-grid">
            <input id="total-edit-id" type="hidden" :value="activeRecordId">

            <div class="form-group">
              <label for="total-edit-company">公司</label>
              <input id="total-edit-company" aria-required="true" maxlength="100" v-model="form.company" ref="companyInput">
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

            <div class="form-group detail-field-wide">
              <label for="total-edit-url">入口网址</label>
              <input id="total-edit-url" placeholder="https://..." v-model="form.url">
            </div>
            </div>
          </section>

          <section id="detail-page-process" class="detail-form-section detail-page" :class="{ active: activePage === 'process' }" role="tabpanel" aria-labelledby="detail-tab-process">
            <div class="detail-form-heading"><h3>投递流程</h3><p>当前状态、使用简历与各流程节点</p></div>
            <div class="detail-form-grid">

            <div class="form-group" id="total-edit-progress-group">
              <label for="total-edit-progress">进展</label>
              <select id="total-edit-progress" v-model="form.progress" @change="handleProgressChange">
                <option value="未投递">未投递</option>
                <option value="已投递">已投递</option>
                <option value="机考">机考</option>
                <option value="面试">面试</option>
                <option value="OC">OC</option>
                <option value="已挂">已挂</option>
                <option value="放弃">放弃</option>
              </select>
            </div>

            <div class="form-group" id="total-edit-resume-version-group">
              <label for="total-edit-resume-version">简历版本</label>
              <select id="total-edit-resume-version" v-model="form.resume_version">
                <option value="">未指定</option>
                <option v-for="f in resumes" :key="f.name" :value="f.name">{{ f.name }}</option>
              </select>
            </div>

            <div class="form-group">
              <label for="total-edit-deadline">截止</label>
              <input id="total-edit-deadline" type="text" v-model="form.deadline" @focus="activateOptionalDate" @blur="deactivateOptionalDate">
            </div>

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
            </div>
          </section>

          <section id="detail-page-offer" class="detail-form-section detail-page" :class="{ active: activePage === 'offer' }" role="tabpanel" aria-labelledby="detail-tab-offer">
            <div class="detail-form-heading"><h3>Offer 信息</h3><p>用于 Offer 对比，可按需填写</p></div>
            <div class="detail-form-grid">

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
            </div>
          </section>

          <section id="detail-page-materials" class="detail-form-section detail-page" :class="{ active: activePage === 'materials' }" role="tabpanel" aria-labelledby="detail-tab-materials">
            <div class="detail-form-heading"><h3>岗位材料</h3><p>岗位要求与个人备注</p></div>
            <div class="detail-form-grid">
            <div class="form-group record-detail-textarea">
              <label for="total-edit-job-jd">岗位 JD</label>
              <textarea id="total-edit-job-jd" maxlength="10000" placeholder="填写岗位职责、任职要求等信息" v-model="form.job_jd"></textarea>
            </div>

            <div class="form-group record-detail-textarea">
              <label for="total-edit-note">备注</label>
              <textarea id="total-edit-note" maxlength="5000" placeholder="填写公司评价、流程提醒或其他备注" v-model="form.note"></textarea>
            </div>
            </div>
          </section>
        </div>

        <div class="detail-actions" id="total-edit-actions" v-if="record" style="display:grid">
          <div class="detail-actions-copy">
            <b>记录管理</b>
            <span>AI 补全只填写空缺字段，备注会追加在原内容之后</span>
          </div>
          <div class="detail-action-buttons">
            <button class="btn btn-ai-enrich" id="detail-enrich-btn" type="button" @click="enrichRecord" :disabled="enriching">{{ enriching ? '补全中…' : 'AI 补全' }}</button>
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

    <Teleport to="body">
      <div class="modal-mask show record-timeline-mask" v-if="showTimeline" @mousedown.self="showTimeline = false">
        <div class="modal record-timeline-modal">
        <div class="modal-hd">
          <div>
            <h2>{{ record?.company || '记录详情' }} · 进度时间线</h2>
            <p>汇总个人总表节点和邮箱智能识别历史。</p>
          </div>
          <button class="icon-btn" type="button" @click="showTimeline = false" title="关闭">&times;</button>
        </div>
        <div class="modal-body">
          <div class="record-progress-timeline">
            <div v-if="timelineLoading" class="record-timeline-empty">正在读取进度历史…</div>
            <div v-else-if="!timeline.length" class="record-timeline-empty">暂无进度节点，邮箱识别或手动填写时间后会显示在这里。</div>
            <article v-for="item in timeline" :key="timelineKey(item)" class="record-timeline-item" :class="'is-' + item.status">
              <i></i>
              <div class="record-timeline-card">
                <div class="record-timeline-head">
                  <b>{{ item.label || item.progress }}</b>
                  <span>{{ formatTimelineTime(item.event_ms) }}</span>
                </div>
                <p v-if="item.resolution">{{ item.resolution }}</p>
                <p v-else-if="item.reason">{{ item.reason }}</p>
                <div v-if="item.kind === 'email'" class="record-timeline-meta">
                  <span>邮箱识别</span>
                  <span>置信度 {{ Math.round(Number(item.confidence || 0) * 100) }}%</span>
                  <span v-if="item.deadline_ms">截止 {{ formatTimelineTime(item.deadline_ms) }}</span>
                  <span v-if="item.status === 'pending'">待确认</span>
                  <span v-else-if="item.status === 'ignored'">已忽略</span>
                </div>
              </div>
            </article>
          </div>
        </div>
        <div class="modal-ft">
          <button class="btn btn-primary" type="button" @click="showTimeline = false">关闭</button>
        </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, nextTick } from 'vue'
import { useDashboardStore } from '@/stores/dashboard'
import { useToastStore } from '@/stores/toast'
import { useDialogStore } from '@/stores/dialog'
import { get, post } from '@/utils/api'
import { inputDateChina } from '@/utils/date'
import { useRecordGroups } from '@/composables/useRecordGroups'

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
const creatingPosition = ref(false)
const resumes = ref([])
const initialAiState = ref('')
const timeline = ref([])
const timelineLoading = ref(false)
const showTimeline = ref(false)
const activePage = ref('basic')
const previousProgress = ref('未投递')
const detailPages = [
  { id: 'basic', label: '基础信息' },
  { id: 'process', label: '投递流程' },
  { id: 'offer', label: 'Offer 信息' },
  { id: 'materials', label: '岗位材料' },
]

// ---------- helper functions (ported from original JS) ----------

function inputDate(v) {
  return inputDateChina(v)
}

function selectAdjacentPage(currentId, offset) {
  const currentIndex = detailPages.findIndex(page => page.id === currentId)
  const nextIndex = (currentIndex + offset + detailPages.length) % detailPages.length
  activePage.value = detailPages[nextIndex].id
  nextTick(() => document.getElementById(`detail-tab-${activePage.value}`)?.focus())
}

const PROGRESS_RANK = { '未投递': 0, '已投递': 1, '机考': 2, '面试': 3, OC: 4, '已挂': 4, '放弃': 4 }
const PROGRESS_TIME_FIELDS = [
  { rank: 1, key: 'apply_date', label: '投递时间' },
  { rank: 2, key: 'exam_date', label: '机考时间' },
  { rank: 3, key: 'interview1', label: '一面' },
  { rank: 3, key: 'interview2', label: '二面' },
  { rank: 3, key: 'interview3', label: '三面' },
  { rank: 3, key: 'warm', label: '保温时间' },
  { rank: 4, key: 'result_date', label: '结果时间' },
]

function handleProgressChange() {
  const oldRank = PROGRESS_RANK[previousProgress.value]
  const newRank = PROGRESS_RANK[form.progress]
  if (Number.isFinite(oldRank) && Number.isFinite(newRank) && newRank < oldRank) {
    const cleared = []
    PROGRESS_TIME_FIELDS.forEach(field => {
      if (field.rank > newRank && form[field.key]) {
        form[field.key] = ''
        cleared.push(field.label)
      }
    })
    if (cleared.length) toast.info('进展已回退，已清除：' + cleared.join('、'))
  }
  previousProgress.value = form.progress
}

function timelineKey(item) {
  return `${item.kind}-${item.id || item.label}-${item.event_ms || 0}`
}

function formatTimelineTime(value) {
  if (!value) return '时间未识别'
  const date = new Date(Number(value))
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleString('zh-CN', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hour12: false
  })
}

async function loadTimeline() {
  timelineLoading.value = true
  try {
    const data = await get(
      `/api/progress-tracker/records/${encodeURIComponent(activeRecordId.value)}/timeline`,
      { silent: true }
    )
    timeline.value = data.timeline || []
  } catch (_) {
    timeline.value = []
  } finally {
    timelineLoading.value = false
  }
}

async function openTimeline() {
  showTimeline.value = true
  await loadTimeline()
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
const activeRecordId = ref(props.recordId)
const initialFormSnapshot = ref('')
const recordDrafts = new Map()
const recordBaselines = new Map()

// ---------- computed ----------

const record = computed(() => {
  return store.records.find(r => r.record_id === activeRecordId.value) || null
})

const positionRecords = computed(() => {
  const company = String(record.value?.company || '').trim().toLocaleLowerCase('zh-CN')
  if (!company) return record.value ? [record.value] : []
  return store.records.filter(item => String(item.company || '').trim().toLocaleLowerCase('zh-CN') === company)
})
const { groupedRecords: detailPositionGroups, selectPosition: persistDetailPosition } = useRecordGroups(positionRecords)

function formSnapshot(value = form) {
  return JSON.stringify({ form: { ...value } })
}

function currentFormSnapshot() {
  return formSnapshot(form)
}

function rememberCurrentDraft() {
  if (!activeRecordId.value) return
  recordDrafts.set(activeRecordId.value, { ...form })
}

const isDirty = computed(() => {
  const currentChanged = Boolean(initialFormSnapshot.value) && currentFormSnapshot() !== initialFormSnapshot.value
  const otherChanged = [...recordDrafts.entries()].some(([recordId, draft]) => {
    if (recordId === activeRecordId.value) return false
    return formSnapshot(draft) !== recordBaselines.get(recordId)
  })
  return currentChanged || otherChanged
})

const isAppRecord = computed(() => isApplicationRecord(record.value || {}))

const shareMissingFields = computed(() => shareMissing(record.value || {}))

const shareDisabled = computed(() => shareMissingFields.value.length > 0)

const shareTitle = computed(() => {
  return shareDisabled.value ? '需补全：' + shareMissingFields.value.join('、') : ''
})

// ---------- actions ----------

function recordPayload(job = form.job) {
  return {
    company: form.company.trim(),
    job: String(job || '').trim(),
    city: form.city.trim(),
    batch: form.batch,
    progress: form.progress,
    directions: form.directions.split(/[，、,]/).map(value => value.trim()).filter(Boolean),
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
    resume_version: form.resume_version,
  }
}

async function addPosition() {
  const jobName = await dialog.prompt(
    '新岗位会继承当前记录的公司、城市、批次和流程信息，创建后将自动切换到新岗位。',
    {
      title: '增加子记录',
      inputLabel: '岗位名称',
      placeholder: '请输入岗位名称',
      confirmText: '确认创建',
      required: true,
      tone: 'info',
    },
  )
  const nextJob = String(jobName || '').trim()
  if (!nextJob) return
  if (!form.company.trim()) {
    activePage.value = 'basic'
    toast.error('请先填写公司名称')
    await nextTick()
    companyInput.value?.focus()
    return
  }
  const duplicate = positionRecords.value.some(item => String(item.job || '').trim() === nextJob)
  if (duplicate) {
    toast.error('该岗位子记录已存在')
    return
  }
  creatingPosition.value = true
  const previousIds = new Set(store.records.map(item => item.record_id))
  try {
    await post('/api/dashboard/records/' + encodeURIComponent(activeRecordId.value) + '/master/update', recordPayload())
    const savedSnapshot = currentFormSnapshot()
    recordBaselines.set(activeRecordId.value, savedSnapshot)
    recordDrafts.delete(activeRecordId.value)
    initialFormSnapshot.value = savedSnapshot
    await post('/api/dashboard/records/master', recordPayload(nextJob))
    await store.refresh()
    const created = store.records.find(item => !previousIds.has(item.record_id) && String(item.job || '').trim() === nextJob)
    if (!created) throw new Error('创建成功，但未能定位新增记录')
    switchDetailPosition(created)
    toast.success('已创建并切换到新岗位')
  } catch (err) {
    toast.error('创建子记录失败：' + err.message)
  } finally {
    creatingPosition.value = false
  }
}

async function handleSubmit() {
  if (!form.company.trim()) {
    activePage.value = 'basic'
    toast.error('请填写公司名称')
    await nextTick()
    companyInput.value?.focus()
    return false
  }
  submitting.value = true
  try {
    const payload = recordPayload()
    await post(`/api/dashboard/records/${encodeURIComponent(activeRecordId.value)}/master/update`, payload)
    await store.refresh()
    toast.success('记录已更新')
    initialFormSnapshot.value = currentFormSnapshot()
    recordBaselines.set(activeRecordId.value, initialFormSnapshot.value)
    recordDrafts.delete(activeRecordId.value)
    return true
  } catch (err) {
    toast.error('保存失败：' + err.message)
    return false
  } finally {
    submitting.value = false
  }
}

async function requestBackdropClose() {
  if (submitting.value) return
  if (!isDirty.value) {
    emit('close')
    return
  }
  const shouldSave = await dialog.confirm(
    '当前记录有尚未保存的修改，是否保存后关闭？',
    { title: '保存修改', tone: 'info', confirmText: '保存', cancelText: '不保存' },
  )
  if (shouldSave) {
    const saved = await handleSubmit()
    if (saved) emit('close')
  } else emit('close')
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
    const result = await post(`/api/ai/records/${encodeURIComponent(activeRecordId.value)}/enrich`, {})
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
    await post(`/api/dashboard/shared/records/from-personal/${encodeURIComponent(activeRecordId.value)}`)
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
    await post(`/api/dashboard/records/${encodeURIComponent(activeRecordId.value)}/remove`)
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
    const remaining = positionRecords.value.filter(item => item.record_id !== activeRecordId.value)
    await post(`/api/dashboard/records/${encodeURIComponent(activeRecordId.value)}/permanent-delete`)
    await store.refresh()
    toast.success('记录已删除')
    emit('saved')
    if (remaining.length) {
      activeRecordId.value = remaining[0].record_id
      loadRecordForm(remaining[0])
    } else {
      emit('close')
    }
  } catch (err) {
    toast.error('删除失败：' + err.message)
  }
}

// ---------- mount ----------

function loadRecordForm(r) {
  if (!r) return
  const draft = recordDrafts.get(r.record_id)
  if (draft) {
    Object.assign(form, draft)
    previousProgress.value = form.progress
    initialAiState.value = computeAiState()
    initialFormSnapshot.value = recordBaselines.get(r.record_id) || currentFormSnapshot()
    return
  }
  form.company = r.company || ''
  form.job = r.job || ''
  form.city = r.city || ''
  form.batch = r.batch || '秋招'
  form.directions = (Array.isArray(r.dir) ? r.dir : []).join('、')
  form.company_type = r.type || ''
  form.progress = (Array.isArray(r.progress) ? r.progress[0] : r.progress) || '未投递'
  previousProgress.value = form.progress
  form.url = r.url || ''
  form.priority = r.priority || '⭐⭐⭐'
  form.job_jd = r.job_jd || ''
  form.note = r.note || ''
  form.offer_total = r.offer_total || ''
  form.offer_base = r.offer_base || ''
  form.offer_bonus = r.offer_bonus || ''
  form.resume_version = r.resume_version || ''
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
  const snapshot = currentFormSnapshot()
  if (!recordBaselines.has(r.record_id)) recordBaselines.set(r.record_id, snapshot)
  initialFormSnapshot.value = recordBaselines.get(r.record_id)
}

function switchDetailPosition(position) {
  if (!position || position.record_id === activeRecordId.value) return
  rememberCurrentDraft()
  const group = detailPositionGroups.value[0]
  if (group) persistDetailPosition(group, position)
  activeRecordId.value = position.record_id
  loadRecordForm(position)
}

async function deletePosition(position) {
  switchDetailPosition(position)
  await nextTick()
  await deleteRecord()
}

onMounted(async () => {
  const r = record.value
  if (!r) {
    toast.error('未找到对应记录')
    emit('close')
    return
  }

  loadRecordForm(r)

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

<style scoped>
.record-detail-modal{display:flex;height:min(860px,92dvh);flex-direction:column;overflow:hidden}.record-detail-modal>.modal-hd,.detail-position-bar{flex:0 0 auto}.record-detail-modal>form{display:flex;min-height:0;flex:1;flex-direction:column}.record-detail-modal .modal-body{min-height:0;flex:1;padding-top:20px;overflow:auto;background:var(--bg)}.record-detail-modal :is(.detail-actions,.modal-ft){flex:0 0 auto}.position-add-btn{height:30px;padding:0 10px;white-space:nowrap}
.detail-position-bar{display:grid;gap:10px;padding:12px 18px 14px;border-bottom:1px solid var(--line);background:var(--bg)}.detail-position-heading{display:flex;align-items:center;justify-content:space-between;gap:16px}.detail-position-heading>div:first-child{display:grid;gap:3px}.detail-position-heading b{font-size:12px}.detail-position-heading span{color:var(--muted);font-size:9px}.detail-position-heading-actions{display:flex;min-width:0;align-items:center;gap:10px}.detail-position-heading strong{max-width:230px;overflow:hidden;color:var(--blue);font-size:10px;text-overflow:ellipsis;white-space:nowrap}.detail-position-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}.detail-position-item{display:grid;grid-template-columns:minmax(0,1fr) 30px;overflow:hidden;border:1px solid var(--line);border-radius:9px;background:var(--panel);transition:border-color .15s ease,background .15s ease}.detail-position-item:hover{border-color:var(--line2)}.detail-position-item.active{border-color:var(--blue);background:var(--blueS);box-shadow:inset 3px 0 var(--blue)}.detail-position-item>button:first-child{display:flex;min-width:0;align-items:center;justify-content:space-between;gap:12px;padding:9px 10px;border:0;color:var(--ink);text-align:left;background:transparent;font:inherit;cursor:pointer}.detail-position-title,.detail-position-meta{display:grid;min-width:0;gap:3px}.detail-position-title b,.detail-position-title small,.detail-position-meta small{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.detail-position-title b{font-size:11px}.detail-position-title small,.detail-position-meta small{color:var(--muted);font-size:8px}.detail-position-meta{max-width:44%;justify-items:end}.detail-position-meta em{color:var(--blue);font-size:9px;font-style:normal;font-weight:800}.detail-position-delete{border:0;border-left:1px solid var(--line);color:var(--muted);background:transparent;font-size:15px;cursor:pointer}.detail-position-delete:hover{color:var(--red);background:var(--redS)}
.detail-tabs{grid-template-columns:repeat(4,minmax(0,1fr));flex:0 0 auto;background:var(--bg)}.detail-page{display:none}.detail-page.active{display:grid}.detail-form-section{gap:14px}.detail-form-heading{display:flex;align-items:baseline;justify-content:space-between;gap:16px}.detail-form-heading h3{margin:0;color:var(--ink);font-size:13px}.detail-form-heading p{margin:0;color:var(--muted);font-size:9px}.detail-form-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));align-items:start;column-gap:18px;row-gap:16px}.detail-form-grid>.form-group{min-width:0;margin:0}.detail-form-grid>.form-group>label{display:block;margin-bottom:7px}.detail-form-grid :is(input,select,textarea){width:100%;box-sizing:border-box}.detail-field-wide,.record-detail-textarea{grid-column:1/-1}.record-detail-textarea textarea{min-height:126px;resize:vertical}
@media(max-width:700px){.record-detail-modal{height:96dvh}.detail-tabs .btn{min-width:0;padding-inline:4px}.detail-position-heading{align-items:flex-start;flex-direction:column;gap:8px}.detail-position-heading-actions{width:100%;justify-content:space-between}.detail-position-heading strong{max-width:60%}.detail-position-list,.detail-form-grid{grid-template-columns:1fr}.detail-field-wide,.record-detail-textarea{grid-column:auto}.detail-form-heading{align-items:flex-start;flex-direction:column;gap:3px}}
</style>
