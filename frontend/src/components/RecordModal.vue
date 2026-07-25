<script setup>
import { ref } from 'vue'
import { useDashboardStore } from '@/stores/dashboard'
import { useToastStore } from '@/stores/toast'

const emit = defineEmits(['close', 'saved'])
const store = useDashboardStore()
const toast = useToastStore()
const loading = ref(false)

const editId = ref('')
const company = ref(''), job = ref(''), city = ref(''), batch = ref('秋招'), progress = ref('已投递'), url = ref('')
const applyDate = ref(''), examDate = ref(''), interview1 = ref(''), interview2 = ref(''), interview3 = ref(''), warm = ref(''), resultDate = ref(''), deadline = ref('')

const dateIds = ['record-date','record-exam','record-interview1','record-interview2','record-interview3','record-warm','record-result','record-deadline']
const dateRefs = { 'record-date': applyDate, 'record-exam': examDate, 'record-interview1': interview1, 'record-interview2': interview2, 'record-interview3': interview3, 'record-warm': warm, 'record-result': resultDate, 'record-deadline': deadline }

function onFocus(e) { e.target.type = 'date'; try { e.target.showPicker?.() } catch {} }
function onBlur(e) { if (!e.target.value) e.target.type = 'text' }
function inputDate(ts) { if (!ts) return ''; const d = new Date(ts); return isNaN(d) ? '' : new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10) }

function reset() {
  editId.value = ''; company.value = ''; job.value = ''; city.value = ''; batch.value = '秋招'; progress.value = '已投递'; url.value = ''
  dateIds.forEach(id => { const el = document.getElementById(id); if (el) { el.type = 'text'; el.value = '' } })
}

async function submit() {
  if (!company.value.trim()) { toast.error('请填写公司名称'); return }
  loading.value = true
  const payload = {
    company: company.value.trim(), job: job.value.trim(), city: city.value.trim(), batch: batch.value,
    apply_date: applyDate.value || null, exam_date: examDate.value || null,
    interview1: interview1.value || null, interview2: interview2.value || null, interview3: interview3.value || null,
    warm: warm.value || null, result_date: resultDate.value || null, deadline: deadline.value || null,
    progress: progress.value, url: url.value.trim() || null
  }
  try {
    const r = await fetch(`/api/dashboard/records${editId.value ? '/' + encodeURIComponent(editId.value) + '/update' : ''}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${localStorage.getItem('rb_token')}` },
      body: JSON.stringify(payload)
    })
    if (!r.ok) throw new Error((await r.json()).detail || '保存失败')
    const data = await r.json()
    if (data.dashboard) store.data = data.dashboard; else await store.fetch()
    toast.success(data.message || '记录已保存')
    reset(); emit('saved'); emit('close')
  } catch (e) { toast.error(e.message) }
  finally { loading.value = false }
}

defineExpose({ editId, company, job, city, batch, progress, url, applyDate, examDate, interview1, interview2, interview3, warm, resultDate, deadline, inputDate, reset })
</script>

<template>
  <div class="modal-mask show" @click.self="emit('close')">
    <div class="modal">
      <div class="modal-hd"><div><h2>{{ editId ? '编辑投递记录' : '新增投递记录' }}</h2><p>{{ editId ? '修改后将保存到本地总表。' : '在本地总表中新建记录，公司名称可以重复，时间均可留空。' }}</p></div><button class="icon-btn" @click="emit('close')" title="关闭">&times;</button></div>
      <form @submit.prevent="submit">
        <div class="modal-body">
          <div class="grid-2">
            <div class="form-group"><label for="record-company">公司</label><input id="record-company" v-model="company" required maxlength="100"></div>
            <div class="form-group"><label for="record-job">目标岗位</label><input id="record-job" v-model="job" maxlength="200"></div>
            <div class="form-group"><label for="record-city">城市</label><input id="record-city" v-model="city" maxlength="100"></div>
            <div class="form-group"><label for="record-batch">批次</label><select id="record-batch" v-model="batch"><option value="秋招">秋招</option><option value="提前批">提前批</option></select></div>
            <div class="form-group"><label for="record-date">投递时间</label><input id="record-date" v-model="applyDate" type="text" @focus="onFocus" @blur="onBlur"></div>
            <div class="form-group"><label for="record-exam">机考时间</label><input id="record-exam" v-model="examDate" type="text" @focus="onFocus" @blur="onBlur"></div>
            <div class="form-group"><label for="record-interview1">一面</label><input id="record-interview1" v-model="interview1" type="text" @focus="onFocus" @blur="onBlur"></div>
            <div class="form-group"><label for="record-interview2">二面</label><input id="record-interview2" v-model="interview2" type="text" @focus="onFocus" @blur="onBlur"></div>
            <div class="form-group"><label for="record-interview3">三面</label><input id="record-interview3" v-model="interview3" type="text" @focus="onFocus" @blur="onBlur"></div>
            <div class="form-group"><label for="record-warm">保温</label><input id="record-warm" v-model="warm" type="text" @focus="onFocus" @blur="onBlur"></div>
            <div class="form-group"><label for="record-result">结果时间</label><input id="record-result" v-model="resultDate" type="text" @focus="onFocus" @blur="onBlur"></div>
            <div class="form-group"><label for="record-deadline">截止</label><input id="record-deadline" v-model="deadline" type="text" @focus="onFocus" @blur="onBlur"></div>
            <div class="form-group"><label for="record-progress">进展</label><select id="record-progress" v-model="progress"><option value="已投递">已投递</option><option value="机考">机考</option><option value="面试">面试</option><option value="OC">OC</option><option value="已挂">已挂</option><option value="放弃">放弃</option></select></div>
            <div class="form-group"><label for="record-url">入口网址</label><input id="record-url" v-model="url" placeholder="https://..."></div>
          </div>
        </div>
        <div class="modal-ft"><button class="btn" type="button" @click="emit('close')">取消</button><button class="btn btn-primary" type="submit" :disabled="loading">{{ loading ? '...' : '保存记录' }}</button></div>
      </form>
    </div>
  </div>
</template>
