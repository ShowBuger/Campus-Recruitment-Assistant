export const PRIMARY_NAV_ITEMS = Object.freeze([
  { to: '/', label: '投递信息', dockLabel: '投递', icon: 'home' },
  { to: '/board', label: '投递看板', dockLabel: '看板', icon: 'board' },
  { to: '/records', label: '总表信息', dockLabel: '总表', icon: 'table' },
  { to: '/resumes', label: '简历管理', dockLabel: '简历', icon: 'resume' },
  { to: '/analysis', label: '简历分析', dockLabel: '分析', icon: 'analysis' },
  { to: '/notes', label: '校招笔记', dockLabel: '笔记', icon: 'notes' },
  { to: '/salary', label: '薪资查询', dockLabel: '薪资', icon: 'salary' },
  { to: '/offer-comparison', label: '岗位对比', dockLabel: '对比', icon: 'comparison' },
])

export const ADMIN_NAV_ITEM = Object.freeze({
  to: '/admin',
  label: '管理页面',
  dockLabel: '管理',
  icon: 'admin',
})

export function navigationItems(isAdmin) {
  return isAdmin ? [...PRIMARY_NAV_ITEMS, ADMIN_NAV_ITEM] : [...PRIMARY_NAV_ITEMS]
}
