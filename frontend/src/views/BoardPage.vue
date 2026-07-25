<script setup>
import { ref, onMounted } from 'vue'
import { useDashboardStore } from '@/stores/dashboard'
import { useToastStore } from '@/stores/toast'
import ProgressBadge from '@/components/ProgressBadge.vue'
import { post } from '@/utils/api'

const store = useDashboardStore()
const toast = useToastStore()

const PROGRESS_ORDER = ['未投递', '已投递', '机考', '面试', 'OC', '已挂', '放弃']

const DATE_FIELD_MAP = {
  '已投递': '投递时间',
  '机考': '机考时间',
  '面试': '一面',
  'OC': '结果',
  '已挂': '结果',
  '放弃': '结果',
}

const columns = ['已投递', '机考', '面试', 'OC', '已挂', '放弃']
const dragRid = ref('')

onMounted(() => {
  if (!store.data) store.fetch()
})

function isBackward(from, to) {
  return PROGRESS_ORDER.indexOf(to) < PROGRESS_ORDER.indexOf(from)
}

function getClearStages(from, to) {
  const stages = []
  const fromIdx = PROGRESS_ORDER.indexOf(from)
  const toIdx = PROGRESS_ORDER.indexOf(to)
  PROGRESS_ORDER.forEach((s, i) => {
    if (toIdx < i && i <= fromIdx) stages.push(s)
  })
  return stages
}

function getDateField(col, r) {
  const map = {
    '已投递': r.apply_date,
    '机考': r.exam_date,
    '面试': Math.max(r.interview1 || 0, r.interview2 || 0, r.interview3 || 0),
    'OC': r.result,
    '已挂': r.result,
    '放弃': r.result,
  }
  return map[col] || 0
}

function getRecords(col) {
  return store.recentRecords
    .filter(r => (r.progress || [])[0] === col)
    .sort((a, b) => (getDateField(col, b) || 0) - (getDateField(col, a) || 0))
}

function getDwell(col, r) {
  const ts = getDateField(col, r)
  if (!ts) return '—'
  const days = Math.floor((Date.now() - ts) / 86400000)
  if (days < 0) return '0 天'
  return days < 30 ? days + ' 天' : Math.floor(days / 30) + ' 个月'
}

function onDragStart(e, record) {
  dragRid.value = record.record_id
  e.target.classList.add('dragging')
  e.dataTransfer.effectAllowed = 'move'
  e.dataTransfer.setData('text/plain', record.record_id)
}

function onDragEnd(e) {
  e.target.classList.remove('dragging')
  dragRid.value = ''
}

function onDragOver(e) {
  e.currentTarget.classList.add('drag-over')
  e.dataTransfer.dropEffect = 'move'
}

function onDragLeave(e) {
  if (!e.currentTarget.contains(e.relatedTarget)) {
    e.currentTarget.classList.remove('drag-over')
  }
}

async function onDrop(e, targetCol) {
  e.currentTarget.classList.remove('drag-over')
  const rid = dragRid.value || e.dataTransfer.getData('text/plain')
  if (!rid) return

  const record = store.recentRecords.find(r => r.record_id === rid)
  if (!record) return
  const oldProgress = (record.progress || [])[0]
  if (oldProgress === targetCol) return

  if (isBackward(oldProgress, targetCol)) {
    const stages = getClearStages(oldProgress, targetCol)
    if (!confirm(
      `确定将进展从「${oldProgress}」回退到「${targetCol}」吗？\n\n` +
      `此操作将清除以下阶段对应的时间记录：\n${stages.join('、')}\n\n` +
      `「${targetCol}」的时间将更新为今天。`
    )) {
      return
    }
  }

  const dateField = DATE_FIELD_MAP[targetCol] || ''
  try {
    await post(`/api/dashboard/records/${rid}/progress`, {
      progress: targetCol,
      date_field: dateField,
      date_value: Date.now(),
      old_progress: oldProgress || '',
    })
    toast.success(`已更新为「${targetCol}」`)
    await store.fetch()
  } catch (e) {
    toast.error('更新失败：' + e.message)
  }
}
</script>

<template>
  <div class="page">
    <div class="card">
      <div class="card-hd">
        <span class="dot"></span>
        <div class="card-title">投递看板</div>
        <div class="card-sub">{{ store.recentRecords.length }} 条投递记录</div>
        <div class="board-hint">按住卡片拖到其他进展分区即可更新进展。回退操作会弹窗确认。</div>
      </div>

      <div class="board-columns" id="board-columns">
        <div
          v-for="col in columns"
          :key="col"
          class="board-col"
          :data-progress="col"
          @dragover.prevent="onDragOver($event)"
          @dragleave="onDragLeave($event)"
          @drop="onDrop($event, col)"
        >
          <div class="board-col-hd">
            <ProgressBadge :progress="col" />
            <span class="board-col-count">{{ getRecords(col).length }}</span>
          </div>
          <div class="board-col-empty" v-if="!getRecords(col).length">
            拖动卡片到此列
          </div>
          <div class="board-tbl" v-else>
            <table class="board-table">
              <thead>
                <tr>
                  <th>公司</th>
                  <th>目标岗位</th>
                  <th>停留</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="r in getRecords(col)"
                  :key="r.record_id"
                  class="board-row"
                  draggable="true"
                  :data-rid="r.record_id"
                  @dragstart="onDragStart($event, r)"
                  @dragend="onDragEnd($event)"
                >
                  <td class="b-company">{{ r.company || '—' }}</td>
                  <td>{{ r.job || '—' }}</td>
                  <td class="b-dwell">{{ getDwell(col, r) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
