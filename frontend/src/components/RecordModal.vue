<script setup>
import { ref, watch, onMounted, computed } from 'vue'
import { useDashboardStore } from '@/stores/dashboard'
import { useToastStore } from '@/stores/toast'

const props = defineProps({
  recordId: { type: [String, Number], default: null }
})

const emit = defineEmits(['close', 'saved'])

const store = useDashboardStore()
const toast = useToastStore()

/* ---------- form fields ---------- */
const company = ref('')
const job = ref('')
const city = ref('')
const batch = ref('秋招')
const progress = ref('已投递')
const url = ref('')
const loading = ref(false)

/* ---------- date fields (text <-> date toggle) ---------- */
const applyDate = ref('')
const examDate = ref('')
const interview1 = ref('')
const interview2 = ref('')
const interview3 = ref('')
const warm = ref('')
const resultDate = ref('')
const deadline = ref('')

const activeDates = ref(new Set())

function activateDate(name) {
  activeDates.value = new Set(activeDates.value).add(name)
}

function deactivateDate(name) {
  if (!getDateValue(name)) {
    const s = new Set(activeDates.value)
    s.delete(name)
    activeDates.value = s
  }
}

function dateType(name) {
  return activeDates.value.has(name) ? 'date' : 'text'
}

function getDateValue(name) {
  const map = {
    apply_date: applyDate,
    exam_date: examDate,
    interview1,
    interview2,
    interview3,
    warm,
    result_date: resultDate,
    deadline,
  }
  return map[name].value
}

function inputDate(v) {
  if (!v) return ''
  const d = new Date(v)
  if (isNaN(d)) return String(v).slice(0, 10)
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
}

/* ---------- modal state ---------- */
const isEditing = computed(() => !!props.recordId)

const modalTitle = computed(() => isEditing.value ? '编辑投递记录' : '新增投递记录')
const modalDesc = computed(() => isEditing.value
  ? '修改后将保存到本地总表。'
  : '在本地总表中新建记录，公司名称可以重复，时间均可留空。'
)
const submitText = computed(() => isEditing.value ? '保存修改' : '保存记录')

/* ---------- load record for editing ---------- */
function loadRecord(recordId) {
  if (!recordId) return
  const records = store.records || []
  const r = records.find(rec => String(rec.record_id) === String(recordId))
  if (!r) return

  company.value = r.company || ''
  job.value = r.job || ''
  city.value = r.city || ''
  batch.value = r.batch || '秋招'
  progress.value = (Array.isArray(r.progress) ? r.progress[0] : '') || '已投递'
  url.value = r.url || ''

  applyDate.value = inputDate(r.apply_date)
  examDate.value = inputDate(r.exam_date)
  interview1.value = inputDate(r.interview1)
  interview2.value = inputDate(r.interview2)
  interview3.value = inputDate(r.interview3)
  warm.value = inputDate(r.warm)
  resultDate.value = inputDate(r.result)
  deadline.value = inputDate(r.deadline)

  // Activate date inputs that have a value
  const s = new Set()
  if (applyDate.value) s.add('apply_date')
  if (examDate.value) s.add('exam_date')
  if (interview1.value) s.add('interview1')
  if (interview2.value) s.add('interview2')
  if (interview3.value) s.add('interview3')
  if (warm.value) s.add('warm')
  if (resultDate.value) s.add('result_date')
  if (deadline.value) s.add('deadline')
  activeDates.value = s
}

function resetForm() {
  company.value = ''
  job.value = ''
  city.value = ''
  batch.value = '秋招'
  progress.value = '已投递'
  url.value = ''
  applyDate.value = ''
  examDate.value = ''
  interview1.value = ''
  interview2.value = ''
  interview3.value = ''
  warm.value = ''
  resultDate.value = ''
  deadline.value = ''
  activeDates.value = new Set()
}

watch(() => props.recordId, (val) => {
  if (val && store.data) {
    loadRecord(val)
  } else if (!val) {
    resetForm()
  }
})

onMounted(async () => {
  if (!store.data) await store.fetch()
  if (props.recordId) loadRecord(props.recordId)
})

/* ---------- close ---------- */
function closeModal() {
  emit('close')
}

function handleOverlayClick(e) {
  if (e.target === e.currentTarget) closeModal()
}

