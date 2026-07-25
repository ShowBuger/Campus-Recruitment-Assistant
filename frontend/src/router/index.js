import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'dashboard', component: () => import('@/views/DashboardPage.vue') },
  { path: '/board', name: 'board', component: () => import('@/views/BoardPage.vue') },
  { path: '/records', name: 'records', component: () => import('@/views/RecordsPage.vue') },
  { path: '/resumes', name: 'resumes', component: () => import('@/views/ResumePage.vue') },
  { path: '/analysis', name: 'analysis', component: () => import('@/views/AnalysisPage.vue') },
  { path: '/admin', name: 'admin', component: () => import('@/views/AdminPage.vue') },
]

export default createRouter({
  history: createWebHistory(),
  routes
})
