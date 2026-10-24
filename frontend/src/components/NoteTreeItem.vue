<script setup>
import { ref } from 'vue'
import { PhCaretRight, PhFileText, PhPlus } from '@phosphor-icons/vue'

defineOptions({ name: 'NoteTreeItem' })
const props = defineProps({
  note: { type: Object, required: true },
  activeId: { type: String, default: '' },
  depth: { type: Number, default: 0 },
})
const emit = defineEmits(['select', 'add-child'])
const expanded = ref(true)
</script>

<template>
  <div class="note-tree-node">
    <div class="note-tree-row" :class="{ active: activeId === note.id }" :style="{ '--note-depth': depth }">
      <button
        class="note-tree-toggle"
        type="button"
        :class="{ open: expanded }"
        :disabled="!note.children?.length"
        :aria-label="expanded ? '收起子笔记' : '展开子笔记'"
        @click="expanded = !expanded"
      ><PhCaretRight :size="13" weight="bold" /></button>
      <button class="note-tree-main" type="button" @click="emit('select', note.id)">
        <PhFileText :size="15" weight="duotone" />
        <span>{{ note.title || '未命名笔记' }}</span>
      </button>
      <button class="note-tree-add" type="button" title="新建子笔记" :aria-label="`在 ${note.title} 下新建子笔记`" @click="emit('add-child', note.id)">
        <PhPlus :size="13" weight="bold" />
      </button>
    </div>
    <div v-if="expanded && note.children?.length" class="note-tree-children">
      <NoteTreeItem
        v-for="child in note.children"
        :key="child.id"
        :note="child"
        :active-id="activeId"
        :depth="depth + 1"
        @select="emit('select', $event)"
        @add-child="emit('add-child', $event)"
      />
    </div>
  </div>
</template>

<style scoped>
.note-tree-row{display:grid;grid-template-columns:20px minmax(0,1fr) 26px;align-items:center;min-height:34px;padding-left:calc(var(--note-depth) * 14px);border-radius:8px;color:var(--sub);transition:background .14s ease,color .14s ease}.note-tree-row:hover{color:var(--ink);background:var(--bg)}.note-tree-row.active{color:var(--blue);background:var(--blueS)}
.note-tree-toggle,.note-tree-add,.note-tree-main{border:0;color:inherit;background:transparent;cursor:pointer}.note-tree-toggle{display:grid;width:20px;height:28px;place-items:center;padding:0}.note-tree-toggle svg{transition:transform .14s ease}.note-tree-toggle.open svg{transform:rotate(90deg)}.note-tree-toggle:disabled{visibility:hidden}.note-tree-main{display:flex;min-width:0;height:32px;align-items:center;gap:7px;padding:0;text-align:left;font:700 11px/1.2 var(--font)}.note-tree-main svg{flex:0 0 auto}.note-tree-main span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.note-tree-add{display:grid;width:24px;height:24px;place-items:center;padding:0;border-radius:6px;opacity:0}.note-tree-row:hover .note-tree-add,.note-tree-row:focus-within .note-tree-add{opacity:1}.note-tree-add:hover{color:var(--blue);background:var(--panel)}
@media(prefers-reduced-motion:reduce){.note-tree-row,.note-tree-toggle svg{transition:none}}
</style>
