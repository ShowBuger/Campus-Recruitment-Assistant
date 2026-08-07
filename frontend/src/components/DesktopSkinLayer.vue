<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const inkTrail = ref(null)
const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)')
let inkContext = null
let inkFrame = 0
let inkRatio = 1
let inkPoints = []
let inkSplashes = []
let inkBlooms = []
let inkBloomBlock = -1
let lastInkBloomAt = -Infinity
let lastPointer = null
let inkStrokeId = 0
let inkTravel = 0
let inkSplashBlock = -1
let inkResizeObserver = null

const INK_LIFETIME = 520
const INK_DISTANCE_AGE = 2.7
const INK_BREAK_MS = 220
const INK_POINT_GAP = 5
const INK_MAX_POINTS = 72
const INK_MAX_TRAVEL = 150
const INK_BLOOM_GAP = 34

function sizeInkTrail() {
  const canvas = inkTrail.value
  if (!canvas) return
  const rect = canvas.getBoundingClientRect()
  inkRatio = Math.min(window.devicePixelRatio || 1, 1)
  canvas.width = Math.max(1, Math.round(rect.width * inkRatio))
  canvas.height = Math.max(1, Math.round(rect.height * inkRatio))
  canvas.dataset.buffer = `${canvas.width}x${canvas.height}`
  inkContext = canvas.getContext('2d', { alpha: true })
  inkContext?.setTransform(inkRatio, 0, 0, inkRatio, 0, 0)
  inkPoints = []
  inkSplashes = []
  inkBlooms = []
  lastPointer = null
}

function inkNoise(value) {
  const wave = Math.sin(value * 12.9898 + 78.233) * 43758.5453
  return wave - Math.floor(wave)
}

function pointGeometry(points, now) {
  const smoothed = points.map((point, index) => {
    const radius = Math.min(2, index, points.length - 1 - index)
    if (!radius) return point
    let x = 0
    let y = 0
    let total = 0
    for (let offset = -radius; offset <= radius; offset += 1) {
      const weight = radius + 1 - Math.abs(offset)
      x += points[index + offset].x * weight
      y += points[index + offset].y * weight
      total += weight
    }
    return { ...point, x: x / total, y: y / total }
  })
  return points.map((point, index) => {
    const current = smoothed[index]
    const before = smoothed[Math.max(0, index - 1)]
    const after = smoothed[Math.min(points.length - 1, index + 1)]
    const length = Math.hypot(after.x - before.x, after.y - before.y) || 1
    const nx = -(after.y - before.y) / length
    const ny = (after.x - before.x) / length
    const distanceFromHead = points[points.length - 1].travel - point.travel
    const idleAge = now - points[points.length - 1].time
    const effectiveAge = idleAge + distanceFromHead * INK_DISTANCE_AGE
    const life = Math.max(0, Math.min(1, 1 - effectiveAge / INK_LIFETIME))
    const distanceFade = Math.max(0, Math.min(1, 1 - distanceFromHead / INK_MAX_TRAVEL))
    const tail = Math.pow(life, .48) * Math.pow(distanceFade, .58)
    const start = index === 0 ? .025 : index === 1 ? .28 : index === 2 ? .66 : index === 3 ? .9 : 1
    const headIndex = points.length - 1 - index
    const head = headIndex === 0 ? .42 : headIndex === 1 ? .7 : headIndex === 2 ? .9 : 1
    const roughness = .88 + inkNoise(point.seed * .37) * .2
    const brushWidth = point.width * tail * roughness
    return {
      ...point,
      x: current.x,
      y: current.y,
      nx,
      ny,
      opacity: Math.pow(life, 1.35) * Math.pow(distanceFade, .72),
      brushWidth,
      width: brushWidth * start * head,
    }
  })
}

