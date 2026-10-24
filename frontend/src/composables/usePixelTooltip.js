let tipEl = null
let currentEl = null
let hideTimer = null

function ensureTip() {
  if (tipEl) return
  tipEl = document.createElement('div')
  tipEl.id = 'px-tooltip'
  document.body.appendChild(tipEl)
}

function restore() {
  if (!currentEl) return
  const orig = currentEl.getAttribute('data-px-title-backup')
  if (orig) { currentEl.setAttribute('title', orig); currentEl.removeAttribute('data-px-title-backup') }
  currentEl = null
}

function doHide() {
  restore()
  if (tipEl) tipEl.classList.remove('on')
}

function scheduleHide() {
  clearTimeout(hideTimer)
  hideTimer = setTimeout(doHide, 50)
}

function cancelHide() {
  clearTimeout(hideTimer)
}

function onMouseOver(e) {
  cancelHide()
  const el = e.target.closest?.('[title]')
  if (!el) { scheduleHide(); return }
  if (el === currentEl) return
  restore()
  const text = (el.getAttribute('title') || '').trim()
  if (!text) return
  currentEl = el
  el.setAttribute('data-px-title-backup', text)
  el.removeAttribute('title')
  ensureTip()
  tipEl.textContent = text
  move(e)
  tipEl.classList.add('on')
}

function onMouseOut(e) {
  const toEl = e.relatedTarget
  // moving to a child of currentEl → stay
  if (currentEl && toEl && currentEl.contains(toEl)) return
  // moving to another [title] → let mouseover handle it
  if (toEl && toEl.closest?.('[title]')) return
  scheduleHide()
}

function move(e) {
  if (!tipEl || !tipEl.classList.contains('on')) return
  const gap = 10
  let x = e.clientX + gap, y = e.clientY + gap
  const r = tipEl.getBoundingClientRect()
  if (r.width && x + r.width > window.innerWidth - 4) x = e.clientX - r.width - gap
  if (r.height && y + r.height > window.innerHeight - 4) y = e.clientY - r.height - gap
  tipEl.style.left = Math.max(4, x) + 'px'
  tipEl.style.top = Math.max(4, y) + 'px'
}

export function installPixelTooltip() {
  document.addEventListener('mouseover', onMouseOver)
  document.addEventListener('mouseout', onMouseOut)
  document.addEventListener('mousemove', move)
}

export function uninstallPixelTooltip() {
  document.removeEventListener('mouseover', onMouseOver)
  document.removeEventListener('mouseout', onMouseOut)
  document.removeEventListener('mousemove', move)
  cancelHide()
  doHide()
  if (tipEl) { tipEl.remove(); tipEl = null }
}
