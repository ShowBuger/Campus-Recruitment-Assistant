<script setup>
import { ref, onMounted } from 'vue'
import { useDashboardStore } from '@/stores/dashboard'
import { useToastStore } from '@/stores/toast'
import { useDialogStore } from '@/stores/dialog'
import ProgressBadge from '@/components/ProgressBadge.vue'
import TooltipCell from '@/components/TooltipCell.vue'
import { post } from '@/utils/api'
import { boardDwellChina } from '@/utils/date'

const store = useDashboardStore()
const toast = useToastStore()
const dialog = useDialogStore()
const dragRid = ref('')

/* ---------- 常量 ---------- */
var BOARD_COLUMNS = ['已投递', '机考', '面试', 'OC', '已挂', '放弃']
var _PROGRESS_ORDER_BOARD = ['未投递', '已投递', '机考', '面试', 'OC', '已挂', '放弃']

/* 进展→时间线字段映射：用于计算停留 & 拖拽时写日期 */
var BOARD_DATE_FIELD = {
  '已投递': { get: r => r.apply_date, set: '投递时间', label: '投递时间' },
  '机考': { get: r => r.exam_date, set: '机考时间', label: '机考时间' },
  '面试': { get: r => Math.max(r.interview1 || 0, r.interview2 || 0, r.interview3 || 0) || null, set: '一面', label: '面试时间' },
  'OC': { get: r => r.result, set: '结果', label: '结果时间' },
  '已挂': { get: r => r.result, set: '结果', label: '结果时间' },
  '放弃': { get: r => r.result, set: '结果', label: '结果时间' },
}

var DAY = 86400000

function toArray(v) { return Array.isArray(v) ? v : (v ? [v] : []) }

function applicationRecords() { return store.data?.main?.recent || [] }

/* 停留天数 */
function boardDwell(ts) {
  return boardDwellChina(ts)
}

/* 排序键 */
function boardSortKey(r, p) {
  var mapper = BOARD_DATE_FIELD[p] || {}
  return mapper.get ? mapper.get(r) || 0 : 0
}

/* ---- 获取某列记录 ---- */
function getRecords(col) {
  var recent = applicationRecords()
  var items = []
  recent.forEach(function (r) {
    var p = toArray(r.progress)[0]
    if (!BOARD_COLUMNS.includes(p)) p = '已投递'
    if (p === col) items.push(r)
  })
  // 按时间线降序：刚发生/刚进入的在上，停留久的在下
  items.sort(function (a, b) { return boardSortKey(b, col) - boardSortKey(a, col) })
  return items
}

/* 停留文本 + 是否陈旧 */
function boardDwellFor(col, r) {
  var mapper = BOARD_DATE_FIELD[col] || BOARD_DATE_FIELD['已投递']
  var fieldDate = mapper.get(r)
  return boardDwell(fieldDate)
}

onMounted(function () {
  if (!store.data) store.fetch()
})

/* ---- 拖拽 ---- */
function onDragStart(e, record) {
  dragRid.value = record.record_id || ''
  e.currentTarget.classList.add('dragging')
  try { e.dataTransfer.effectAllowed = 'move'; e.dataTransfer.setData('text/plain', dragRid.value) } catch (err) {}
}

function onDragEnd(e) {
  e.currentTarget.classList.remove('dragging')
}

function onDragOver(e) {
  e.preventDefault()
  e.currentTarget.classList.add('drag-over')
  try { e.dataTransfer.dropEffect = 'move' } catch (err) {}
}

function onDragLeave(e) {
  if (!e.currentTarget.contains(e.relatedTarget)) e.currentTarget.classList.remove('drag-over')
}

async function onDrop(e, targetCol) {
  e.preventDefault()
  var colEl = e.currentTarget
  colEl.classList.remove('drag-over')
  var rid = dragRid.value || (e.dataTransfer && e.dataTransfer.getData('text/plain'))
  dragRid.value = ''
  if (!rid || !targetCol) return

  /* 查找到当前记录 */
  var recent = applicationRecords(), cur = null
  for (var i = 0; i < recent.length; i++) { if (recent[i].record_id === rid) { cur = recent[i]; break } }
  if (!cur) return

  var oldProgress = toArray(cur.progress)[0] || ''
  if (oldProgress === targetCol) return

  /* 回退确认 */
  var oldIdx = _PROGRESS_ORDER_BOARD.indexOf(oldProgress),
      newIdx = _PROGRESS_ORDER_BOARD.indexOf(targetCol)
  var isBackward = oldIdx >= 0 && newIdx >= 0 && newIdx < oldIdx
  if (isBackward) {
    var clearStages = []
    _PROGRESS_ORDER_BOARD.forEach(function (s, i) { if (newIdx < i && i <= oldIdx) clearStages.push(s) })
    const confirmed = await dialog.confirm(
      '确定将进展从「' + oldProgress + '」回退到「' + targetCol + '」吗？\n\n' +
      '此操作将清除以下阶段对应的时间记录：\n' + clearStages.join('、') +
      '\n\n「' + targetCol + '」的时间将更新为今天。',
      { title: '回退投递进展', tone: 'warning', confirmText: '确认回退' },
    )
    if (!confirmed) {
      return
    }
  }

  /* 提交进展更新 */
  var mapper = BOARD_DATE_FIELD[targetCol] || {}, dateField = mapper.set || '', todayMs = Date.now()
  try {
    var payload = { progress: targetCol, old_progress: oldProgress || '' }
    if (dateField) { payload.date_field = dateField; payload.date_value = todayMs }
    var result = await post('/api/dashboard/records/' + encodeURIComponent(rid) + '/progress', payload)
    toast.success(result.message || '进展已更新')
    await store.fetch()
  } catch (err) {
    toast.error('更新失败：' + err.message)
  }
}
</script>

