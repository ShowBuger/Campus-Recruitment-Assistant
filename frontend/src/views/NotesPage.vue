<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import DOMPurify from 'dompurify'
import MarkdownIt from 'markdown-it'
import { EditorState } from '@codemirror/state'
import {
  crosshairCursor,
  Decoration,
  drawSelection,
  dropCursor,
  EditorView,
  highlightSpecialChars,
  keymap,
  rectangularSelection,
  ViewPlugin,
  WidgetType,
} from '@codemirror/view'
import { defaultKeymap, history, historyKeymap, indentWithTab } from '@codemirror/commands'
import { markdown } from '@codemirror/lang-markdown'
import {
  PhBookOpenText,
  PhCaretLeft,
  PhCaretRight,
  PhColumns,
  PhFilePlus,
  PhFloppyDisk,
  PhListBullets,
  PhMagnifyingGlass,
  PhNotePencil,
  PhPlus,
  PhTrash,
} from '@phosphor-icons/vue'
import NoteTreeItem from '@/components/NoteTreeItem.vue'
import { api } from '@/utils/api'
import { useDialogStore } from '@/stores/dialog'
import { useToastStore } from '@/stores/toast'

const dialog = useDialogStore()
const toast = useToastStore()
const notes = ref([])
const records = ref([])
const activeId = ref('')
const draftTitle = ref('')
const draftContent = ref('')
const draftRecordId = ref('')
const search = ref('')
const loading = ref(true)
const loadError = ref('')
const saving = ref(false)
const saveState = ref('已保存')
const editorMode = ref('edit')
const editorHost = ref(null)
const previewHost = ref(null)
const libraryCollapsed = ref(false)
const outlineCollapsed = ref(false)
let editor = null
let saveTimer = null
let changingDocument = false
let draftRevision = 0
let savePromise = null

const markdownRenderer = new MarkdownIt({ html: false, linkify: true, breaks: true })
markdownRenderer.renderer.rules.link_open = (tokens, index, options, env, self) => {
  tokens[index].attrSet('target', '_blank')
  tokens[index].attrSet('rel', 'noopener noreferrer')
  return self.renderToken(tokens, index, options)
}

const activeNote = computed(() => notes.value.find(note => note.id === activeId.value) || null)

function noteTree(source = notes.value) {
  const nodes = new Map(source.map(note => [note.id, { ...note, children: [] }]))
  const roots = []
  nodes.forEach(node => {
    const parent = node.parent_id && nodes.get(node.parent_id)
    if (parent) parent.children.push(node)
    else roots.push(node)
  })
  return roots
}

function filterTree(nodes, query) {
  if (!query) return nodes
  return nodes.flatMap(node => {
    const children = filterTree(node.children || [], query)
    return node.title.toLocaleLowerCase().includes(query) || children.length
      ? [{ ...node, children }]
      : []
  })
}

const visibleTree = computed(() => filterTree(noteTree(), search.value.trim().toLocaleLowerCase()))

function markdownDocument(source) {
  const tokens = markdownRenderer.parse(source || '', {})
  const headings = []
  let headingIndex = 0
  tokens.forEach((token, index) => {
    if (token.type !== 'heading_open') return
    const next = tokens[index + 1]
    const text = next?.content?.trim() || '未命名章节'
    const id = `note-heading-${headingIndex++}`
    token.attrSet('id', id)
    headings.push({ id, level: Number(token.tag.slice(1)), text })
  })
  return {
    html: DOMPurify.sanitize(
      markdownRenderer.renderer.render(tokens, markdownRenderer.options, {}),
      { ADD_ATTR: ['target'] },
    ),
    headings,
  }
}

const renderedDocument = computed(() => markdownDocument(draftContent.value))

class MarkdownTableWidget extends WidgetType {
  constructor(html) {
    super()
    this.html = html
  }
  eq(other) { return other.html === this.html }
  toDOM() {
    const wrapper = document.createElement('div')
    wrapper.className = 'cm-live-table'
    wrapper.innerHTML = this.html
    return wrapper
  }
}

