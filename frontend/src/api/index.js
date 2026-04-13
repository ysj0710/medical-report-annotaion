const API_BASE = '/api'
const LOCAL_HOSTS = new Set(['localhost', '127.0.0.1'])
const TOKEN_STORAGE_KEY = 'token'

function buildWebSocketOriginFromTarget(target) {
  const raw = String(target || '').trim()
  if (!raw) return ''
  try {
    const resolved = new URL(raw, window.location.origin)
    if (resolved.protocol === 'http:') resolved.protocol = 'ws:'
    if (resolved.protocol === 'https:') resolved.protocol = 'wss:'
    return `${resolved.protocol}//${resolved.host}`
  } catch (_e) {
    return ''
  }
}

function pushUniqueUrl(list, url) {
  const value = String(url || '').trim()
  if (!value || list.includes(value)) return
  list.push(value)
}

function normalizeToken(raw) {
  if (!raw) return null
  const value = String(raw).trim()
  if (!value || value === 'null' || value === 'undefined') return null
  return value
}

function getSessionStorage() {
  if (typeof window === 'undefined') return null
  try {
    return window.sessionStorage
  } catch (_e) {
    return null
  }
}

function getLocalStorage() {
  if (typeof window === 'undefined') return null
  try {
    return window.localStorage
  } catch (_e) {
    return null
  }
}

function readStoredToken() {
  const sessionStorageRef = getSessionStorage()
  const localStorageRef = getLocalStorage()

  const sessionToken = normalizeToken(sessionStorageRef?.getItem(TOKEN_STORAGE_KEY))
  if (sessionToken) return sessionToken

  const legacyLocalToken = normalizeToken(localStorageRef?.getItem(TOKEN_STORAGE_KEY))
  if (legacyLocalToken && sessionStorageRef) {
    sessionStorageRef.setItem(TOKEN_STORAGE_KEY, legacyLocalToken)
    localStorageRef?.removeItem(TOKEN_STORAGE_KEY)
  }
  return legacyLocalToken
}

function persistToken(nextToken) {
  const sessionStorageRef = getSessionStorage()
  const localStorageRef = getLocalStorage()

  if (nextToken) {
    sessionStorageRef?.setItem(TOKEN_STORAGE_KEY, nextToken)
  } else {
    sessionStorageRef?.removeItem(TOKEN_STORAGE_KEY)
  }

  // 兼容旧版本：清掉共享 localStorage，避免多窗口串号。
  localStorageRef?.removeItem(TOKEN_STORAGE_KEY)
}

let token = readStoredToken()
let currentUser = null
let currentUserRequest = null

function setCurrentUser(user) {
  currentUser = user || null
  return currentUser
}

export const api = {
  setToken(t) {
    token = normalizeToken(t)
    persistToken(token)
  },
  clearToken() {
    token = null
    persistToken(null)
    currentUser = null
    currentUserRequest = null
  },
  getToken() {
    return token
  },
  getCurrentUser() {
    return currentUser
  },
  buildCollaborationWebSocketUrls(reportId) {
    const authToken = normalizeToken(token)
    if (!authToken || !reportId || typeof window === 'undefined') return []

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const encodedToken = encodeURIComponent(authToken)
    const path = `${API_BASE}/doctor/reports/${reportId}/collaboration/ws?token=${encodedToken}`
    const urls = []
    const hostname = window.location.hostname
    pushUniqueUrl(urls, `${protocol}//${window.location.host}${path}`)

    const envTarget = buildWebSocketOriginFromTarget(
      import.meta.env.VITE_COLLABORATION_WS_TARGET ||
      import.meta.env.VITE_API_PROXY_TARGET
    )
    if (envTarget) {
      pushUniqueUrl(urls, `${envTarget}${path}`)
    }

    if (LOCAL_HOSTS.has(hostname)) {
      pushUniqueUrl(urls, `${protocol}//127.0.0.1:8088${path}`)
      pushUniqueUrl(urls, `${protocol}//localhost:8088${path}`)
    }

    return urls
  },
  buildCollaborationWebSocketUrl(reportId) {
    return this.buildCollaborationWebSocketUrls(reportId)[0] || ''
  },
  buildReportUpdatesWebSocketUrls() {
    const authToken = normalizeToken(token)
    if (!authToken || typeof window === 'undefined') return []

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const encodedToken = encodeURIComponent(authToken)
    const path = `${API_BASE}/doctor/reports/updates/ws?token=${encodedToken}`
    const urls = []
    const hostname = window.location.hostname
    pushUniqueUrl(urls, `${protocol}//${window.location.host}${path}`)

    const envTarget = buildWebSocketOriginFromTarget(
      import.meta.env.VITE_COLLABORATION_WS_TARGET ||
      import.meta.env.VITE_API_PROXY_TARGET
    )
    if (envTarget) {
      pushUniqueUrl(urls, `${envTarget}${path}`)
    }

    if (LOCAL_HOSTS.has(hostname)) {
      pushUniqueUrl(urls, `${protocol}//127.0.0.1:8088${path}`)
      pushUniqueUrl(urls, `${protocol}//localhost:8088${path}`)
    }

    return urls
  },
  buildReportUpdatesWebSocketUrl() {
    return this.buildReportUpdatesWebSocketUrls()[0] || ''
  },

  async request(method, path, data = null) {
    const headers = { 'Content-Type': 'application/json' }
    const isLoginPath = path === '/auth/login'
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
    if (!isLoginPath && (res.status === 401 || (path === '/auth/me' && res.status === 422))) {
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
      currentUserRequest = null
      return setCurrentUser(data.user)
    })
  },
  getMe() {
    if (!normalizeToken(token)) {
      this.clearToken()
      return Promise.reject(new Error('Unauthorized'))
    }
    if (currentUser) {
      return Promise.resolve(currentUser)
    }
    if (currentUserRequest) {
      return currentUserRequest
    }
    currentUserRequest = this.get('/auth/me')
      .then(user => setCurrentUser(user))
      .catch(err => {
        currentUserRequest = null
        throw err
      })
    return currentUserRequest.finally(() => {
      currentUserRequest = null
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
  batchDeleteReports(reportIds = []) {
    return this.post('/reports/batch-delete', { report_ids: reportIds })
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
  assignReports({
    mode,
    reportIds = [],
    assignAll = false,
    q = '',
    status = '',
    doctorId = null,
    doctorIds = null,
    dispatchMode = 'auto'
  } = {}) {
    const payload = {}
    payload.mode = mode
    if (Array.isArray(reportIds) && reportIds.length > 0) {
      payload.report_ids = reportIds
    }
    if (assignAll) {
      payload.assign_all = true
    }
    if (q) {
      payload.q = q
    }
    if (status) {
      payload.status = status
    }
    if (doctorId !== null && doctorId !== undefined && doctorId !== '') {
      payload.doctor_id = doctorId
    }
    if (Array.isArray(doctorIds) && doctorIds.length > 0) {
      payload.doctor_ids = doctorIds
    }
    payload.dispatch_mode = dispatchMode
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
  },
  collaborationHeartbeat(reportId, intent = 'view', activity = null) {
    return this.post(`/doctor/reports/${reportId}/collaboration/heartbeat`, { intent, activity })
  }
}
