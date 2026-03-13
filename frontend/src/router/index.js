import { createRouter, createWebHistory } from 'vue-router'
import Login from '../pages/Login.vue'
import AdminHome from '../pages/AdminHome.vue'
import DoctorHome from '../pages/DoctorHome.vue'
import ReviewerHome from '../pages/ReviewerHome.vue'

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
