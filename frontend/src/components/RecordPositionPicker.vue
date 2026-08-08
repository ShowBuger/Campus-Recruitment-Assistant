<script setup>
defineProps({ group: { type: Object, required: true } })
const emit = defineEmits(['close', 'select'])
</script>

<template>
  <div class="modal-mask show" @mousedown.self="emit('close')">
    <div class="modal position-picker-modal" role="dialog" aria-modal="true" aria-labelledby="position-picker-title">
      <div class="modal-hd">
        <div><h2 id="position-picker-title">选择目标岗位</h2><p>{{ group.company }}共有 {{ group._positions?.length || 0 }} 条岗位记录，选择后整行将显示对应信息。</p></div>
        <button class="icon-btn" type="button" title="关闭" @click="emit('close')">&times;</button>
      </div>
      <div class="modal-body position-picker-list">
        <button v-for="position in group._positions" :key="position.record_id" type="button" class="position-picker-item" :class="{ active: position.record_id === group.record_id }" @click="emit('select', position)">
          <span><b>{{ position.job || '未命名岗位' }}</b><small>{{ position.city || '城市未填写' }} / {{ position.batch || '批次未填写' }}</small></span>
          <em>{{ (position.progress || [])[0] || '未投递' }}</em>
        </button>
      </div>
      <div class="modal-ft"><button class="btn" type="button" @click="emit('close')">取消</button></div>
    </div>
  </div>
</template>

<style scoped>
.position-picker-modal{width:min(520px,94vw)}.position-picker-list{display:grid;gap:8px;max-height:55dvh;overflow:auto}.position-picker-item{display:flex;align-items:center;justify-content:space-between;gap:16px;width:100%;padding:12px 13px;border:1px solid var(--line);border-radius:10px;text-align:left;color:var(--ink);background:var(--bg);cursor:pointer}.position-picker-item:hover,.position-picker-item:focus-visible{border-color:var(--blue);outline:none;background:var(--blueS)}.position-picker-item.active{border-color:var(--blue);box-shadow:inset 3px 0 var(--blue)}.position-picker-item span{display:grid;min-width:0;gap:4px}.position-picker-item b{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:13px}.position-picker-item small{color:var(--muted);font-size:10px}.position-picker-item em{flex-shrink:0;color:var(--blue);font:800 10px var(--font);font-style:normal}
</style>
