<script setup>
import { ref, onMounted } from 'vue'
import { useDashboardStore } from '@/stores/dashboard'
import { useToastStore } from '@/stores/toast'
import ProgressBadge from '@/components/ProgressBadge.vue'
import { post } from '@/utils/api'

const store = useDashboardStore()
const toast = useToastStore()
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
  if (!ts) return { text: '—', days: -1 }
  var entered = new Date(ts)
  if (isNaN(entered)) return { text: '—', days: -1 }
  var now = new Date(), today = new Date(now.getFullYear(), now.getMonth(), now.getDate()),
      enteredDay = new Date(entered.getFullYear(), entered.getMonth(), entered.getDate())
  var days = Math.floor((today - enteredDay) / DAY)
  if (days < 0) days = 0
  return { text: days < 30 ? days + ' 天' : Math.floor(days / 30) + ' 个月', days: days }
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
    if (!confirm('确定将进展从「' + oldProgress + '」回退到「' + targetCol + '」吗？\n\n此操作将清除以下阶段对应的时间记录：\n' + clearStages.join('、') + '\n\n「' + targetCol + '」的时间将更新为今天。')) {
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
  <div class="page active">
    <div class="card">
      <div class="card-hd">
        <span class="dot"></span>
        <div class="card-title">投递看板</div>
        <div class="card-sub" id="board-count">{{ applicationRecords().length }} 条投递记录</div>
        <div class="board-hint">按住卡片拖到其他进展分区即可更新进展。回退操作会弹窗确认。</div>
      </div>

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
                    <td class="b-company">{{ r.company || '—' }}</td>
                    <td>{{ r.job || '—' }}</td>
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
