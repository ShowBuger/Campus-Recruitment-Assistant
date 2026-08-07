<script setup>
import { nextTick, onMounted, ref, watch } from 'vue'
import { gsap } from 'gsap'
import { useAuthStore } from '@/stores/auth'
import { useAppStore } from '@/stores/app'
import SidebarNav from '@/components/SidebarNav.vue'
import Topbar from '@/components/Topbar.vue'
import LoginModal from '@/components/LoginModal.vue'
import ConfigModal from '@/components/ConfigModal.vue'
import ChatModal from '@/components/ChatModal.vue'
import RecordModal from '@/components/RecordModal.vue'
import RecordDetailModal from '@/components/RecordDetailModal.vue'
import RecordManagerModal from '@/components/RecordManagerModal.vue'
import HelpModal from '@/components/HelpModal.vue'
import StatsModal from '@/components/StatsModal.vue'
import OfferCompareModal from '@/components/OfferCompareModal.vue'
import RecommendationModal from '@/components/RecommendationModal.vue'
import ToastContainer from '@/components/ToastContainer.vue'
import AppDialog from '@/components/AppDialog.vue'
import DesktopTitlebar from '@/components/DesktopTitlebar.vue'
import DesktopLogin from '@/components/DesktopLogin.vue'
import DesktopSkinLayer from '@/components/DesktopSkinLayer.vue'
import AuroraVideoBackdrop from '@/components/AuroraVideoBackdrop.vue'
import ShuimoRippleLayer from '@/components/ShuimoRippleLayer.vue'
import { hasDesktopTitlebar } from '@/utils/runtime'


const auth = useAuthStore()
const app = useAppStore()
const hasCustomTitlebar = hasDesktopTitlebar()

watch(() => auth.isLoggedIn, loggedIn => {
  if (!hasCustomTitlebar) return
  window.electronAPI?.windowControl?.(loggedIn ? 'main-size' : 'login-size')
})

watch(() => auth.isAdmin, isAdmin => {
  document.documentElement.dataset.adminUser = isAdmin ? 'true' : 'false'
}, { immediate: true })

// Error modal
const showError = ref(false)
const errorMsg = ref('')
const errorDetail = ref('')
window.__showError = (msg, detail) => { errorMsg.value = msg || '未知错误'; errorDetail.value = detail || ''; showError.value = true }
function copyError() { navigator.clipboard?.writeText(`${errorMsg.value}\n${errorDetail.value}`) }

// Card hover parallax. Track bound nodes because route changes can trigger the
// observer many times during a desktop session.
const boundHoverCards = new WeakSet()
const animatedElements = new WeakSet()
const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)')
function onCardMouseMove(e) {
  const card = e.currentTarget; const rect = card.getBoundingClientRect()
  card.style.setProperty('--mx', `${((e.clientX-rect.left)/rect.width)*100}%`)
  card.style.setProperty('--my', `${((e.clientY-rect.top)/rect.height)*100}%`)
}
function onCardMouseLeave(e) { e.currentTarget.style.removeProperty('--mx'); e.currentTarget.style.removeProperty('--my') }
function bindCardHover() {
  document.querySelectorAll('.kpi-card,.metric').forEach(el => {
    if (boundHoverCards.has(el)) return
    boundHoverCards.add(el)
    el.addEventListener('mousemove', onCardMouseMove); el.addEventListener('mouseleave', onCardMouseLeave)
  })
}

function animateNewUi() {
  if (reduceMotion.matches) return
  const cards = [...document.querySelectorAll('.page.active .card,.page.active .kpi,.page.active .metric')]
    .filter(el => !animatedElements.has(el))
  cards.forEach(el => animatedElements.add(el))
  if (cards.length) {
    gsap.fromTo(cards,
      { autoAlpha: 0, y: 16, scale: 0.992 },
      { autoAlpha: 1, y: 0, scale: 1, duration: 0.42, stagger: 0.045, ease: 'power3.out', clearProps: 'opacity,visibility,transform' }
    )
  }
  document.querySelectorAll('.modal-mask.show').forEach(mask => {
    if (animatedElements.has(mask)) return
    animatedElements.add(mask)
    const panel = mask.querySelector('.modal,.chat-modal-window,.error-modal')
    gsap.fromTo(mask, { autoAlpha: 0 }, { autoAlpha: 1, duration: 0.18, ease: 'power1.out', clearProps: 'opacity,visibility' })
    if (panel) gsap.fromTo(panel,
      { y: 18, scale: 0.965, autoAlpha: 0 },
      { y: 0, scale: 1, autoAlpha: 1, duration: 0.34, ease: 'back.out(1.35)', clearProps: 'opacity,visibility,transform' }
    )
  })
}

onMounted(async () => {
  try { await auth.checkSession() } catch (e) {
    if (e?.message === '登录已过期') auth.clear()
  }
  setTimeout(bindCardHover, 500)
  await nextTick()
  animateNewUi()
  let hoverBindFrame = 0
  new MutationObserver(() => {
    cancelAnimationFrame(hoverBindFrame)
    hoverBindFrame = requestAnimationFrame(() => {
      bindCardHover()
      animateNewUi()
    })
  }).observe(document.body, { childList: true, subtree: true })
})
</script>

<template>
  <AuroraVideoBackdrop />
  <ShuimoRippleLayer />
  <div class="app" v-if="auth.isLoggedIn">
    <DesktopTitlebar v-if="hasCustomTitlebar" />
    <SidebarNav />
    <DesktopSkinLayer />
    <main class="main">
      <div class="cyber-desktop-backdrop" aria-hidden="true"><i></i></div>
      <Topbar @open-config="app.toggleConfig()" @open-chat="app.toggleChat()" @open-help="app.toggleHelp()" />
      <router-view />
    </main>
    <ConfigModal v-if="app.showConfig" @close="app.showConfig = false" />
    <ChatModal v-if="app.showChat" @close="app.showChat = false" />
    <RecordModal v-if="app.showRecord" @close="app.closeRecord()" @saved="app.closeRecord()" />
    <RecordDetailModal v-if="app.detailId" :record-id="app.detailId" @close="app.closeDetail()" @saved="app.closeDetail()" />
    <RecordManagerModal v-if="app.showManager" @close="app.closeManager()" />
    <HelpModal v-if="app.showHelp" @close="app.showHelp = false" />
    <StatsModal v-if="app.showStats" @close="app.closeStats()" />
    <OfferCompareModal v-if="app.showOffer" @close="app.closeOffer()" />
    <RecommendationModal v-if="app.showRecommendation" @close="app.closeRecommendation()" />
    <div v-if="showError" class="error-overlay" @mousedown.self="showError = false">
      <div class="error-modal"><h3>&#9888; {{ errorMsg }}</h3><pre>{{ errorDetail }}</pre><div class="btn-row"><button class="btn" @click="copyError">复制详情</button><button class="btn" style="background:var(--blue);color:#fff" @click="showError = false">关闭</button></div></div>
    </div>
  </div>
  <DesktopLogin v-else-if="hasCustomTitlebar" />
  <LoginModal v-else />
  <AppDialog />
  <ToastContainer />
</template>