function livePreviewDecorations(view) {
  const ranges = []
  const activeLine = view.state.doc.lineAt(view.state.selection.main.head).number
  const codeLines = new Map()
  const codeBlocks = []
  let openBlock = null

  for (let number = 1; number <= view.state.doc.lines; number += 1) {
    const line = view.state.doc.line(number)
    const fence = /^\s*(`{3,}|~{3,})(.*)$/.exec(line.text)
    if (!openBlock && fence) {
      openBlock = { start: number, end: view.state.doc.lines, marker: fence[1][0], size: fence[1].length, closed: false }
    } else if (openBlock && fence && fence[1][0] === openBlock.marker && fence[1].length >= openBlock.size) {
      openBlock.end = number
      openBlock.closed = true
      codeBlocks.push(openBlock)
      openBlock = null
    }
  }
  if (openBlock) codeBlocks.push(openBlock)
  codeBlocks.forEach(block => {
    block.active = activeLine >= block.start && activeLine <= block.end
    for (let number = block.start; number <= block.end; number += 1) {
      codeLines.set(number, {
        block,
        fence: number === block.start || (block.closed && number === block.end),
        first: number === block.start + 1,
        last: number === (block.closed ? block.end - 1 : block.end),
      })
    }
  })

  const tableLines = new Set()
  for (let number = 1; number < view.state.doc.lines; number += 1) {
    if (codeLines.has(number) || tableLines.has(number)) continue
    const header = view.state.doc.line(number)
    const delimiter = view.state.doc.line(number + 1)
    const isTableHeader = header.text.includes('|')
      && /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(delimiter.text)
    if (!isTableHeader) continue
    let end = number + 1
    while (end < view.state.doc.lines) {
      const next = view.state.doc.line(end + 1)
      if (!next.text.trim() || !next.text.includes('|') || codeLines.has(end + 1)) break
      end += 1
    }
    for (let row = number; row <= end; row += 1) tableLines.add(row)
    if (activeLine >= number && activeLine <= end) {
      for (let row = number; row <= end; row += 1) {
        const sourceLine = view.state.doc.line(row)
        ranges.push(Decoration.line({ class: 'cm-live-table-source' }).range(sourceLine.from))
      }
    } else {
      const source = view.state.sliceDoc(header.from, view.state.doc.line(end).to)
      const html = DOMPurify.sanitize(markdownRenderer.render(source))
      ranges.push(Decoration.replace({ widget: new MarkdownTableWidget(html), block: true }).range(header.from, view.state.doc.line(end).to))
    }
    number = end
  }
  const addHidden = (from, to) => {
    if (to > from) ranges.push(Decoration.replace({}).range(from, to))
  }

  for (const viewport of view.visibleRanges) {
    let position = viewport.from
    while (position <= viewport.to) {
      const line = view.state.doc.lineAt(position)
      const codeLine = codeLines.get(line.number)
      if (tableLines.has(line.number)) {
        // The table is either rendered as one block widget or kept as editable source.
      } else if (codeLine) {
        if (codeLine.fence) {
          ranges.push(Decoration.line({ class: `cm-live-code-fence${codeLine.block.active ? '' : ' cm-live-code-fence-hidden'}` }).range(line.from))
          if (!codeLine.block.active) addHidden(line.from, line.to)
        } else {
          const edgeClasses = `${codeLine.first ? ' cm-live-codeblock-first' : ''}${codeLine.last ? ' cm-live-codeblock-last' : ''}`
          ranges.push(Decoration.line({ class: `cm-live-codeblock${edgeClasses}` }).range(line.from))
        }
      } else if (line.number !== activeLine) {
        if (/^\s{0,3}([-*_])(?:\s*\1){2,}\s*$/.test(line.text)) {
          ranges.push(Decoration.line({ class: 'cm-live-hr' }).range(line.from))
          addHidden(line.from, line.to)
        }

        const listMarker = /^(\s*)(?:(\d+)[.)]|([-+*]))\s+/.exec(line.text)
        if (listMarker) {
          const markerStart = line.from + listMarker[1].length
          const markerEnd = line.from + listMarker[0].length
          ranges.push(Decoration.mark({ class: listMarker[2] ? 'cm-live-list-number' : 'cm-live-list-bullet' }).range(markerStart, markerEnd))
          ranges.push(Decoration.line({ class: 'cm-live-list-line' }).range(line.from))
        }

        const heading = /^(#{1,6})\s+/.exec(line.text)
        if (heading) {
          ranges.push(Decoration.line({ class: `cm-live-heading cm-live-heading-${heading[1].length}` }).range(line.from))
          addHidden(line.from, line.from + heading[0].length)
        }

        const inlinePatterns = [
          { regex: /\*\*([^*\n]+)\*\*/g, className: 'cm-live-strong', open: 2, close: 2 },
          { regex: /(?<!\*)\*([^*\n]+)\*(?!\*)/g, className: 'cm-live-em', open: 1, close: 1 },
          { regex: /`([^`\n]+)`/g, className: 'cm-live-code', open: 1, close: 1 },
          { regex: /~~([^~\n]+)~~/g, className: 'cm-live-strike', open: 2, close: 2 },
        ]
        inlinePatterns.forEach(({ regex, className, open, close }) => {
          for (const match of line.text.matchAll(regex)) {
            const start = line.from + match.index
            const end = start + match[0].length
            addHidden(start, start + open)
            ranges.push(Decoration.mark({ class: className }).range(start + open, end - close))
            addHidden(end - close, end)
          }
        })
      }
      if (line.to >= viewport.to || line.to >= view.state.doc.length) break
      position = line.to + 1
    }
  }
  return Decoration.set(ranges, true)
}

const livePreviewPlugin = ViewPlugin.fromClass(class {
  constructor(view) { this.decorations = livePreviewDecorations(view) }
  update(update) {
    if (update.docChanged || update.selectionSet || update.viewportChanged) {
      this.decorations = livePreviewDecorations(update.view)
    }
  }
}, { decorations: value => value.decorations })