function ribbonPath(points, scale = 1, offset = 0) {
  if (points.length < 2) return false
  const edge = side => points.map(point => ({
    x: point.x + point.nx * point.width * (side * .5 * scale + offset),
    y: point.y + point.ny * point.width * (side * .5 * scale + offset),
  }))
  const left = edge(1)
  const right = edge(-1).reverse()
  const trace = vertices => {
    for (let index = 1; index < vertices.length - 1; index += 1) {
      const current = vertices[index]
      const next = vertices[index + 1]
      inkContext.quadraticCurveTo(current.x, current.y, (current.x + next.x) / 2, (current.y + next.y) / 2)
    }
    const last = vertices[vertices.length - 1]
    inkContext.lineTo(last.x, last.y)
  }
  inkContext.beginPath()
  inkContext.moveTo(left[0].x, left[0].y)
  trace(left)
  const head = points[points.length - 1]
  const beforeHead = points[Math.max(0, points.length - 2)]
  const tangentLength = Math.hypot(head.x - beforeHead.x, head.y - beforeHead.y) || 1
  const tx = (head.x - beforeHead.x) / tangentLength
  const ty = (head.y - beforeHead.y) / tangentLength
  inkContext.quadraticCurveTo(
    head.x + tx * head.width * .42,
    head.y + ty * head.width * .42,
    right[0].x,
    right[0].y,
  )
  trace(right)
  inkContext.closePath()
  return true
}

function drawContinuousRibbon(points, scale, offset, color, alpha) {
  if (!ribbonPath(points, scale, offset)) return
  const headOpacity = points[points.length - 1].opacity
  inkContext.globalAlpha = alpha * Math.pow(headOpacity, .24)
  inkContext.fillStyle = `rgb(${color})`
  inkContext.fill()
}

function drawFiberSegments(points, offsets, color, erase = false) {
  inkContext.globalCompositeOperation = erase ? 'destination-out' : 'source-over'
  inkContext.lineCap = 'butt'
  for (const [fiber, baseOffset] of offsets.entries()) {
    for (let index = 0; index < points.length - 1; index += 1) {
      const from = points[index]
      const to = points[index + 1]
      const block = Math.floor((from.travel + fiber * 17) / (erase ? 23 : 15))
      const texture = inkNoise(block + from.stroke * 31 + fiber * 7.7)
      const dryness = (from.dryness + to.dryness) * .5
      if (texture < (erase ? .56 - dryness * .12 : .18)) continue
      const wobble = (texture - .5) * (erase ? .14 : .09)
      const offset = baseOffset + wobble
      const fromAmount = from.width * offset
      const toAmount = to.width * offset
      inkContext.beginPath()
      inkContext.moveTo(from.x + from.nx * fromAmount, from.y + from.ny * fromAmount)
      inkContext.lineTo(to.x + to.nx * toAmount, to.y + to.ny * toAmount)
      inkContext.globalAlpha = (from.opacity + to.opacity) * .5 * (erase ? .22 + dryness * .28 : .18 + texture * .17)
      inkContext.lineWidth = erase ? .3 + dryness * (.65 + texture * .85) : .25 + texture * .72
      inkContext.strokeStyle = erase ? '#000' : `rgb(${color})`
      inkContext.stroke()
    }
  }
}

