const API_BASE = '/api'

function normalizeToken(raw) {
  if (!raw) return null
  const value = String(raw).trim()
  if (!value || value === 'null' || value === 'undefined') return null
  return value
}

let token = normalizeToken(localStorage.getItem('token'))
let currentUser = null

export const api = {
  setToken(t) {
    token = normalizeToken(t)
    if (token) {
      localStorage.setItem('token', token)
    } else {
      localStorage.removeItem('token')
    }
  },
  clearToken() {
    token = null
    localStorage.removeItem('token')
    currentUser = null
  },
  getToken() {
    return token
  },
  getCurrentUser() {
    return currentUser
  },

  async request(method, path, data = null) {
    const headers = { 'Content-Type': 'application/json' }
    const authToken = normalizeToken(token)
    if (path === '/auth/me' && !authToken) {
      this.clearToken()
      throw new Error('Unauthorized')
    }
    if (authToken) {
      headers['Authorization'] = `Bearer ${authToken}`
    }
    const options = { method, headers }
    if (data && method !== 'GET') {
      options.body = JSON.stringify(data)
    }
    const res = await fetch(API_BASE + path, options)
    if (res.status === 401 || (path === '/auth/me' && res.status === 422)) {
      this.clearToken()
      window.location.href = '/login'
      throw new Error('Unauthorized')
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || 'Request failed')
    }
    return res.json()
  },

  get(path) { return this.request('GET', path) },
  post(path, data) { return this.request('POST', path, data) },
  patch(path, data) { return this.request('PATCH', path, data) },
  delete(path) { return this.request('DELETE', path) },

  async getBlob(path) {
    const headers = {}
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }
    const res = await fetch(API_BASE + path, { method: 'GET', headers })
    if (res.status === 401) {
      this.clearToken()
      window.location.href = '/login'
      throw new Error('Unauthorized')
    }
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail || 'Request failed')
    }
    return res.blob()
  },

  // Auth
  login(username, password) {
    return this.post('/auth/login', { username, password }).then(data => {
      this.setToken(data.access_token)
      return this.get('/auth/me')
        .then(user => {
          currentUser = user
          return user
        })
        .catch(err => {
          this.clearToken()
          throw err
        })
    })
  },
  getMe() {
    if (!normalizeToken(token)) {
      this.clearToken()
      return Promise.reject(new Error('Unauthorized'))
    }
    return this.get('/auth/me').then(user => {
      currentUser = user
      return user
    })
  },
  logout() {
    this.clearToken()
  },

  // Users
  getUsers(role) {
    return this.get('/users' + (role ? `?role=${role}` : ''))
  },
  createUser(data) {
    return this.post('/users', data)
  },
  updateUser(id, data) {
    return this.patch(`/users/${id}`, data)
  },
  requestViewAllAccess() {
    return this.post('/users/view-all-request', {})
  },
  deleteUser(id) {
    return this.delete(`/users/${id}`)
  },

  // Reports (Admin)
  getReports(params = {}) {
    const query = new URLSearchParams(params).toString()
    return this.get('/reports' + (query ? `?${query}` : ''))
  },
  getReport(id) {
    return this.get(`/reports/${id}`)
  },
  deleteReport(id) {
    return this.delete(`/reports/${id}`)
  },
  importReports(file, preAnnotationFile = null) {
    const formData = new FormData()
    formData.append('file', file)
    if (preAnnotationFile) {
      formData.append('pre_annotation_file', preAnnotationFile)
    }
    return fetch(API_BASE + '/reports/import', {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}` },
      body: formData
    }).then(async (res) => {
      const data = await res.json().catch(() => ({}))
      if (!res.ok) {
        throw new Error(data.detail || '导入失败')
      }
      return data
    })
  },
  getImportTask(taskId) {
    return this.get(`/reports/import-tasks/${taskId}`)
  },
  getImportErrors(taskId) {
    return this.get(`/reports/import-tasks/${taskId}/errors`)
  },
  assignReports(reportIds = [], doctorId = null, doctorIds = null, mode = 'auto') {
    const payload = {}
    if (Array.isArray(reportIds) && reportIds.length > 0) {
      payload.report_ids = reportIds
    }
    if (doctorId !== null && doctorId !== undefined && doctorId !== '') {
      payload.doctor_id = doctorId
    }
    if (Array.isArray(doctorIds) && doctorIds.length > 0) {
      payload.doctor_ids = doctorIds
    }
    payload.mode = mode
    return this.post('/reports/assign', payload)
  },
  exportAnnotations(params = {}) {
    const query = new URLSearchParams(params).toString()
    return this.get('/export/annotations' + (query ? `?${query}` : ''))
  },
  exportAllReports(params = {}) {
    const query = new URLSearchParams(params).toString()
    return this.getBlob('/reports/export/all' + (query ? `?${query}` : ''))
  },

  // Doctor
  getDoctorReports(params = {}) {
    const query = new URLSearchParams(params).toString()
    return this.get('/doctor/reports' + (query ? `?${query}` : ''))
  },
  getDoctorReport(id) {
    return this.get(`/doctor/reports/${id}`)
  },
  saveDraft(reportId, data) {
    return this.post(`/doctor/reports/${reportId}/annotation/draft`, { data })
  },
  submitAnnotation(reportId, data) {
    return this.post(`/doctor/reports/${reportId}/annotation/submit`, { data })
  },
  cancelAnnotation(reportId) {
    return this.post(`/doctor/reports/${reportId}/annotation/cancel`, {})
  }
}