function editorExtensions() {
  return [
    highlightSpecialChars(),
    history(),
    drawSelection(),
    dropCursor(),
    EditorState.allowMultipleSelections.of(true),
    rectangularSelection(),
    crosshairCursor(),
    markdown(),
    livePreviewPlugin,
    EditorView.lineWrapping,
    keymap.of([...defaultKeymap, ...historyKeymap, indentWithTab]),
    EditorView.updateListener.of(update => {
      if (!update.docChanged || changingDocument) return
      draftContent.value = update.state.doc.toString()
      scheduleSave()
    }),
    EditorView.theme({
      '&': { height: '100%', color: 'var(--ink)', backgroundColor: 'var(--panel)' },
      '.cm-scroller': { fontFamily: 'var(--mono)', lineHeight: '1.72', fontSize: '13px' },
      '.cm-content': { padding: '24px 28px 48px', caretColor: 'var(--blue)' },
      '.cm-selectionBackground, &.cm-focused .cm-selectionBackground': { backgroundColor: 'color-mix(in srgb, var(--blue) 22%, transparent)' },
      '&.cm-focused': { outline: 'none' },
      '.cm-live-heading': { fontFamily: 'var(--font)', fontWeight: '800', lineHeight: '1.35', color: 'var(--ink)' },
      '.cm-live-heading-1': { fontSize: '1.85em', paddingTop: '.4em', paddingBottom: '.28em' },
      '.cm-live-heading-2': { fontSize: '1.5em', paddingTop: '.35em', paddingBottom: '.2em' },
      '.cm-live-heading-3': { fontSize: '1.25em', paddingTop: '.25em' },
      '.cm-live-heading-4, .cm-live-heading-5, .cm-live-heading-6': { fontSize: '1.08em', paddingTop: '.18em' },
      '.cm-live-strong': { fontWeight: '800', color: 'var(--ink)' },
      '.cm-live-em': { fontStyle: 'italic' },
      '.cm-live-code': { padding: '1px 5px', borderRadius: '5px', color: 'var(--ink)', backgroundColor: 'var(--bg)', fontFamily: 'var(--mono)' },
      '.cm-live-codeblock': { paddingLeft: '14px', paddingRight: '14px', color: 'var(--ink)', backgroundColor: 'var(--bg)', fontFamily: 'var(--mono)', lineHeight: '1.65' },
      '.cm-live-codeblock-first': { paddingTop: '11px', borderTopLeftRadius: '9px', borderTopRightRadius: '9px' },
      '.cm-live-codeblock-last': { paddingBottom: '11px', borderBottomLeftRadius: '9px', borderBottomRightRadius: '9px' },
      '.cm-live-code-fence': { color: 'var(--muted)', fontFamily: 'var(--mono)', fontSize: '11px' },
      '.cm-live-code-fence-hidden': { height: '0', minHeight: '0', padding: '0', overflow: 'hidden', lineHeight: '0', fontSize: '0' },
      '.cm-live-strike': { textDecoration: 'line-through', color: 'var(--muted)' },
      '.cm-live-hr': { minHeight: '19px', marginTop: '8px', marginBottom: '8px', borderTop: '1px solid var(--line)', lineHeight: '0' },
      '.cm-live-list-line': { paddingLeft: '10px' },
      '.cm-live-list-number': { color: 'var(--blue)', fontWeight: '800' },
      '.cm-live-list-bullet': { color: 'var(--blue)', fontWeight: '900' },
      '.cm-live-table-source': { paddingLeft: '10px', paddingRight: '10px', backgroundColor: 'var(--bg)', fontFamily: 'var(--mono)' },
      '.cm-live-table': { display: 'block', margin: '12px 0', overflowX: 'auto', border: '1px solid var(--line)', borderRadius: '9px', backgroundColor: 'var(--panel)', fontFamily: 'var(--font)' },
      '.cm-live-table table': { width: '100%', borderCollapse: 'collapse' },
      '.cm-live-table th, .cm-live-table td': { padding: '8px 10px', borderRight: '1px solid var(--line)', borderBottom: '1px solid var(--line)', textAlign: 'left' },
      '.cm-live-table th': { color: 'var(--ink)', backgroundColor: 'var(--bg)', fontWeight: '800' },
      '.cm-live-table tr:last-child td': { borderBottom: '0' },
      '.cm-live-table th:last-child, .cm-live-table td:last-child': { borderRight: '0' },
    }),
  ]
}

async function ensureEditor() {
  await nextTick()
  if (!editorHost.value || editor) return
  editor = new EditorView({
    state: EditorState.create({ doc: draftContent.value, extensions: editorExtensions() }),
    parent: editorHost.value,
  })
}

function setEditorDocument(content) {
  if (!editor) return
  changingDocument = true
  editor.dispatch({ changes: { from: 0, to: editor.state.doc.length, insert: content || '' } })
  changingDocument = false
}