function drawTailSilks(points, color) {
  if (points.length < 6) return
  const anchor = points[Math.min(3, points.length - 2)]
  const ahead = points[Math.min(6, points.length - 1)]
  const length = Math.hypot(ahead.x - anchor.x, ahead.y - anchor.y) || 1
  const tx = (ahead.x - anchor.x) / length
  const ty = (ahead.y - anchor.y) / length
  const nx = -ty
  const ny = tx
  inkContext.save()
  inkContext.lineCap = 'round'
  for (let fiber = 0; fiber < 8; fiber += 1) {
    const seed = inkNoise(anchor.seed + fiber * 13.1)
    const spread = (fiber - 3.5) * 1.35 + (seed - .5) * 3
    const silkLength = 18 + seed * 44
    const bend = (inkNoise(anchor.seed + fiber * 29.4) - .5) * 22
    inkContext.beginPath()
    inkContext.moveTo(anchor.x + nx * spread, anchor.y + ny * spread)
    inkContext.bezierCurveTo(
      anchor.x - tx * silkLength * .3 + nx * (spread + bend * .35),
      anchor.y - ty * silkLength * .3 + ny * (spread + bend * .35),
      anchor.x - tx * silkLength * .72 + nx * bend,
      anchor.y - ty * silkLength * .72 + ny * bend,
      anchor.x - tx * silkLength + nx * bend * .6,
      anchor.y - ty * silkLength + ny * bend * .6,
    )
    inkContext.globalAlpha = anchor.opacity * (.07 + seed * .16)
    inkContext.lineWidth = .25 + seed * .8
    inkContext.strokeStyle = `rgb(${color})`
    inkContext.stroke()
  }
  inkContext.restore()
}
function addInkBloom(point, width) {
  const block = Math.floor(inkTravel / INK_BLOOM_GAP)
  if (block === inkBloomBlock || point.time - lastInkBloomAt < 62) return
  inkBloomBlock = block
  lastInkBloomAt = point.time
  const seed = inkNoise(block * 11.7 + inkStrokeId * 37.3)
  const radius = Math.max(6, Math.min(17, width * (.48 + seed * .18)))
  const rect = inkTrail.value?.getBoundingClientRect()
  inkBlooms.push({ x: point.x, y: point.y, radius, seed, time: point.time + 55, life: 620 + seed * 260 })
  if (inkBlooms.length > 12) inkBlooms.splice(0, inkBlooms.length - 12)
  window.dispatchEvent(new CustomEvent('shuimo-ink-bloom', { detail: {
    x: point.x + (rect?.left || 0),
    y: point.y + (rect?.top || 0),
    radius,
    strength: .009 + Math.max(0, Math.min(1, (radius - 6) / 11)) * .009, seed,
  } }))
}

function drawInkBlooms(now, color) {
  inkContext.save()
  inkContext.filter = 'blur(3.6px)'
  inkContext.globalCompositeOperation = 'source-over'
  for (const bloom of inkBlooms) {
    const age = now - bloom.time
    if (age < 0) continue
    const progress = Math.min(1, age / bloom.life)
    const eased = 1 - Math.pow(1 - progress, 2.2)
    const radius = bloom.radius * (1 + eased * 2.25)
    inkContext.beginPath()
    inkContext.ellipse(
      bloom.x + (bloom.seed - .5) * eased * 5,
      bloom.y + (.5 - bloom.seed) * eased * 3,
      radius * (1 + bloom.seed * .2), radius * (.72 + bloom.seed * .18),
      bloom.seed * Math.PI, 0, Math.PI * 2,
    )
    inkContext.globalAlpha = Math.pow(1 - progress, 1.55) * .105
    inkContext.fillStyle = `rgb(${color})`
    inkContext.fill()
  }
  inkContext.restore()
}


function drawSplashes(now, color) {
  inkContext.save()
  for (const splash of inkSplashes) {
    const age = now - splash.time
    const life = Math.max(0, 1 - age / splash.life)
    if (!life) continue
    const x = splash.x + splash.vx * age / 1000
    const y = splash.y + splash.vy * age / 1000
    inkContext.beginPath()
    inkContext.ellipse(x, y, splash.radius * (1 + age / splash.life * .2), splash.radius * (.7 + splash.seed * .35), splash.angle, 0, Math.PI * 2)
    inkContext.globalAlpha = Math.pow(life, 1.8) * (.13 + splash.seed * .28)
    inkContext.fillStyle = `rgb(${color})`
    inkContext.fill()
  }
  inkContext.restore()
}