<template>
  <div class="page active board-page">
    <div class="card board-shell">
      <div class="board-hint"><strong>拖动更新</strong><span>将记录拖到目标阶段。回退时会先确认，并同步更新时间。</span><em>{{ applicationRecords().length }} 条记录</em></div>

      <div class="board-columns" id="board-columns">
        <div
          v-for="col in BOARD_COLUMNS"
          :key="col"
          class="board-col"
          :data-progress="col"
          @dragover.prevent="onDragOver"
          @dragleave="onDragLeave"
          @drop="onDrop($event, col)"
        >
          <div class="board-col-hd">
            <ProgressBadge :progress="col" />
            <span class="board-col-count">{{ getRecords(col).length }}</span>
            <span class="board-col-hint">松手放到「{{ col }}」</span>
          </div>
          <template v-if="getRecords(col).length">
            <div class="board-tbl">
              <table class="board-table">
                <colgroup>
                  <col class="c-company" />
                  <col class="c-job" />
                  <col class="c-date" />
                </colgroup>
                <thead>
                  <tr><th>公司</th><th>目标岗位</th><th>停留</th></tr>
                </thead>
                <tbody>
                  <tr
                    v-for="r in getRecords(col)"
                    :key="r.record_id"
                    class="board-row"
                    draggable="true"
                    :data-rid="r.record_id"
                    @dragstart="onDragStart($event, r)"
                    @dragend="onDragEnd"
                  >
                    <td class="b-company"><TooltipCell :text="r.company || '-'" /></td>
                    <td><TooltipCell :text="r.job || '-'" /></td>
                    <td class="b-dwell" :class="{ stale: boardDwellFor(col, r).days >= 14 && boardDwellFor(col, r).days >= 0 }">
                      {{ boardDwellFor(col, r).text }}
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </template>
          <template v-else>
            <div class="board-col-empty">暂无记录，拖动其他分区的行到这里</div>
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.board-page{min-width:0}.board-page-head{display:flex;align-items:flex-end;justify-content:space-between;gap:24px;margin-bottom:18px}.board-page-head h2{margin:0;font-size:clamp(22px,2.5vw,30px);line-height:1.2;letter-spacing:-.035em}.board-page-head p{max-width:620px;margin-top:7px;color:var(--muted);font-size:13px}.board-overview{display:flex;align-items:baseline;gap:7px;padding:9px 12px;border:1px solid var(--line);border-radius:10px;background:var(--panel)}.board-overview strong{color:var(--blue);font-size:18px}.board-overview span{color:var(--sub);font-size:10px}.board-shell{overflow:hidden;border-radius:16px}.board-hint{display:flex;align-items:baseline;gap:10px;padding:13px 16px;border-bottom:1px solid var(--line);background:var(--bg);color:var(--muted);font-size:11px}.board-hint strong{color:var(--ink);font-size:11px}.board-columns{padding:12px;background:var(--bg)}.board-col{overflow:hidden;border:1px solid var(--line);border-radius:12px;background:var(--panel);transition:border-color .18s ease,background .18s ease,transform .18s ease}.board-col.drag-over{border-color:var(--blue);background:var(--blueS);transform:translateY(-2px)}.board-col-hd{padding:11px 12px;border-bottom:1px solid var(--line);background:var(--panel)}.board-col-count{min-width:23px;height:23px;padding:0 7px;border-radius:7px;background:var(--bg);color:var(--muted);font-size:10px;line-height:23px;text-align:center}.board-row{transition:background .15s ease,opacity .15s ease}.board-row:hover{background:var(--blueS)}.board-row.dragging{opacity:.42}.board-col-empty{min-height:92px;padding:30px 16px;color:var(--sub);font-size:10px;line-height:1.6;text-align:center}.b-dwell.stale{color:var(--red);font-weight:800}@media(max-width:820px){.board-page-head{align-items:flex-start;flex-direction:column}.board-overview{width:100%;justify-content:space-between}.board-hint{align-items:flex-start;flex-direction:column;gap:4px}.board-columns{padding:8px}}@media(prefers-reduced-motion:reduce){.board-col,.board-row{transition:none}}
.board-hint em{margin-left:auto;color:var(--sub);font-size:10px;font-style:normal;white-space:nowrap}@media(max-width:820px){.board-hint em{margin-left:0}}
</style>