/* ---------- submit ---------- */
async function submitRecord() {
  loading.value = true
  try {
    const payload = {
      company: company.value.trim(),
      job: job.value.trim(),
      city: city.value.trim(),
      batch: batch.value,
      apply_date: applyDate.value || null,
      exam_date: examDate.value || null,
      interview1: interview1.value || null,
      interview2: interview2.value || null,
      interview3: interview3.value || null,
      warm: warm.value || null,
      result_date: resultDate.value || null,
      deadline: deadline.value || null,
      progress: progress.value,
      url: url.value.trim() || null,
    }

    const path = props.recordId
      ? `/api/dashboard/records/${encodeURIComponent(props.recordId)}/update`
      : '/api/dashboard/records'

    const token = localStorage.getItem('rb_token')
    const res = await fetch(path, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(payload),
    })

    if (!res.ok) {
      const data = await res.json().catch(() => ({}))
      throw new Error(data.detail || `HTTP ${res.status}`)
    }

    const result = await res.json()

    if (result.dashboard) {
      store.data = result.dashboard
    } else {
      await store.fetch()
    }

    toast.success(result.message || '记录已保存')
    resetForm()
    emit('saved')
  } catch (err) {
    toast.error('保存失败：' + err.message)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="modal-mask show" @click.self="$emit('close')">
    <div class="modal" style="width:min(640px,94vw)">
      <div class="modal-hd">
        <div>
          <h2>{{ modalTitle }}</h2>
          <p>{{ modalDesc }}</p>
        </div>
        <button class="icon-btn" title="关闭" @click="closeModal">&times;</button>
      </div>
      <form @submit.prevent="submitRecord">
        <div class="modal-body">
          <div class="grid-2">
            <div class="form-group">
              <label for="record-company">公司</label>
              <input id="record-company" v-model.trim="company" required maxlength="100">
            </div>
            <div class="form-group">
              <label for="record-job">目标岗位</label>
              <input id="record-job" v-model.trim="job" required maxlength="500">
            </div>
            <div class="form-group">
              <label for="record-city">城市</label>
              <input id="record-city" v-model.trim="city" required maxlength="200">
            </div>
            <div class="form-group">
              <label for="record-batch">批次</label>
              <select id="record-batch" v-model="batch" required>
                <option value="秋招">秋招</option>
                <option value="提前批">提前批</option>
              </select>
            </div>
            <div class="form-group">
              <label for="record-date">投递时间</label>
              <input
                id="record-date"
                v-model="applyDate"
                :type="dateType('apply_date')"
                class="optional-date"
                @focus="activateDate('apply_date')"
                @blur="deactivateDate('apply_date')"
              >
            </div>
            <div class="form-group">
              <label for="record-progress">进展</label>
              <select id="record-progress" v-model="progress" required>
                <option value="已投递">已投递</option>
                <option value="机考">机考</option>
                <option value="面试">面试</option>
                <option value="OC">OC</option>
                <option value="已挂">已挂</option>
                <option value="放弃">放弃</option>
              </select>
            </div>
            <div class="form-group">
              <label for="record-url">入口网址</label>
              <input id="record-url" v-model.trim="url" type="url" placeholder="https://...（选填）">
            </div>
            <div class="form-group">
              <label for="record-exam">机考</label>
              <input
                id="record-exam"
                v-model="examDate"
                :type="dateType('exam_date')"
                class="optional-date"
                @focus="activateDate('exam_date')"
                @blur="deactivateDate('exam_date')"
              >
            </div>
            <div class="form-group">
              <label for="record-interview1">一面</label>
              <input
                id="record-interview1"
                v-model="interview1"
                :type="dateType('interview1')"
                class="optional-date"
                @focus="activateDate('interview1')"
                @blur="deactivateDate('interview1')"
              >
            </div>
            <div class="form-group">
              <label for="record-interview2">二面</label>
              <input
                id="record-interview2"
                v-model="interview2"
                :type="dateType('interview2')"
                class="optional-date"
                @focus="activateDate('interview2')"
                @blur="deactivateDate('interview2')"
              >
            </div>
            <div class="form-group">
              <label for="record-interview3">三面</label>
              <input
                id="record-interview3"
                v-model="interview3"
                :type="dateType('interview3')"
                class="optional-date"
                @focus="activateDate('interview3')"
                @blur="deactivateDate('interview3')"
              >
            </div>
            <div class="form-group">
              <label for="record-warm">保温</label>
              <input
                id="record-warm"
                v-model="warm"
                :type="dateType('warm')"
                class="optional-date"
                @focus="activateDate('warm')"
                @blur="deactivateDate('warm')"
              >
            </div>
            <div class="form-group">
              <label for="record-result">结果</label>
              <input
                id="record-result"
                v-model="resultDate"
                :type="dateType('result_date')"
                class="optional-date"
                @focus="activateDate('result_date')"
                @blur="deactivateDate('result_date')"
              >
            </div>
            <div class="form-group">
              <label for="record-deadline">截止</label>
              <input
                id="record-deadline"
                v-model="deadline"
                :type="dateType('deadline')"
                class="optional-date"
                @focus="activateDate('deadline')"
                @blur="deactivateDate('deadline')"
              >
            </div>
          </div>
        </div>
        <div class="modal-ft">
          <button class="btn" type="button" @click="closeModal">取消</button>
          <button class="btn btn-primary" :disabled="loading" type="submit">{{ loading ? '保存中…' : submitText }}</button>
        </div>
      </form>
    </div>
  </div>
</template>
