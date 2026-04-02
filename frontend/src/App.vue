<template>
  <div class="app">
    <header v-if="isLoggedIn" class="app-header">
      <div class="header-top">
        <h1>医疗影像报告标注系统</h1>
        <div class="user-info">
          <span>{{ currentUser?.username }} ({{ currentUser?.role }})</span>
          <button @click="handleLogout" class="logout-btn">退出</button>
        </div>
      </div>
      <nav>
        <router-link v-if="currentUser?.role === 'admin'" to="/admin/reports">报告池</router-link>
        <router-link v-if="currentUser?.role === 'admin'" to="/admin/import">导入</router-link>
        <router-link v-if="currentUser?.role === 'admin'" to="/admin/users">用户管理</router-link>
        <router-link v-if="currentUser?.role === 'doctor'" to="/doctor">我的报告</router-link>
        <router-link v-if="currentUser?.role === 'reviewer'" to="/reviewer">复核任务</router-link>
      </nav>
    </header>
    <main>
      <router-view />
    </main>
  </div>
</template>

<script>
import { api } from './api'

export default {
  name: 'App',
  data() {
    return {
      isLoggedIn: false,
      currentUser: null
    }
  },
  watch: {
    '$route'(to) {
      this.checkAuth()
    }
  },
  created() {
    this.checkAuth()
  },
  methods: {
    async checkAuth() {
      const token = api.getToken()
      if (!token) {
        this.isLoggedIn = false
        if (this.$route.path !== '/login') {
          this.$router.push('/login')
        }
        return
      }
      try {
        this.currentUser = api.getCurrentUser() || await api.getMe()
        this.isLoggedIn = true
        // 如果在登录页且已登录，根据角色跳转
        if (this.$route.path === '/login') {
          if (this.currentUser.role === 'admin') {
            this.$router.push('/admin/reports')
          } else if (this.currentUser.role === 'doctor') {
            this.$router.push('/doctor')
          } else if (this.currentUser.role === 'reviewer') {
            this.$router.push('/reviewer')
          }
        }
      } catch (e) {
        api.clearToken()
        this.isLoggedIn = false
        this.$router.push('/login')
      }
    },
    handleLogout() {
      api.logout()
      this.isLoggedIn = false
      this.currentUser = null
      this.$router.push('/login')
    }
  }
}
</script>

<style scoped>
.app-header {
  background: #fff;
  padding: 16px 24px;
  border-bottom: 1px solid #eee;
}
.header-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
h1 {
  font-size: 20px;
  margin: 0;
  color: #333;
}
.user-info {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 14px;
  color: #666;
}
.logout-btn {
  padding: 6px 12px;
  background: #f56c6c;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 13px;
}
.logout-btn:hover {
  background: #f78989;
}
nav a {
  margin-right: 16px;
  color: #409eff;
  text-decoration: none;
  font-size: 14px;
}
nav a:hover {
  text-decoration: underline;
}
nav a.router-link-active {
  color: #333;
  font-weight: 500;
}
main {
  padding: 20px;
}
</style>