function drawInkStroke(points, now, color) {
  const geometry = pointGeometry(points, now)

  // Diffuse wet halo: soft rice-paper capillary bleed, never a neon glow.
  inkContext.save()
  inkContext.filter = 'blur(2.8px)'
  drawContinuousRibbon(geometry, 1.42, 0, color, .085)
  inkContext.restore()

  inkContext.save()
  // Wet body and uneven loaded core create black/grey ink-density variation.
  drawContinuousRibbon(geometry, 1, 0, color, .64)
  drawContinuousRibbon(geometry, .38, -.16, color, .28)
  drawContinuousRibbon(geometry, .13, .13, color, .2)
  // Sparse dry gaps and separated hairs follow the stroke rather than repeating a stamp.
  drawFiberSegments(geometry, [-.12, .17], color, true)
  drawFiberSegments(geometry, [-.54, -.47, .46, .53], color, false)
  inkContext.restore()
  drawTailSilks(geometry, color)
}

function drawInkTrail(now) {
  const canvas = inkTrail.value
  if (!canvas || !inkContext) { inkFrame = 0; return }
  const rect = canvas.getBoundingClientRect()
  inkContext.clearRect(0, 0, rect.width, rect.height)
  const latestByStroke = new Map()
  for (const point of inkPoints) latestByStroke.set(point.stroke, point)
  inkPoints = inkPoints.filter(point => {
    const latest = latestByStroke.get(point.stroke)
    const distanceFromHead = latest.travel - point.travel
    const effectiveAge = now - latest.time + distanceFromHead * INK_DISTANCE_AGE
    return effectiveAge < INK_LIFETIME && distanceFromHead <= INK_MAX_TRAVEL
  })
  inkSplashes = inkSplashes.filter(splash => now - splash.time < splash.life)
  inkBlooms = inkBlooms.filter(bloom => now - bloom.time < bloom.life)
  canvas.dataset.points = String(inkPoints.length)
  canvas.dataset.newestAge = inkPoints.length ? String(Math.round(now - inkPoints[inkPoints.length - 1].time)) : '0'
  canvas.dataset.oldestAge = inkPoints.length ? String(Math.round(now - inkPoints[0].time)) : '0'
  canvas.dataset.travelSpan = inkPoints.length ? String(Math.round(inkPoints[inkPoints.length - 1].travel - inkPoints[0].travel)) : '0'
  const dark = document.documentElement.dataset.theme === 'dark'
  const color = dark ? '214,214,210' : '20,20,20'
  drawInkBlooms(now, color)
  let start = 0
  while (start < inkPoints.length) {
    let end = start + 1
    while (end < inkPoints.length && inkPoints[end].stroke === inkPoints[start].stroke) end += 1
    if (end - start > 1) drawInkStroke(inkPoints.slice(start, end), now, color)
    start = end
  }
  drawSplashes(now, color)
  canvas.dataset.drops = inkPoints.length || inkSplashes.length || inkBlooms.length ? 'active' : '0'
  if (inkPoints.length || inkSplashes.length || inkBlooms.length) inkFrame = requestAnimationFrame(drawInkTrail)
  else { inkFrame = 0; lastPointer = null }
}

function maybeSplash(point, nx, ny, speed) {
  const block = Math.floor(inkTravel / 58)
  if (block === inkSplashBlock || speed < .72) return
  inkSplashBlock = block
  const chance = inkNoise(block + inkStrokeId * 43.7)
  if (chance < .68) return
  const count = chance > .9 ? 2 : 1
  for (let index = 0; index < count; index += 1) {
    const seed = inkNoise(block * 7.1 + index * 17.9 + inkStrokeId)
    const side = seed > .5 ? 1 : -1
    const spread = 10 + seed * 24
    inkSplashes.push({
      x: point.x + nx * spread * side,
      y: point.y + ny * spread * side,
      vx: nx * side * (4 + seed * 12),
      vy: ny * side * (4 + seed * 12) + 3,
      radius: .55 + seed * 2.25,
      angle: point.angle + seed,
      seed,
      time: point.time,
      life: 280 + seed * 180,
    })
    if (seed > .62) {
      inkSplashes.push({
        x: point.x + nx * spread * side * 1.45,
        y: point.y + ny * spread * side * 1.45,
        vx: nx * side * (9 + seed * 15),
        vy: ny * side * (7 + seed * 13) - 5,
        radius: .28 + seed * .72,
        angle: point.angle - seed,
        seed: 1 - seed,
        time: point.time,
        life: 340 + seed * 160,
      })
    }
  }
  if (inkSplashes.length > 16) inkSplashes.splice(0, inkSplashes.length - 16)
}

