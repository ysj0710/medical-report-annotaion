import { createRouter, createWebHistory } from 'vue-router'

const Login = () => import('../pages/Login.vue')
const AdminHome = () => import('../pages/AdminHome.vue')
const DoctorHome = () => import('../pages/DoctorHome.vue')
const ReviewerHome = () => import('../pages/ReviewerHome.vue')

const routes = [
  { path: '/', redirect: '/login' },
  { path: '/login', component: Login },
  { path: '/admin', redirect: '/admin/reports' },
  { path: '/admin/reports', component: AdminHome, meta: { adminTab: 'reports' } },
  { path: '/admin/import', component: AdminHome, meta: { adminTab: 'import' } },
  { path: '/admin/users', component: AdminHome, meta: { adminTab: 'users' } },
  { path: '/doctor', component: DoctorHome },
  { path: '/reviewer', component: ReviewerHome }
]

export default createRouter({
  history: createWebHistory(),
  routes
})
