import { createRouter, createWebHistory } from 'vue-router'
import { api } from '../api'

const Login = () => import('../pages/Login.vue')
const AdminHome = () => import('../pages/AdminHome.vue')
const DoctorHome = () => import('../pages/DoctorHome.vue')
const ReviewerHome = () => import('../pages/ReviewerHome.vue')

const getDefaultRouteByRole = (role) => {
  if (role === 'admin') return '/admin/reports'
  if (role === 'doctor') return '/doctor'
  if (role === 'reviewer') return '/reviewer'
  return '/login'
}

const routes = [
  { path: '/', redirect: '/login' },
  { path: '/login', component: Login, meta: { public: true } },
  { path: '/admin', redirect: '/admin/reports' },
  { path: '/admin/reports', component: AdminHome, meta: { adminTab: 'reports', roles: ['admin'] } },
  { path: '/admin/import', component: AdminHome, meta: { adminTab: 'import', roles: ['admin'] } },
  { path: '/admin/users', component: AdminHome, meta: { adminTab: 'users', roles: ['admin'] } },
  { path: '/doctor', component: DoctorHome, meta: { roles: ['doctor', 'admin'] } },
  { path: '/reviewer', component: ReviewerHome, meta: { roles: ['reviewer'] } }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach(async (to) => {
  if (to.meta?.public) {
    const token = api.getToken()
    if (!token) return true

    try {
      const user = api.getCurrentUser() || await api.getMe()
      const targetPath = getDefaultRouteByRole(user?.role)
      if (to.path !== targetPath) {
        return targetPath
      }
    } catch (_e) {
      return true
    }
    return true
  }

  const token = api.getToken()
  if (!token) {
    return '/login'
  }

  let user = api.getCurrentUser()
  if (!user) {
    try {
      user = await api.getMe()
    } catch (_e) {
      return '/login'
    }
  }

  const allowedRoles = Array.isArray(to.meta?.roles) ? to.meta.roles : []
  if (!allowedRoles.length || allowedRoles.includes(user?.role)) {
    return true
  }

  return getDefaultRouteByRole(user?.role)
})

export default router