async function loadNotes() {
  loading.value = true
  loadError.value = ''
  try {
    const [noteData, recordData] = await Promise.all([
      api('GET', '/api/notes'),
      api('GET', '/api/notes/records'),
    ])
    notes.value = noteData.notes || []
    records.value = recordData.records || []
    if (notes.value.length) {
      const firstRoot = notes.value.find(note => !note.parent_id) || notes.value[0]
      await selectNote(firstRoot.id, false)
    }
    await ensureEditor()
  } catch (error) {
    loadError.value = error.message || '笔记加载失败'
  } finally {
    loading.value = false
  }
}

async function createNote(parentId = null) {
  await saveActiveNow()
  try {
    const data = await api('POST', '/api/notes', {
      title: parentId ? '新建子笔记' : '未命名笔记',
      parent_id: parentId,
      record_id: parentId ? activeNote.value?.record_id || null : null,
    })
    notes.value.push(data.note)
    await selectNote(data.note.id, false)
    toast.success(parentId ? '子笔记已创建' : '笔记已创建')
    await nextTick()
    document.querySelector('.notes-title-input')?.select()
  } catch (error) {
    toast.error(error.message || '创建笔记失败')
  }
}

async function selectNote(noteId, saveCurrent = true) {
  if (noteId === activeId.value) return
  if (saveCurrent) await saveActiveNow()
  const note = notes.value.find(item => item.id === noteId)
  if (!note) return
  activeId.value = note.id
  draftTitle.value = note.title || '未命名笔记'
  draftContent.value = note.content || ''
  draftRecordId.value = note.record_id || ''
  saveState.value = '已保存'
  await ensureEditor()
  setEditorDocument(draftContent.value)
}

function scheduleSave() {
  if (!activeId.value) return
  draftRevision += 1
  saveState.value = '待保存'
  clearTimeout(saveTimer)
  saveTimer = setTimeout(saveActiveNow, 700)
}

async function saveActiveNow() {
  clearTimeout(saveTimer)
  saveTimer = null
  const noteId = activeId.value
  if (!noteId || saveState.value === '已保存') return
  if (saving.value && savePromise) {
    await savePromise.catch(() => null)
    if (activeId.value === noteId && saveState.value !== '已保存') await saveActiveNow()
    return
  }
  const savingRevision = draftRevision
  saving.value = true
  saveState.value = '保存中'
  try {
    savePromise = api('PUT', `/api/notes/${encodeURIComponent(noteId)}`, {
      title: draftTitle.value,
      content: draftContent.value,
      record_id: draftRecordId.value || null,
    })
    const data = await savePromise
    const index = notes.value.findIndex(note => note.id === noteId)
    if (index >= 0) notes.value[index] = data.note
    if (activeId.value === noteId) {
      if (draftRevision === savingRevision) saveState.value = '已保存'
      else {
        saveState.value = '待保存'
        saveTimer = setTimeout(saveActiveNow, 250)
      }
    }
  } catch (error) {
    saveState.value = '保存失败'
    toast.error(error.message || '笔记保存失败')
  } finally {
    savePromise = null
    saving.value = false
  }
}

async function deleteActiveNote() {
  const note = activeNote.value
  if (!note) return
  const hasChildren = notes.value.some(item => item.parent_id === note.id)
  const confirmed = await dialog.confirm(
    hasChildren ? `确定删除“${note.title}”及其所有子笔记吗？` : `确定删除“${note.title}”吗？`,
    { title: '删除笔记', tone: 'danger', confirmText: '删除笔记' },
  )
  if (!confirmed) return
  try {
    await api('DELETE', `/api/notes/${encodeURIComponent(note.id)}`)
    const deletedIds = new Set([note.id])
    let changed = true
    while (changed) {
      changed = false
      notes.value.forEach(item => {
        if (item.parent_id && deletedIds.has(item.parent_id) && !deletedIds.has(item.id)) {
          deletedIds.add(item.id)
          changed = true
        }
      })
    }
    notes.value = notes.value.filter(item => !deletedIds.has(item.id))
    activeId.value = ''
    draftTitle.value = ''
    draftContent.value = ''
    draftRecordId.value = ''
    setEditorDocument('')
    if (notes.value.length) await selectNote(notes.value[0].id, false)
    toast.success('笔记已删除')
  } catch (error) {
    toast.error(error.message || '删除笔记失败')
  }
}

