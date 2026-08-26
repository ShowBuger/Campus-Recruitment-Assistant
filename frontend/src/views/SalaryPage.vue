<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { get, post } from '@/utils/api'
import { PhCurrencyCny, PhGearSix, PhMagnifyingGlass, PhX } from '@phosphor-icons/vue'

const auth = useAuthStore()
const toast = useToastStore()
const loading = ref(false)
const loadingMore = ref(false)
const error = ref('')
const items = ref([])
const total = ref(0)
const sourceTotal = ref(0)
const sheetName = ref('')
const page = ref(1)
const pageSize = 50
const company = ref('')
const job = ref('')
const city = ref('')
const submittedFilters = ref({ company: '', job: '', city: '' })
const source = ref('feishu')
const attribution = ref('')
const hasSearched = ref(false)
const tokenDialogOpen = ref(false)
const tokenConfigured = ref(false)
const maskedToken = ref('')
const usingPersonalToken = ref(false)
const tokenInput = ref('')
const savingToken = ref(false)
const tableScroll = ref(null)
const hasMore = computed(() => items.value.length < total.value)

function queryString() {
  const params = new URLSearchParams({ page: String(page.value), page_size: String(pageSize) })
  for (const [name, value] of Object.entries(submittedFilters.value)) {
    if (value) params.set(name, value)
  }
  return params.toString()
}

