<script setup>
import { computed, onMounted, ref } from 'vue'
import { get, post } from '@/utils/api'
import { useToastStore } from '@/stores/toast'

const emit = defineEmits(['close'])
const toast = useToastStore()
const preference = ref('')
const resumeFilename = ref('')
const resumes = ref([])
const loading = ref(false)
const result = ref(null)

const gradeTitle = { S: '强烈推荐', A: '优先推荐', B: '值得关注', C: '备选岗位' }
const items = computed(() => result.value?.items || [])

async function runRecommendation() {
  loading.value = true
  try {
    result.value = await post('/api/recommendations', {
      preference: preference.value,
      resume_filename: resumeFilename.value,
    })
    if (!items.value.length) toast.info('没有达到当前推荐门槛的岗位，可在设置中降低最低分。')
  } catch (error) {
    toast.error(error.message || '岗位筛选失败')
  } finally { loading.value = false }
}

function deadline(value) {
  if (!value) return '无截止日期'
  const date = new Date(value)
  return isNaN(date) ? '无截止日期' : `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

onMounted(async () => {
  try { resumes.value = (await get('/api/resumes')).files || [] } catch { resumes.value = [] }
})
</script>

<template>
  <div class="modal-mask show" @click.self="emit('close')">
    <div class="modal recommendation-modal">
      <div class="modal-hd">
        <div><h2>智能岗位筛选</h2><p>按输入偏好和已上传简历，从共享总表中分级推荐合适岗位。</p></div>
        <button class="icon-btn" @click="emit('close')" title="关闭">&times;</button>
      </div>
      <div class="modal-body recommendation-body">
        <div class="recommendation-form">
          <div class="form-group"><label for="recommend-preference">岗位偏好</label>
            <textarea id="recommend-preference" v-model="preference" rows="3" placeholder="例如：上海或杭州，嵌入式 Linux / BSP / 驱动，偏 C++，机器人或汽车电子方向"></textarea>
          </div>
          <div class="form-group"><label for="recommend-resume">关联简历（可选）</label>
            <select id="recommend-resume" v-model="resumeFilename"><option value="">不使用简历，仅按偏好筛选</option><option v-for="file in resumes" :key="file.name" :value="file.name">{{ file.name }}</option></select>
          </div>
          <button class="btn btn-primary" :disabled="loading" @click="runRecommendation">{{ loading ? '正在匹配…' : '开始智能筛选' }}</button>
        </div>

        <div v-if="result" class="recommendation-result">
          <div class="recommendation-summary">扫描 {{ result.scanned }} 条共享岗位 · {{ result.resume_used ? '已结合简历' : '按岗位偏好' }} · {{ items.length }} 条推荐</div>
          <div v-if="!items.length" class="center muted">没有匹配岗位。可补充偏好、选择简历，或在设置中降低最低推荐分。</div>
          <article v-for="job in items" :key="job.record_id" class="recommendation-card">
            <div class="recommendation-grade" :class="'grade-' + job.recommendation_grade"><b>{{ job.recommendation_grade }}</b><span>{{ job.recommendation_score }} 分</span></div>
            <div class="recommendation-main"><h3>{{ job.company || '—' }} · {{ job.job || '—' }}</h3><p>{{ gradeTitle[job.recommendation_grade] }} · {{ job.recommendation_reason }}</p><div class="recommendation-meta"><span>{{ job.city || '地点待定' }}</span><span>{{ (job.dir || []).join(' / ') || '方向待补充' }}</span><span>截止：{{ deadline(job.deadline) }}</span></div></div>
            <a v-if="job.url" :href="job.url" target="_blank" rel="noreferrer" class="btn">查看岗位</a>
          </article>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.recommendation-modal { width:min(860px,96vw); }
.recommendation-body { display:grid; gap:14px; max-height:75vh; overflow:auto; }
.recommendation-form { display:grid; grid-template-columns:minmax(0,1fr) 235px auto; align-items:end; gap:10px; padding:12px; border:2px solid var(--ink); background:var(--bg); box-shadow:3px 3px 0 var(--ink); }
.recommendation-form textarea { resize:vertical; min-height:74px; }
.recommendation-result { display:grid; gap:8px; }
.recommendation-summary { font:900 11px var(--mono); color:var(--muted); padding:4px 1px; }
.recommendation-card { display:flex; gap:12px; align-items:center; border:1px solid var(--line2); background:var(--panel); padding:11px; }
.recommendation-grade { width:48px; min-height:48px; display:grid; place-content:center; text-align:center; border:2px solid var(--ink); font-family:var(--mono); background:var(--amberS); flex:none; }
.recommendation-grade b { font-size:20px; line-height:1; }.recommendation-grade span { font-size:9px; margin-top:3px; }
.grade-S { background:var(--blue); color:#fff; }.grade-A { background:var(--greenS); }.grade-C { background:var(--bg); color:var(--muted); }
.recommendation-main { flex:1; min-width:0; }.recommendation-main h3 { font-size:14px; margin:0 0 4px; }.recommendation-main p { margin:0; font-size:11px; color:var(--sub); }.recommendation-meta { display:flex; flex-wrap:wrap; gap:8px; margin-top:7px; color:var(--muted); font-size:10px; }
@media (max-width:720px) { .recommendation-form { grid-template-columns:1fr; }.recommendation-card { align-items:flex-start; flex-wrap:wrap; }.recommendation-card .btn { margin-left:60px; } }
</style>