function trackInk(event) {
  if (reduceMotion.matches || document.documentElement.dataset.style !== 'shuimo' || document.documentElement.dataset.shuimoTrail === 'off') {
    lastPointer = null
    return
  }
  const canvas = inkTrail.value
  if (!canvas) return
  const rect = canvas.getBoundingClientRect()
  const point = { x: event.clientX - rect.left, y: event.clientY - rect.top, time: performance.now() }
  if (!lastPointer || point.time - lastPointer.time > INK_BREAK_MS) {
    inkStrokeId += 1
    inkTravel = 0
    inkSplashBlock = -1
    inkBloomBlock = -1
    lastInkBloomAt = -Infinity
    inkPoints.push({ ...point, width: 1, dryness: .2, angle: 0, seed: inkStrokeId * 101, stroke: inkStrokeId, travel: 0 })
  } else {
    const dx = point.x - lastPointer.x
    const dy = point.y - lastPointer.y
    const distance = Math.hypot(dx, dy)
    if (distance > 0) {
      const elapsed = Math.max(4, point.time - lastPointer.time)
      const speed = distance / elapsed
      const angle = Math.atan2(dy, dx)
      const nx = -Math.sin(angle)
      const ny = Math.cos(angle)
      const pressure = Math.pow(Math.max(0, Math.min(1, 1 - speed / 5.5)), .58)
      const targetWidth = 8 + pressure * 20
      const targetDryness = Math.max(.12, Math.min(.94, (speed - .12) / 1.85))
      const steps = Math.max(1, Math.ceil(distance / INK_POINT_GAP))
      const previousWidth = inkPoints[inkPoints.length - 1]?.width || targetWidth
      const previousDryness = inkPoints[inkPoints.length - 1]?.dryness ?? targetDryness
      for (let step = 1; step <= steps; step += 1) {
        const amount = step / steps
        inkTravel += distance / steps
        inkPoints.push({
          x: lastPointer.x + (point.x - lastPointer.x) * amount,
          y: lastPointer.y + (point.y - lastPointer.y) * amount,
          time: lastPointer.time + elapsed * amount,
          width: previousWidth + (targetWidth - previousWidth) * Math.min(1, amount * .62),
          dryness: previousDryness + (targetDryness - previousDryness) * amount,
          angle,
          seed: inkTravel + inkStrokeId * 101,
          stroke: inkStrokeId,
          travel: inkTravel,
        })
        addInkBloom(
          { x: lastPointer.x + dx * amount, y: lastPointer.y + dy * amount, time: lastPointer.time + elapsed * amount },
          previousWidth + (targetWidth - previousWidth) * amount,
        )
      }
      maybeSplash({ ...point, angle }, nx, ny, speed)
    }
  }
  lastPointer = point
  if (inkPoints.length > INK_MAX_POINTS) inkPoints.splice(0, inkPoints.length - INK_MAX_POINTS)
  if (!inkFrame) inkFrame = requestAnimationFrame(drawInkTrail)
}

function resetInkPointer() { lastPointer = null }