async function load({ append = false } = {}) {
  if (!auth.isLoggedIn) return
  if (append) loadingMore.value = true
  else loading.value = true
  error.value = ''
  try {
    const endpoint = hasSearched.value ? '/api/salaries/offershow' : '/api/salaries'
    const data = await get(`${endpoint}?${queryString()}`, { timeout: 130000, retries: 0 })
    items.value = append ? [...items.value, ...(data.items || [])] : (data.items || [])
    total.value = Number(data.total || 0)
    sourceTotal.value = Number(data.source_total || 0)
    sheetName.value = data.sheet_name || ''
    source.value = data.source || 'feishu'
    attribution.value = data.attribution || ''
    if (data.warning) toast.error(data.warning)
  } catch (e) {
    if (append) page.value = Math.max(1, page.value - 1)
    error.value = e.message || '薪资数据加载失败'
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

async function search() {
  submittedFilters.value = { company: company.value.trim(), job: job.value.trim(), city: city.value.trim() }
  if (!Object.values(submittedFilters.value).some(Boolean)) {
    hasSearched.value = false
    items.value = []
    total.value = 0
    sourceTotal.value = 0
    return
  }
  hasSearched.value = true
  page.value = 1
  await load()
  await nextTick()
  if (tableScroll.value) tableScroll.value.scrollTop = 0
}
async function clearSearch() {
  company.value = ''
  job.value = ''
  city.value = ''
  submittedFilters.value = { company: '', job: '', city: '' }
  hasSearched.value = false
  items.value = []
  total.value = 0
  sourceTotal.value = 0
  sheetName.value = ''
  error.value = ''
}
async function loadMore() {
  if (!hasMore.value || loading.value || loadingMore.value) return
  page.value += 1
  await load({ append: true })
}
function onTableScroll(event) {
  const target = event.currentTarget
  if (target.scrollHeight - target.scrollTop - target.clientHeight <= 120) loadMore()
}
async function loadTokenStatus() {
  try {
    const data = await get('/api/salaries/offershow/config')
    tokenConfigured.value = Boolean(data.configured)
    maskedToken.value = data.masked_token || ''
    usingPersonalToken.value = Boolean(data.using_personal)
  } catch { /* 页面主体会单独处理权限和网络错误 */ }
}
function openTokenDialog() {
  tokenInput.value = ''
  tokenDialogOpen.value = true
}
async function saveToken() {
  if (!tokenInput.value.trim()) return toast.error('请输入 OfferShow Token')
  savingToken.value = true
  try {
    const data = await post('/api/salaries/offershow/config', { token: tokenInput.value.trim() })
    tokenConfigured.value = true
    maskedToken.value = data.masked_token || ''
    usingPersonalToken.value = Boolean(data.using_personal)
    tokenInput.value = ''
    tokenDialogOpen.value = false
    toast.success(data.message || 'Token 已保存')
  } catch (e) {
    toast.error(e.message || 'Token 保存失败')
  } finally {
    savingToken.value = false
  }
}

async function usePublicToken() {
  savingToken.value = true
  try {
    const data = await post('/api/salaries/offershow/config', { token: '' })
    tokenConfigured.value = Boolean(data.configured)
    maskedToken.value = data.masked_token || ''
    usingPersonalToken.value = false
    tokenInput.value = ''
    toast.success(data.message || '已恢复使用公共 Token')
  } catch (e) {
    toast.error(e.message || '切换公共 Token 失败')
  } finally {
    savingToken.value = false
  }
}

onMounted(loadTokenStatus)
</script>

<template>
  <section v-if="auth.isLoggedIn" class="page active salary-page">
    <header class="salary-page-head">
      <div><h2>薪资查询</h2><p>{{ hasSearched ? `${sheetName} · 已找到 ${sourceTotal} 条匹配记录` : '按公司、岗位和城市组合查询薪资信息' }}</p></div>
      <div class="salary-head-actions">
        <button class="btn salary-token-config" type="button" @click="openTokenDialog"><PhGearSix :size="16" />配置 Token</button>
      </div>
    </header>

    <div class="card salary-shell">
      <div class="salary-tools">
        <label class="salary-keyword"><PhMagnifyingGlass :size="16" /><input v-model="company" type="search" placeholder="公司" aria-label="按公司查询薪资" @keyup.enter="search"></label>
        <label class="salary-keyword"><PhMagnifyingGlass :size="16" /><input v-model="job" type="search" placeholder="岗位" aria-label="按岗位查询薪资" @keyup.enter="search"></label>
        <label class="salary-keyword"><PhMagnifyingGlass :size="16" /><input v-model="city" type="search" placeholder="城市" aria-label="按城市查询薪资" @keyup.enter="search"></label>
        <button type="button" class="btn salary-search-submit" :disabled="loading" @click="search">查询</button>
        <button v-if="company || job || city || hasSearched" type="button" class="salary-search-clear" @click="clearSearch">清除搜索</button>
        <span v-if="hasSearched">{{ total }} / {{ sourceTotal }} 条记录</span>
      </div>

      <div v-if="!hasSearched" class="salary-state salary-empty"><PhMagnifyingGlass :size="34" weight="duotone" /><b>搜索后显示薪资信息</b><span>请至少填写公司、岗位或城市中的一项，然后点击查询。</span></div>
      <div v-else-if="loading" class="salary-state"><i></i><i></i><i></i><span>正在整理薪资数据</span></div>
      <div v-else-if="error" class="salary-state salary-error"><PhCurrencyCny :size="32" weight="duotone" /><b>暂时无法读取薪资数据</b><span>{{ error }}</span><button class="btn" @click="load">重新加载</button></div>
      <div v-else class="salary-results">
        <div class="salary-result-meta"><b>{{ total }} 条匹配结果</b><span>{{ source === 'combined' ? attribution : '数据来自公开统计，仅供求职决策参考' }}</span></div>
        <div ref="tableScroll" class="tbl salary-table-scroll" @scroll="onTableScroll">
          <table class="data-table salary-table">
            <thead><tr><th>公司</th><th>Offer 薪资</th><th>城市</th><th>个人学历</th><th>岗位</th><th>时间</th><th>来源</th></tr></thead>
            <tbody>
              <tr v-if="!items.length"><td colspan="7" class="center">没有匹配的薪资记录</td></tr>
              <tr v-for="item in items" :key="item.id">
                <td class="salary-company">{{ item.company }}</td>
                <td><strong class="salary-value">{{ item.salary }}</strong></td>
                <td>{{ item.city || '-' }}</td>
                <td>{{ item.education || '-' }}</td>
                <td>{{ item.job || '-' }}</td>
                <td>{{ item.year || '-' }}</td>
                <td><span class="salary-source" :class="`salary-source-${item.source || 'sheet'}`">{{ item.source === 'offershow' ? 'OfferShow' : '总表' }}</span></td>
              </tr>
              <tr v-if="hasMore"><td colspan="7" class="center salary-load-more">{{ loadingMore ? '正在加载更多记录' : '继续向下滚动，加载更多记录' }}</td></tr>
            </tbody>
          </table>
        </div>
        <footer class="salary-pagination"><span>已显示 {{ items.length }} / {{ total }} 条；向下滚动自动加载更多。</span></footer>
      </div>
    </div>

    <div v-if="tokenDialogOpen" class="salary-token-mask" @click.self="tokenDialogOpen = false">
      <div class="salary-token-dialog" role="dialog" aria-modal="true" aria-labelledby="salary-token-title">
        <div class="salary-token-title"><div><h3 id="salary-token-title">配置 OfferShow Token</h3><p>未配置个人 Token 时自动使用系统公共 Token</p></div><button type="button" aria-label="关闭" @click="tokenDialogOpen = false"><PhX :size="18" /></button></div>
        <div v-if="tokenConfigured" class="salary-token-current">当前使用：{{ usingPersonalToken ? '个人 Token' : '公共 Token' }} · {{ maskedToken }}</div>
        <label class="salary-token-field"><span>Access Token</span><textarea v-model="tokenInput" rows="5" autocomplete="off" spellcheck="false" placeholder="粘贴 OfferShow localStorage 中的 usertoken"></textarea></label>
        <p class="salary-token-hint">请先前往 <a href="https://www.offershow.cn" target="_blank" rel="noopener noreferrer">OfferShow 官网</a> 登录，然后从浏览器 Local Storage 复制 usertoken。个人 Token 仅保存在服务器，不会返回前端。</p>
        <div class="salary-token-actions"><button v-if="usingPersonalToken" type="button" class="btn" :disabled="savingToken" @click="usePublicToken">使用公共 Token</button><button type="button" class="btn" @click="tokenDialogOpen = false">取消</button><button type="button" class="btn primary" :disabled="savingToken" @click="saveToken">{{ savingToken ? '保存中' : '保存个人 Token' }}</button></div>
      </div>
    </div>
  </section>
  <section v-else class="page active"><div class="salary-state salary-error"><b>请先登录</b><span>登录后即可使用薪资查询。</span></div></section>
</template>

<style scoped>
.salary-page{min-width:0}.salary-page-head{display:flex;align-items:flex-end;justify-content:space-between;gap:20px;margin-bottom:16px}.salary-page-head h2{margin:0;color:var(--ink);font-size:26px;letter-spacing:-.03em}.salary-page-head p{margin:6px 0 0;color:var(--muted);font-size:11px}.salary-head-actions{display:flex;gap:9px}.salary-refresh,.salary-token-config{display:flex;align-items:center;gap:7px}.spinning{animation:salary-spin .8s linear infinite}.salary-shell{overflow:hidden;border-radius:16px}.salary-tools{display:flex;align-items:center;gap:10px;padding:13px 14px;border-bottom:1px solid var(--line);background:var(--panel)}.salary-tools>span{margin-left:auto;color:var(--sub);font-size:10px;white-space:nowrap}.salary-keyword{position:relative;display:block;flex:1;min-width:260px}.salary-keyword svg{position:absolute;top:11px;left:11px;color:var(--muted)}.salary-keyword input{width:100%;height:38px;padding:0 34px;border:1px solid var(--line2);border-radius:9px;outline:0;background:var(--bg);color:var(--ink);font:11px var(--font)}.salary-keyword input:focus{border-color:var(--blue);box-shadow:0 0 0 3px var(--blueS)}.salary-search-submit{height:38px}.salary-search-clear{height:32px;padding:0 8px;border:0;background:transparent;color:var(--blue);font:700 10px var(--font);cursor:pointer}.salary-result-meta{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px 14px;color:var(--muted);background:var(--bg);font-size:10px}.salary-result-meta b{color:var(--ink);font-size:11px}.salary-table-scroll{max-height:calc(100dvh - 310px);overflow:auto}.salary-table{min-width:780px}.salary-table th{position:sticky;top:0;z-index:2;background:var(--bg)}.salary-table td{height:47px}.salary-company{font-weight:850}.salary-value{color:var(--blue);font-size:12px}.salary-load-more{height:42px!important;color:var(--muted);font-size:10px;background:var(--bg)}.salary-pagination{display:flex;min-height:56px;align-items:center;justify-content:flex-end;padding:10px 14px;border-top:1px solid var(--line);background:var(--bg);color:var(--muted);font-size:10px}.salary-state{display:grid;min-height:320px;place-content:center;justify-items:center;gap:10px;padding:30px;color:var(--muted);text-align:center}.salary-state>i{width:min(520px,70vw);height:16px;border-radius:5px;background:var(--line);animation:salary-pulse 1.2s ease-in-out infinite}.salary-state>i:nth-child(2){width:min(430px,60vw)}.salary-state>i:nth-child(3){width:min(480px,65vw)}.salary-error b{color:var(--ink)}.salary-error span{max-width:540px;line-height:1.6}.salary-token-mask{position:fixed;inset:0;z-index:1200;display:grid;place-items:center;padding:20px;background:rgba(15,23,42,.42);backdrop-filter:blur(4px)}.salary-token-dialog{width:min(560px,100%);padding:20px;border:1px solid var(--line2);border-radius:16px;background:var(--panel);box-shadow:0 20px 60px rgba(15,23,42,.22)}.salary-token-title{display:flex;align-items:flex-start;justify-content:space-between;gap:16px}.salary-token-title h3{margin:0;color:var(--ink);font-size:17px}.salary-token-title p{margin:6px 0 0;color:var(--muted);font-size:10px}.salary-token-title button{display:grid;width:30px;height:30px;place-items:center;border:0;background:transparent;color:var(--muted);cursor:pointer}.salary-token-current{margin-top:16px;padding:9px 11px;border-radius:8px;background:var(--blueS);color:var(--blue);font-size:10px}.salary-token-field{display:grid;gap:7px;margin-top:16px;color:var(--ink);font-size:11px;font-weight:700}.salary-token-field textarea{resize:vertical;min-height:105px;padding:11px;border:1px solid var(--line2);border-radius:9px;outline:0;background:var(--bg);color:var(--ink);font:10px/1.5 monospace}.salary-token-field textarea:focus{border-color:var(--blue);box-shadow:0 0 0 3px var(--blueS)}.salary-token-hint{margin:9px 0 0;color:var(--muted);font-size:9px;line-height:1.6}.salary-token-actions{display:flex;justify-content:flex-end;gap:9px;margin-top:18px}@keyframes salary-spin{to{transform:rotate(360deg)}}@keyframes salary-pulse{50%{opacity:.45}}@media(max-width:700px){.salary-page-head{align-items:flex-start;flex-direction:column}.salary-head-actions{width:100%}.salary-head-actions .btn{flex:1;justify-content:center}.salary-tools{flex-wrap:wrap}.salary-keyword{min-width:calc(100% - 70px)}.salary-tools>span{width:100%;margin-left:0}.salary-result-meta{align-items:flex-start;flex-direction:column}.salary-table-scroll{max-height:calc(100dvh - 350px)}}@media(prefers-reduced-motion:reduce){.spinning,.salary-state>i{animation:none}}
.salary-table{min-width:860px}.salary-source{display:inline-flex;padding:4px 8px;border-radius:999px;font-size:9px;font-weight:800;white-space:nowrap}.salary-source-sheet{background:rgba(36,91,235,.1);color:var(--blue)}.salary-source-offershow{background:rgba(16,185,129,.12);color:#059669}.salary-tools{display:grid;grid-template-columns:repeat(3,minmax(150px,1fr)) auto auto auto}.salary-tools .salary-keyword{min-width:0}.salary-tools>span{margin-left:0}@media(max-width:900px){.salary-tools{grid-template-columns:1fr 1fr}.salary-tools>span{width:auto}}@media(max-width:600px){.salary-tools{grid-template-columns:1fr}.salary-tools>span{width:100%}}
</style>