function scrollToHeading(id) {
  previewHost.value?.querySelector(`#${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

function formatUpdated(value) {
  if (!value) return ''
  const date = new Date(String(value).replace(' ', 'T') + 'Z')
  if (Number.isNaN(date.getTime())) return value
  return new Intl.DateTimeFormat('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }).format(date)
}

function setPanelCollapsed(panel, value) {
  if (panel === 'library') libraryCollapsed.value = value
  else outlineCollapsed.value = value
  try { localStorage.setItem(`radar_notes_${panel}_collapsed`, value ? '1' : '0') } catch (_) {}
}

onMounted(() => {
  try {
    libraryCollapsed.value = localStorage.getItem('radar_notes_library_collapsed') === '1'
    outlineCollapsed.value = localStorage.getItem('radar_notes_outline_collapsed') === '1'
  } catch (_) {}
  loadNotes()
})
onBeforeRouteLeave(async () => { await saveActiveNow() })
onBeforeUnmount(() => {
  clearTimeout(saveTimer)
  editor?.destroy()
  editor = null
})
</script>

<template>
  <div class="page active notes-page">
    <section class="notes-workspace" :class="{ 'library-collapsed': libraryCollapsed, 'outline-collapsed': outlineCollapsed }" aria-label="Markdown 笔记工作区">
      <aside class="notes-library" :class="{ 'is-collapsed': libraryCollapsed }">
        <header class="notes-panel-head">
          <div><h2>笔记库</h2><span>{{ notes.length }} 篇</span></div>
          <div class="notes-panel-actions">
            <button class="notes-icon-btn primary" type="button" title="新建笔记" aria-label="新建笔记" @click="createNote()"><PhFilePlus :size="17" weight="bold" /></button>
            <button class="notes-panel-collapse" type="button" :title="libraryCollapsed ? '展开笔记库' : '折叠笔记库'" :aria-label="libraryCollapsed ? '展开笔记库' : '折叠笔记库'" :aria-expanded="!libraryCollapsed" @click="setPanelCollapsed('library', !libraryCollapsed)">
              <PhCaretRight v-if="libraryCollapsed" :size="15" weight="bold" />
              <PhCaretLeft v-else :size="15" weight="bold" />
            </button>
          </div>
        </header>
        <label class="notes-search">
          <PhMagnifyingGlass :size="15" />
          <input v-model.trim="search" type="search" placeholder="搜索笔记" aria-label="搜索笔记">
        </label>
        <div class="notes-tree" aria-live="polite">
          <div v-if="loading" class="notes-tree-loading"><i v-for="i in 5" :key="i"></i></div>
          <div v-else-if="loadError" class="notes-side-state"><strong>无法读取笔记</strong><span>{{ loadError }}</span><button class="btn" type="button" @click="loadNotes">重新加载</button></div>
          <div v-else-if="!notes.length" class="notes-side-state"><PhNotePencil :size="26" weight="duotone" /><strong>开始第一篇笔记</strong><span>记录面试复盘、岗位信息或准备清单。</span><button class="btn btn-primary" type="button" @click="createNote()">新建笔记</button></div>
          <div v-else-if="!visibleTree.length" class="notes-side-state"><strong>没有匹配结果</strong><span>尝试更换搜索词。</span></div>
          <NoteTreeItem v-for="note in visibleTree" v-else :key="note.id" :note="note" :active-id="activeId" @select="selectNote" @add-child="createNote" />
        </div>
      </aside>

      <main class="notes-document">
        <template v-if="activeNote">
          <header class="notes-document-head">
            <div class="notes-title-wrap">
              <input v-model="draftTitle" class="notes-title-input" maxlength="200" aria-label="笔记标题" @input="scheduleSave">
              <span>{{ formatUpdated(activeNote.updated_at) }}</span>
            </div>
            <div class="notes-document-actions">
              <span class="notes-save-state" :class="{ error: saveState === '保存失败' }"><PhFloppyDisk :size="14" />{{ saveState }}</span>
              <button class="notes-icon-btn" type="button" title="新建子笔记" aria-label="新建子笔记" @click="createNote(activeId)"><PhPlus :size="16" weight="bold" /></button>
              <button class="notes-icon-btn danger" type="button" title="删除笔记" aria-label="删除笔记" @click="deleteActiveNote"><PhTrash :size="16" /></button>
            </div>
          </header>

          <div class="notes-toolbar">
            <label class="notes-record-link"><span>关联投递记录</span><select v-model="draftRecordId" @change="scheduleSave"><option value="">不关联记录</option><option v-for="record in records" :key="record.record_id" :value="record.record_id">{{ record.company }} / {{ record.job }}</option></select></label>
            <div class="notes-view-switch" aria-label="编辑视图">
              <button type="button" :class="{ active: editorMode === 'edit' }" title="实时编辑" aria-label="实时编辑" @click="editorMode = 'edit'"><PhNotePencil :size="15" /></button>
              <button type="button" :class="{ active: editorMode === 'split' }" title="双栏" @click="editorMode = 'split'"><PhColumns :size="15" /></button>
              <button type="button" :class="{ active: editorMode === 'preview' }" title="仅预览" @click="editorMode = 'preview'"><PhBookOpenText :size="15" /></button>
            </div>
          </div>

          <div class="notes-content" :class="`mode-${editorMode}`">
            <section v-show="editorMode !== 'preview'" class="notes-editor-pane" aria-label="Markdown 编辑器"><div ref="editorHost" class="notes-editor-host"></div></section>
            <section v-show="editorMode !== 'edit'" ref="previewHost" class="notes-preview-pane" aria-label="Markdown 实时预览">
              <article v-if="draftContent.trim()" class="markdown-body" v-html="renderedDocument.html"></article>
              <div v-else class="notes-writing-empty"><PhNotePencil :size="32" weight="duotone" /><strong>开始写作</strong><span>在编辑区输入 Markdown，预览会实时显示在这里。</span></div>
            </section>
          </div>
        </template>

        <div v-else-if="!loading" class="notes-document-empty"><PhBookOpenText :size="42" weight="duotone" /><h2>选择或创建一篇笔记</h2><p>笔记可以关联投递记录，也可以继续创建任意层级的子笔记。</p><button class="btn btn-primary" type="button" @click="createNote()">新建笔记</button></div>
      </main>

      <aside class="notes-outline" :class="{ 'is-collapsed': outlineCollapsed }">
        <header class="notes-panel-head">
          <div><h2>目录</h2><span>{{ renderedDocument.headings.length }} 节</span></div>
          <div class="notes-panel-actions">
            <PhListBullets class="notes-outline-symbol" :size="18" weight="duotone" />
            <button class="notes-panel-collapse" type="button" :title="outlineCollapsed ? '展开目录' : '折叠目录'" :aria-label="outlineCollapsed ? '展开目录' : '折叠目录'" :aria-expanded="!outlineCollapsed" @click="setPanelCollapsed('outline', !outlineCollapsed)">
              <PhCaretLeft v-if="outlineCollapsed" :size="15" weight="bold" />
              <PhCaretRight v-else :size="15" weight="bold" />
            </button>
          </div>
        </header>
        <nav v-if="activeNote && renderedDocument.headings.length" class="notes-outline-list" aria-label="笔记目录">
          <button v-for="heading in renderedDocument.headings" :key="heading.id" type="button" :style="{ '--heading-depth': heading.level - 1 }" @click="scrollToHeading(heading.id)">{{ heading.text }}</button>
        </nav>
        <div v-else class="notes-outline-empty"><span>使用 #、##、### 创建标题后，目录会自动生成。</span></div>
        <div v-if="activeNote?.record" class="notes-linked-record"><span>关联记录</span><strong>{{ activeNote.record.company }}</strong><small>{{ activeNote.record.job }}</small></div>
      </aside>
    </section>
  </div>
</template>

<style scoped>
.notes-page{height:calc(100dvh - 102px);min-height:620px}.notes-workspace{display:grid;grid-template-columns:236px minmax(0,1fr) 196px;height:100%;min-height:0;overflow:hidden;border:1px solid var(--line);border-radius:16px;background:var(--panel);box-shadow:var(--shadow);transition:grid-template-columns .2s var(--ease)}.notes-workspace.library-collapsed{grid-template-columns:48px minmax(0,1fr) 196px}.notes-workspace.outline-collapsed{grid-template-columns:236px minmax(0,1fr) 48px}.notes-workspace.library-collapsed.outline-collapsed{grid-template-columns:48px minmax(0,1fr) 48px}
.notes-library,.notes-outline{display:flex;min-width:0;min-height:0;flex-direction:column;background:color-mix(in srgb,var(--bg) 68%,var(--panel))}.notes-library{border-right:1px solid var(--line)}.notes-outline{border-left:1px solid var(--line)}.notes-panel-head{display:flex;min-height:57px;align-items:center;justify-content:space-between;gap:8px;padding:0 14px;border-bottom:1px solid var(--line)}.notes-panel-head>div{display:flex;min-width:0;align-items:baseline;gap:7px}.notes-panel-head h2{margin:0;color:var(--ink);font-size:12px}.notes-panel-head span{color:var(--muted);font:700 9px var(--font)}.notes-panel-actions{align-items:center!important;gap:5px!important}.notes-panel-collapse{display:grid;width:28px;height:28px;flex:0 0 28px;place-items:center;padding:0;border:1px solid transparent;border-radius:7px;color:var(--muted);background:transparent;cursor:pointer;transition:color .14s ease,border-color .14s ease,background .14s ease,transform .14s ease}.notes-panel-collapse:hover{border-color:var(--line);color:var(--blue);background:var(--blueS)}.notes-panel-collapse:active{transform:scale(.96)}.notes-library.is-collapsed>.notes-panel-head,.notes-outline.is-collapsed>.notes-panel-head{justify-content:center;padding:0}.notes-library.is-collapsed>.notes-panel-head>div:first-child,.notes-outline.is-collapsed>.notes-panel-head>div:first-child,.notes-library.is-collapsed .notes-icon-btn.primary,.notes-outline.is-collapsed .notes-outline-symbol{display:none}.notes-library.is-collapsed>.notes-panel-head .notes-panel-actions,.notes-outline.is-collapsed>.notes-panel-head .notes-panel-actions{display:flex}.notes-library.is-collapsed>:not(.notes-panel-head),.notes-outline.is-collapsed>:not(.notes-panel-head){display:none}
.notes-icon-btn{display:grid;width:32px;height:32px;flex:0 0 32px;place-items:center;padding:0;border:1px solid var(--line);border-radius:8px;color:var(--sub);background:var(--panel);cursor:pointer;transition:transform .12s ease,color .12s ease,border-color .12s ease,background .12s ease}.notes-icon-btn:hover{border-color:var(--blue);color:var(--blue);background:var(--blueS)}.notes-icon-btn:active{transform:translateY(1px)}.notes-icon-btn.primary{border-color:transparent;color:#f7f9ff;background:var(--blue)}.notes-icon-btn.danger:hover{border-color:var(--red);color:var(--red);background:var(--redS)}
.notes-search{display:grid;grid-template-columns:18px minmax(0,1fr);align-items:center;gap:4px;margin:10px 10px 7px;padding:0 9px;border:1px solid var(--line);border-radius:9px;color:var(--muted);background:var(--panel)}.notes-search:focus-within{border-color:var(--blue);box-shadow:0 0 0 2px var(--blueS)}.notes-search input,.notes-search input:focus,.notes-search input:focus-visible{width:100%;height:34px;padding:0;border:0!important;outline:0!important;color:var(--ink);background:transparent!important;box-shadow:none!important;font:600 11px var(--font)}.notes-search input::placeholder{color:var(--muted)}.notes-tree{min-height:0;flex:1;padding:2px 8px 12px;overflow:auto}.notes-side-state{display:flex;min-height:220px;align-items:center;justify-content:center;flex-direction:column;gap:8px;padding:18px;color:var(--muted);text-align:center}.notes-side-state strong{color:var(--ink);font-size:12px}.notes-side-state span{font-size:10px;line-height:1.55}.notes-side-state .btn{margin-top:4px}.notes-tree-loading{display:grid;gap:9px;padding:9px 5px}.notes-tree-loading i{height:28px;border-radius:7px;background:var(--line);animation:notes-pulse 1.3s ease-in-out infinite}.notes-tree-loading i:nth-child(2),.notes-tree-loading i:nth-child(4){width:78%}
.notes-document{display:flex;min-width:0;min-height:0;flex-direction:column;background:var(--panel)}.notes-document-head{display:flex;min-height:57px;align-items:center;justify-content:space-between;gap:14px;padding:8px 14px 8px 20px;border-bottom:1px solid var(--line)}.notes-title-wrap{display:grid;min-width:0;flex:1;gap:2px}.notes-title-input,.notes-title-input:focus,.notes-title-input:focus-visible{min-width:0;width:100%;padding:0;border:0!important;outline:0!important;color:var(--ink);background:transparent!important;box-shadow:none!important;font:800 18px/1.25 var(--font);letter-spacing:-.02em}.notes-title-wrap>span{color:var(--muted);font:600 9px var(--font)}.notes-document-actions{display:flex;align-items:center;gap:6px}.notes-save-state{display:flex;align-items:center;gap:4px;margin-right:2px;color:var(--muted);font:700 9px var(--font);white-space:nowrap}.notes-save-state.error{color:var(--red)}
.notes-toolbar{display:flex;min-height:49px;align-items:center;justify-content:space-between;gap:12px;padding:7px 14px 7px 20px;border-bottom:1px solid var(--line);background:var(--bg)}.notes-record-link{display:flex;min-width:0;align-items:center;gap:8px}.notes-record-link>span{color:var(--muted);font:700 9px var(--font);white-space:nowrap}.notes-record-link select{max-width:330px;height:32px;padding:0 28px 0 9px;border:1px solid var(--line);border-radius:8px;outline:0;color:var(--ink);background:var(--panel);font:600 10px var(--font)}.notes-record-link select:focus{border-color:var(--blue);box-shadow:0 0 0 2px var(--blueS)}.notes-view-switch{display:flex;flex:0 0 auto;padding:2px;border:1px solid var(--line);border-radius:8px;background:var(--panel)}.notes-view-switch button{display:grid;width:28px;height:26px;place-items:center;padding:0;border:0;border-radius:6px;color:var(--muted);background:transparent;cursor:pointer}.notes-view-switch button:hover{color:var(--ink)}.notes-view-switch button.active{color:var(--blue);background:var(--blueS)}
.notes-content{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);min-height:0;flex:1}.notes-content.mode-edit,.notes-content.mode-preview{grid-template-columns:1fr}.notes-editor-pane,.notes-preview-pane{min-width:0;min-height:0;overflow:hidden}.notes-editor-pane{border-right:1px solid var(--line)}.mode-edit .notes-editor-pane{border-right:0}.notes-editor-host{height:100%}.notes-preview-pane{padding:27px 34px 60px;overflow:auto;scroll-behavior:smooth}.notes-writing-empty,.notes-document-empty{display:flex;height:100%;align-items:center;justify-content:center;flex-direction:column;gap:9px;padding:28px;color:var(--muted);text-align:center}.notes-writing-empty strong,.notes-document-empty h2{margin:0;color:var(--ink)}.notes-writing-empty span,.notes-document-empty p{max-width:380px;margin:0;font-size:11px;line-height:1.6}.notes-document-empty h2{font-size:18px}.notes-document-empty .btn{margin-top:5px}
.markdown-body{max-width:760px;margin:0 auto;color:var(--ink);font:400 13px/1.8 var(--font);overflow-wrap:anywhere}.markdown-body :deep(h1),.markdown-body :deep(h2),.markdown-body :deep(h3),.markdown-body :deep(h4),.markdown-body :deep(h5),.markdown-body :deep(h6){scroll-margin-top:18px;color:var(--ink);line-height:1.3;letter-spacing:-.02em}.markdown-body :deep(h1){margin:0 0 24px;font-size:28px}.markdown-body :deep(h2){margin:32px 0 12px;padding-bottom:7px;border-bottom:1px solid var(--line);font-size:20px}.markdown-body :deep(h3){margin:25px 0 9px;font-size:16px}.markdown-body :deep(h4){margin:20px 0 7px;font-size:14px}.markdown-body :deep(p){margin:0 0 14px}.markdown-body :deep(a){color:var(--blue);text-decoration:underline;text-underline-offset:3px}.markdown-body :deep(blockquote){margin:16px 0;padding:2px 0 2px 14px;border-left:3px solid var(--blue);color:var(--sub)}.markdown-body :deep(code){padding:2px 5px;border-radius:5px;color:var(--ink);background:var(--bg);font:12px var(--mono)}.markdown-body :deep(pre){margin:16px 0;padding:14px;overflow:auto;border:1px solid var(--line);border-radius:10px;background:var(--bg)}.markdown-body :deep(pre code){padding:0;background:transparent}.markdown-body :deep(img){max-width:100%;border-radius:10px}.markdown-body :deep(table){width:100%;margin:16px 0;border-collapse:collapse}.markdown-body :deep(th),.markdown-body :deep(td){padding:8px 10px;border:1px solid var(--line);text-align:left}.markdown-body :deep(hr){margin:26px 0;border:0;border-top:1px solid var(--line)}
.notes-outline-list{display:flex;min-height:0;flex:1;flex-direction:column;gap:2px;padding:10px 8px;overflow:auto}.notes-outline-list button{width:100%;min-height:29px;padding:5px 7px 5px calc(8px + var(--heading-depth) * 10px);overflow:hidden;border:0;border-radius:7px;color:var(--muted);text-align:left;text-overflow:ellipsis;white-space:nowrap;background:transparent;font:600 10px/1.4 var(--font);cursor:pointer}.notes-outline-list button:hover,.notes-outline-list button:focus-visible{outline:0;color:var(--blue);background:var(--blueS)}.notes-outline-empty{padding:17px 14px;color:var(--muted);font-size:10px;line-height:1.65}.notes-linked-record{display:grid;gap:3px;margin:10px;padding:11px;border:1px solid var(--line);border-radius:10px;background:var(--panel)}.notes-linked-record span{color:var(--muted);font:700 9px var(--font)}.notes-linked-record strong{overflow:hidden;color:var(--ink);font-size:11px;text-overflow:ellipsis;white-space:nowrap}.notes-linked-record small{overflow:hidden;color:var(--sub);font-size:9px;text-overflow:ellipsis;white-space:nowrap}
@keyframes notes-pulse{50%{opacity:.45}}@media(max-width:1180px){.notes-workspace{grid-template-columns:210px minmax(0,1fr) 174px}.notes-preview-pane{padding-inline:24px}}@media(max-width:900px){.notes-page{height:auto;min-height:calc(100dvh - 100px)}.notes-workspace{grid-template-columns:210px minmax(0,1fr);min-height:720px}.notes-outline{display:none}.notes-content{grid-template-columns:1fr}.notes-content.mode-split .notes-editor-pane{display:none}.notes-content.mode-split .notes-preview-pane{display:block}.notes-view-switch button:nth-child(2){display:none}}@media(max-width:620px){.notes-workspace{display:flex;min-height:760px;flex-direction:column}.notes-library{max-height:230px;border-right:0;border-bottom:1px solid var(--line)}.notes-document{min-height:520px;flex:1}.notes-document-head{padding-left:14px}.notes-toolbar{align-items:stretch;flex-direction:column;padding:8px 14px}.notes-record-link{display:grid;grid-template-columns:auto minmax(0,1fr)}.notes-record-link select{max-width:none;width:100%}.notes-view-switch{align-self:flex-end}.notes-preview-pane{padding:22px 20px 50px}.notes-save-state{display:none}}
@media(prefers-reduced-motion:reduce){.notes-icon-btn,.notes-tree-loading i{transition:none;animation:none}.notes-preview-pane{scroll-behavior:auto}}
</style>