onMounted(() => {
  requestAnimationFrame(sizeInkTrail)
  inkResizeObserver = new ResizeObserver(sizeInkTrail)
  if (inkTrail.value) inkResizeObserver.observe(inkTrail.value)
  window.addEventListener('resize', sizeInkTrail)
  window.addEventListener('mousemove', trackInk, { passive: true })
  window.addEventListener('mouseleave', resetInkPointer)
})

onUnmounted(() => {
  window.removeEventListener('resize', sizeInkTrail)
  window.removeEventListener('mousemove', trackInk)
  window.removeEventListener('mouseleave', resetInkPointer)
  inkResizeObserver?.disconnect()
  cancelAnimationFrame(inkFrame)
})

const dockItems = computed(() => [
  { to: '/', label: '投递', icon: 'home' },
  { to: '/board', label: '看板', icon: 'board' },
  { to: '/records', label: '总表', icon: 'table' },
  { to: '/resumes', label: '简历', icon: 'resume' },
  { to: '/analysis', label: '分析', icon: 'spark' },
  ...(auth.isAdmin ? [{ to: '/admin', label: '管理', icon: 'admin' }] : []),
])
</script>

<template>
  <div class="desktop-skin-layer">
    <div class="liquid-backdrop" aria-hidden="true"><i></i><i></i><i></i></div>
    <canvas ref="inkTrail" class="ink-cursor-trail" aria-hidden="true"></canvas>
    <div class="ink-stage" aria-hidden="true">
      <svg class="ink-wash" viewBox="0 0 1000 500" preserveAspectRatio="none">
        <defs>
          <linearGradient id="ink-fade" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stop-color="currentColor" stop-opacity=".8" />
            <stop offset=".62" stop-color="currentColor" stop-opacity=".2" />
            <stop offset="1" stop-color="currentColor" stop-opacity="0" />
          </linearGradient>
        </defs>
        <path class="ink-stroke ink-stroke-a" d="M-40 125C135 44 250 185 430 104S720 24 1040 106" />
        <path class="ink-stroke ink-stroke-b" d="M-40 380C150 290 275 440 465 346s330-40 575-8" />
        <path class="ink-ridge" d="M0 430c84-56 133-77 201-39 51-80 120-107 190-29 61-102 129-121 215-38 74-70 142-80 222 1 61-41 113-44 172-13v188H0Z" />
      </svg>
      <div class="ink-mist"><i></i><i></i><i></i></div>
    </div>
    <div class="liquid-dock-glass">
      <nav class="liquid-dock" aria-label="桌面快捷导航">
        <router-link v-for="item in dockItems" :key="item.to" :to="item.to" :title="item.label">
          <svg v-if="item.icon === 'home'" viewBox="0 0 24 24"><path d="M3.5 10.7 12 3.8l8.5 6.9v9H15v-6H9v6H3.5v-9Z"/></svg>
          <svg v-else-if="item.icon === 'board'" viewBox="0 0 24 24"><path d="M4 4h6v16H4V4Zm10 0h6v9h-6V4Zm0 13h6v3h-6v-3Z"/></svg>
          <svg v-else-if="item.icon === 'table'" viewBox="0 0 24 24"><path d="M4 5h16v14H4V5Zm0 5h16M9 5v14"/></svg>
          <svg v-else-if="item.icon === 'resume'" viewBox="0 0 24 24"><path d="M6 3h9l3 3v15H6V3Zm9 0v4h3M9 11h6M9 15h6"/></svg>
          <svg v-else-if="item.icon === 'spark'" viewBox="0 0 24 24"><path d="m12 3 1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5L12 3Zm6 13 .7 2.3L21 19l-2.3.7L18 22l-.7-2.3L15 19l2.3-.7L18 16Z"/></svg>
          <svg v-else viewBox="0 0 24 24"><path d="M4 20v-2a5 5 0 0 1 5-5h6a5 5 0 0 1 5 5v2M12 10a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm6-5v4M16 7h4"/></svg>
          <span>{{ item.label }}</span>
        </router-link>
      </nav>
    </div>
  </div>
</template>
