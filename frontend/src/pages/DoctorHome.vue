<template>
  <div class="doctor-workbench">
    <aside class="left-panel">
      <div class="filter-row">
        <el-radio-group v-model="activeFilter" size="small" @change="loadReports">
          <el-radio-button label="all">全部</el-radio-button>
          <el-radio-button label="unannotated">未标注</el-radio-button>
          <el-radio-button label="annotated">已标注</el-radio-button>
        </el-radio-group>
      </div>

      <div class="search-row">
        <el-input
          v-model="reportQuery"
          placeholder="按标号搜索报告"
          clearable
          @keyup.enter="loadReports"
        >
          <template #append>
            <el-button @click="loadReports">搜索</el-button>
          </template>
        </el-input>
      </div>

      <div class="scope-row">
        <el-checkbox v-model="onlyMine" @change="handleOnlyMineChange">仅查看自己任务</el-checkbox>
      </div>

      <div class="report-list-wrap">
        <div class="report-list-header">
          <span>任务列表</span>
          <span>{{ reportList.length }} 条</span>
        </div>
        <div class="report-table-header">
          <span>状态</span>
          <span>检查号 / 标号</span>
        </div>
        <div class="report-list" ref="reportListRef" @scroll="handleReportListScroll">
          <div class="virtual-spacer" :style="{ height: `${virtualList.totalHeight}px` }">
            <div class="virtual-content" :style="{ transform: `translateY(${virtualList.offsetY}px)` }">
          <div
            v-for="report in virtualList.items"
            :key="report.id"
            :class="['report-item', { active: currentReport?.id === report.id, done: isAnnotated(report.status) }]"
            @click="openReport(report)"
          >
            <span class="dot" :class="isAnnotated(report.status) ? 'done' : 'todo'" />
            <div class="report-texts">
              <div class="report-id">{{ report.ris_no || report.external_id || ('R' + report.id) }}</div>
              <div class="report-sub">{{ getStatusText(report.status) }}</div>
            </div>
          </div>
            </div>
          </div>
        </div>
      </div>

      <div class="progress-wrap">
        <div class="progress-title">工作进度 {{ progress.done }}/{{ progress.total }}</div>
        <el-progress :percentage="progressPercent" :stroke-width="10" />
      </div>
    </aside>

    <section class="middle-panel">
      <div class="middle-header">
        <div>
          <div class="report-title">{{ reportHeaderTitle }}</div>
          <div class="report-meta">检查号：{{ currentReport?.ris_no || '-' }}</div>
        </div>
        <div class="middle-actions">
          <el-button type="primary" @click="createManualCardFromSelection">标注选中文本</el-button>
          <el-button @click="saveDraft" :loading="saving">暂存</el-button>
          <el-button type="success" @click="submitReport" :loading="submitting">完成标注</el-button>
        </div>
      </div>

      <div class="report-sheet" v-if="currentReport">
        <div class="sheet-head">
          <h2>{{ reportHeaderTitle }}</h2>
          <div>项目：{{ currentReport.exam_item || '-' }}</div>
        </div>

        <div class="sheet-body">
          <div class="section-block" data-field="description" @click="handleHighlightClick">
            <h3>【检查所见】</h3>
            <div class="section-content" v-html="getHighlightedHtml('description')"></div>
          </div>
          <div class="section-block" data-field="impression" @click="handleHighlightClick">
            <h3>【诊断意见】</h3>
            <div class="section-content" v-html="getHighlightedHtml('impression')"></div>
          </div>
        </div>
      </div>

      <el-empty v-else description="请选择左侧报告" />
    </section>

    <aside class="right-panel">
      <div class="right-header">纠错建议</div>
      <div class="cards">
        <el-empty v-if="cards.length === 0" description="暂无纠错卡片" />

        <el-card
          v-for="(card, idx) in cards"
          :key="card.id"
          :class="['error-card', { selected: selectedCardId === card.id }]"
          shadow="hover"
          draggable="true"
          @dragstart="onCardDragStart(idx)"
          @dragover.prevent
          @drop="onCardDrop(idx)"
        >
          <template #header>
            <div class="card-head">
              <div>
                <el-tag size="small" :type="card.kind === 'pre' ? 'warning' : 'primary'">
                  {{ card.kind === 'pre' ? '预标注' : '手动标注' }}
                </el-tag>
                <el-tag v-if="card.kind === 'pre' && card.state === 'saved'" size="small" type="danger">预标注错误</el-tag>
                <span class="card-index">#{{ idx + 1 }}</span>
              </div>
              <div class="card-field">{{ fieldText(card.content_type) }}</div>
            </div>
          </template>

          <div class="card-body">
            <div class="row"><span class="label">错误文本：</span>{{ card.source || '-' }}</div>
            <div class="row" v-if="showTarget(card)"><span class="label">纠正方向：</span>{{ card.target || '-' }}</div>

            <div v-if="isEditing(card)">
              <el-select v-model="card.error_type" placeholder="错误类型" style="width: 100%; margin-bottom: 8px" @change="applyDefaultSeverity(card)">
                <el-option v-for="item in errorTypeOptions" :key="item" :label="item" :value="item" />
              </el-select>
              <el-select v-model="card.severity" placeholder="错误级别" style="width: 100%; margin-bottom: 8px">
                <el-option label="低" value="low" />
                <el-option label="中" value="medium" />
                <el-option label="高" value="high" />
              </el-select>
              <el-input
                v-if="showTarget(card)"
                v-model="card.target"
                placeholder="纠正后内容"
                style="margin-bottom: 8px"
              />
              <el-input
                v-model="card.alert_message"
                type="textarea"
                :rows="2"
                placeholder="建议说明"
              />
            </div>

            <div v-else>
              <div class="row"><span class="label">错误类型：</span>{{ card.error_type || '-' }}</div>
              <div class="row"><span class="label">错误级别：</span>{{ severityText(card.severity) }}</div>
              <div class="row"><span class="label">建议说明：</span>{{ card.alert_message || '-' }}</div>
            </div>
          </div>

          <div class="card-actions">
            <template v-if="card.kind === 'pre'">
              <el-button v-if="card.state === 'pending'" size="small" type="success" @click="confirmPreCard(card)">确认</el-button>
              <el-button v-if="card.state === 'pending'" size="small" @click="editCard(card)">修改</el-button>
              <el-button v-if="card.state === 'confirmed'" size="small" @click="editCard(card)">修改</el-button>
              <el-button v-if="card.state === 'editing'" size="small" type="primary" @click="saveCard(card)">保存</el-button>
              <el-button v-if="card.state === 'editing'" size="small" @click="cancelEdit(card)">取消</el-button>
            </template>

            <template v-else>
              <el-button v-if="card.state !== 'editing'" size="small" @click="editCard(card)">修改</el-button>
              <el-button v-if="card.state === 'editing'" size="small" type="primary" @click="saveCard(card)">保存</el-button>
              <el-button v-if="card.state === 'editing'" size="small" @click="removeManualCard(card)">取消</el-button>
            </template>
          </div>
        </el-card>
      </div>
    </aside>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../api'

const activeFilter = ref('all')
const reportQuery = ref('')
const onlyMine = ref(true)
const currentUser = ref(null)

const reportList = ref([])
const currentReport = ref(null)
const cards = ref([])
const selectedCardId = ref(null)
const dragCardIndex = ref(-1)
const reportListRef = ref(null)
const reportListScrollTop = ref(0)

const saving = ref(false)
const submitting = ref(false)
const progress = ref({ done: 0, total: 0 })
const VIRTUAL_ROW_HEIGHT = 52
const VIRTUAL_VIEWPORT_HEIGHT = 300

const errorTypeOptions = [
  'sexs', 'typos', 'typoTerms',
  'bodyParts', 'examitems', 'typo_modality',
  'typo_unit', 'organectomys', 'positions'
]

const reportHeaderTitle = computed(() => {
  const modality = currentReport.value?.modality || currentReport.value?.exam_item || '影像'
  return `${modality}检查报告单`
})

const progressPercent = computed(() => {
  if (!progress.value.total) return 0
  return Math.round((progress.value.done / progress.value.total) * 100)
})

const virtualList = computed(() => {
  const total = reportList.value.length
  const start = Math.max(0, Math.floor(reportListScrollTop.value / VIRTUAL_ROW_HEIGHT) - 5)
  const visibleCount = Math.ceil(VIRTUAL_VIEWPORT_HEIGHT / VIRTUAL_ROW_HEIGHT) + 10
  const end = Math.min(total, start + visibleCount)
  return {
    items: reportList.value.slice(start, end),
    totalHeight: total * VIRTUAL_ROW_HEIGHT,
    offsetY: start * VIRTUAL_ROW_HEIGHT
  }
})

const isAnnotated = (status) => ['SUBMITTED', 'DONE'].includes(status)

const getStatusText = (status) => {
  const map = {
    ASSIGNED: '未标注',
    IN_PROGRESS: '未标注',
    SUBMITTED: '已标注',
    DONE: '已标注'
  }
  return map[status] || status
}

const fieldText = (field) => {
  const normalized = normalizeContentType(field)
  if (normalized === 'description') return '检查所见'
  if (normalized === 'impression') return '诊断意见'
  return field || '未知字段'
}

const normalizeContentType = (contentType) => {
  const v = String(contentType || '').trim().toLowerCase()
  if (['description', 'desc', '检查所见'].includes(v)) return 'description'
  if (['impression', 'impress', '诊断意见'].includes(v)) return 'impression'
  return ''
}

const normalizeIdText = (value) => {
  if (value === null || value === undefined) return ''
  const text = String(value).trim()
  return text.endsWith('.0') ? text.slice(0, -2) : text
}

const riskByErrorType = (errorType) => {
  if (['sexs', 'typos', 'typoTerms'].includes(errorType)) return 'low'
  if (['bodyParts', 'examitems', 'typo_modality'].includes(errorType)) return 'medium'
  if (['typo_unit', 'organectomys', 'positions'].includes(errorType)) return 'high'
  return 'medium'
}

const severityText = (v) => {
  const map = { low: '低', medium: '中', high: '高' }
  return map[v] || v || '-'
}

const showTarget = (card) => {
  return card.alert_type === '0' || card.alert_type === '2'
}

const isEditing = (card) => card.state === 'editing'

const applyDefaultSeverity = (card) => {
  if (!card.severity) card.severity = riskByErrorType(card.error_type)
}

const handleReportListScroll = (event) => {
  reportListScrollTop.value = event.target?.scrollTop || 0
}

const getReportTextByField = (field) => {
  if (!currentReport.value) return ''
  if (field === 'description') return currentReport.value.description || ''
  if (field === 'impression') return currentReport.value.impression || ''
  return ''
}

const escapeHtml = (text) => {
  return String(text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}

const resolveRange = (text, card) => {
  const source = card.source || ''
  const parsedStart = Number.parseInt(card.source_in_start, 10)
  const parsedEnd = Number.parseInt(card.source_in_end, 10)
  const candidates = []

  if (Number.isInteger(parsedStart) && Number.isInteger(parsedEnd)) {
    candidates.push([parsedStart, parsedEnd], [parsedStart - 1, parsedEnd - 1])
  }
  if (Number.isInteger(parsedStart) && source) {
    candidates.push([parsedStart, parsedStart + source.length], [parsedStart - 1, parsedStart - 1 + source.length])
  }

  for (const [rawStart, rawEnd] of candidates) {
    const start = Math.max(0, rawStart)
    const end = Math.min(text.length, Math.max(start, rawEnd))
    if (!source || text.slice(start, end) === source) {
      return { start, end }
    }
  }

  if (source) {
    const index = text.indexOf(source)
    if (index >= 0) return { start: index, end: index + source.length }
  }
  return null
}

const buildHighlights = (field) => {
  const text = getReportTextByField(field)
  if (!text) return []
  const cardOrderMap = new Map()
  let order = 1
  for (const card of cards.value) {
    const cardField = normalizeContentType(card.content_type)
    if (!cardField) continue
    const cardText = getReportTextByField(cardField)
    if (!cardText) continue
    const range = resolveRange(cardText, card)
    if (!range) continue
    cardOrderMap.set(card.id, order)
    order += 1
  }

  const rawHighlights = cards.value
    .filter((card) => normalizeContentType(card.content_type) === field)
    .map((card) => {
      const range = resolveRange(text, card)
      if (!range) return null
      return {
        ...card,
        index: cardOrderMap.get(card.id) || 0,
        start: range.start,
        end: range.end
      }
    })
    .filter(Boolean)

  // 高亮区间若发生重叠，会导致 HTML 二次替换时切断已有标签，出现乱码（如 <sp2an>）。
  // 这里统一按原始文本坐标从左到右拼接：
  // 1) 完全相同的区间合并为一组（用于同一信息源多个错误时显示多个角标）
  // 2) 非完全相同但有重叠的区间跳过后者，避免破坏 HTML 结构
  const sorted = rawHighlights
    .filter((h) => Number.isInteger(h.start) && Number.isInteger(h.end) && h.end > h.start)
    .sort((a, b) => (a.start - b.start) || (a.end - b.end) || (a.index - b.index))

  const grouped = []
  for (const h of sorted) {
    const last = grouped[grouped.length - 1]
    if (!last) {
      grouped.push({ start: h.start, end: h.end, cards: [h] })
      continue
    }
    if (h.start === last.start && h.end === last.end) {
      last.cards.push(h)
      continue
    }
    if (h.start < last.end) {
      continue
    }
    grouped.push({ start: h.start, end: h.end, cards: [h] })
  }
  return grouped
}

const getHighlightedHtml = (field) => {
  const text = getReportTextByField(field)
  if (!text) return '无'

  const highlights = buildHighlights(field)
  if (!highlights.length) return escapeHtml(text)

  let cursor = 0
  const parts = []
  for (const h of highlights) {
    parts.push(escapeHtml(text.slice(cursor, h.start)))
    const primaryCard = h.cards[0]
    const sourceText = text.slice(h.start, h.end) || primaryCard.source
    const cls = h.cards.some((card) => card.kind === 'manual') ? 'hl-chip manual' : 'hl-chip pre'
    const badge = h.cards
      .map((card, idx) => `<span class="hl-mark" data-card-id="${card.id}" style="right:${-7 - idx * 14}px">${card.index}</span>`)
      .join('')
    const replacement = `<span class="${cls}" data-card-id="${primaryCard.id}" title="${escapeHtml(primaryCard.alert_message || '')}">${escapeHtml(sourceText)}${badge}</span>`
    parts.push(replacement)
    cursor = h.end
  }
  parts.push(escapeHtml(text.slice(cursor)))

  return parts.join('')
}

const handleHighlightClick = (event) => {
  const mark = event.target.closest('.hl-mark')
  if (mark?.dataset.cardId) {
    selectedCardId.value = mark.dataset.cardId
    return
  }
  const chip = event.target.closest('.hl-chip')
  if (!chip) return
  const cardId = chip.dataset.cardId
  if (!cardId) return
  selectedCardId.value = cardId
}

const cardToErrorItem = (card) => {
  return {
    error_type: card.error_type || '',
    severity: card.severity || riskByErrorType(card.error_type || ''),
    location: fieldText(card.content_type),
    evidence_text: card.source || '',
    description: card.alert_message || '',
    suggestion: showTarget(card) ? (card.target || '') : '',
    anchor: {
      content_type: normalizeContentType(card.content_type),
      source_in_start: card.source_in_start,
      source_in_end: card.source_in_end,
      alert_type: card.alert_type,
      source: card.source,
      target: card.target,
      kind: card.kind,
      state: card.state
    }
  }
}

const buildPayload = () => {
  const validCards = cards.value.filter((card) => {
    if (card.kind === 'pre') return ['confirmed', 'saved'].includes(card.state)
    return card.state === 'saved'
  })

  return {
    no_error: validCards.length === 0,
    error_items: validCards.map(cardToErrorItem),
    note: ''
  }
}

const loadProgress = async () => {
  const params = { tab: 'all', page: 1, page_size: 1000, only_mine: onlyMine.value }
  if (reportQuery.value) params.q = reportQuery.value

  const all = await api.getDoctorReports(params)
  const done = all.items.filter((item) => isAnnotated(item.status)).length
  progress.value = { done, total: all.total }
}

const loadReports = async () => {
  const params = { tab: activeFilter.value, page: 1, page_size: 1000, only_mine: onlyMine.value }
  if (reportQuery.value) params.q = reportQuery.value

  const res = await api.getDoctorReports(params)
  reportList.value = res.items
  reportListScrollTop.value = 0

  await loadProgress()

  if (!currentReport.value && reportList.value.length > 0) {
    await openReport(reportList.value[0])
    return
  }

  if (currentReport.value) {
    const stillExists = reportList.value.find((r) => r.id === currentReport.value.id)
    if (!stillExists) {
      currentReport.value = null
      cards.value = []
      selectedCardId.value = null
      if (reportList.value.length > 0) {
        await openReport(reportList.value[0])
      }
    }
  }
}

const buildPreCards = (report) => {
  const reportRisNo = normalizeIdText(report.ris_no || report.external_id)
  const preAnnos = report.pre_annotations || []
  const seen = new Set()

  return preAnnos
    .filter((item) => {
      const preRisNo = normalizeIdText(item.ris_no || item.RIS_NO || reportRisNo)
      return preRisNo === reportRisNo
    })
    .map((item, idx) => {
      const card = {
        id: `pre-${report.id}-${idx}`,
        kind: 'pre',
        state: 'pending',
        content_type: item.content_type || '',
        source: item.source || '',
        target: item.target || '',
        alert_type: String(item.alert_type ?? '0'),
        alert_message: item.alert_message || item.alert_msg || '',
        error_type: item.err_type || 'typos',
        severity: riskByErrorType(item.err_type || 'typos'),
        source_in_start: item.source_in_start,
        source_in_end: item.source_in_end
      }

      const dedupKey = [
        normalizeContentType(card.content_type),
        String(card.source || '').trim(),
        String(card.target || '').trim(),
        String(card.alert_type || '').trim(),
        String(card.alert_message || '').trim(),
        String(card.error_type || '').trim(),
        String(card.source_in_start ?? ''),
        String(card.source_in_end ?? '')
      ].join('||')
      if (seen.has(dedupKey)) return null
      seen.add(dedupKey)
      return card
    })
    .filter(Boolean)
}

const buildManualCardsFromAnnotation = (report) => {
  const annotation = report.annotation?.data
  if (!annotation?.error_items?.length) return []

  return annotation.error_items.map((item, idx) => ({
    id: `manual-${report.id}-${idx}`,
    kind: 'manual',
    state: 'saved',
    content_type: item.anchor?.content_type || item.location || 'description',
    source: item.evidence_text || item.anchor?.source || '',
    target: item.suggestion || item.anchor?.target || '',
    alert_type: String(item.anchor?.alert_type ?? (item.suggestion ? '2' : '1')),
    alert_message: item.description || '',
    error_type: item.error_type || 'typos',
    severity: item.severity || riskByErrorType(item.error_type || 'typos'),
    source_in_start: item.anchor?.source_in_start,
    source_in_end: item.anchor?.source_in_end
  }))
}

const dedupeCards = (items) => {
  const seen = new Set()
  const result = []
  for (const card of items) {
    const key = [
      card.kind || '',
      normalizeContentType(card.content_type),
      String(card.source || '').trim(),
      String(card.target || '').trim(),
      String(card.alert_type || '').trim(),
      String(card.alert_message || '').trim(),
      String(card.error_type || '').trim(),
      String(card.source_in_start ?? ''),
      String(card.source_in_end ?? '')
    ].join('||')
    if (seen.has(key)) continue
    seen.add(key)
    result.push(card)
  }
  return result
}

const openReport = async (report) => {
  const detail = await api.getDoctorReport(report.id)
  currentReport.value = detail

  const preCards = buildPreCards(detail)
  const manualCards = buildManualCardsFromAnnotation(detail)
  cards.value = dedupeCards([...preCards, ...manualCards])
  selectedCardId.value = cards.value[0]?.id || null
}

const editCard = (card) => {
  card._backup = { ...card }
  card.state = 'editing'
  selectedCardId.value = card.id
}

const saveCard = (card) => {
  card.state = 'saved'
  card._backup = null
  applyDefaultSeverity(card)
  ElMessage.success('卡片已保存')
}

const cancelEdit = (card) => {
  if (card._backup) {
    Object.assign(card, card._backup)
  }
  card._backup = null
  card.state = card.kind === 'pre' ? 'pending' : 'saved'
}

const removeManualCard = (card) => {
  cards.value = cards.value.filter((item) => item.id !== card.id)
}

const confirmPreCard = (card) => {
  card.state = 'confirmed'
  applyDefaultSeverity(card)
}

const createManualCardFromSelection = () => {
  if (!currentReport.value) {
    ElMessage.warning('请先选择一条报告')
    return
  }

  const selection = window.getSelection()
  const selectedText = selection?.toString()?.trim()
  if (!selectedText) {
    ElMessage.warning('请先在中间报告中选中要标注的文本')
    return
  }

  const anchorEl = selection.anchorNode?.parentElement
  const field = anchorEl?.closest('[data-field]')?.dataset?.field || 'description'

  const now = Date.now()
  const newCard = {
    id: `manual-${currentReport.value.id}-${now}`,
    kind: 'manual',
    state: 'editing',
    content_type: field,
    source: selectedText,
    target: '',
    alert_type: '2',
    alert_message: '',
    error_type: 'typos',
    severity: 'low',
    source_in_start: null,
    source_in_end: null
  }

  cards.value.push(newCard)
  selectedCardId.value = newCard.id
}

const onCardDragStart = (index) => {
  dragCardIndex.value = index
}

const onCardDrop = (targetIndex) => {
  if (dragCardIndex.value < 0 || dragCardIndex.value === targetIndex) return
  const moved = cards.value.splice(dragCardIndex.value, 1)[0]
  cards.value.splice(targetIndex, 0, moved)
  dragCardIndex.value = -1
}

const saveDraft = async () => {
  if (!currentReport.value) return
  saving.value = true
  try {
    await api.saveDraft(currentReport.value.id, buildPayload())
    ElMessage.success('草稿已保存')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    saving.value = false
  }
}

const submitReport = async () => {
  if (!currentReport.value) return
  submitting.value = true
  try {
    await api.submitAnnotation(currentReport.value.id, buildPayload())
    ElMessage.success('标注完成')
    currentReport.value = null
    cards.value = []
    selectedCardId.value = null
    if (activeFilter.value === 'unannotated') {
      await loadReports()
    } else {
      await loadReports()
    }
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    submitting.value = false
  }
}

const handleOnlyMineChange = async (value) => {
  if (!value && !currentUser.value?.can_view_all) {
    try {
      await ElMessageBox.confirm(
        '取消“仅查看自己任务”需要管理员授予权限。是否提交申请？',
        '权限申请',
        { confirmButtonText: '提交申请', cancelButtonText: '取消', type: 'warning' }
      )
      await api.requestViewAllAccess()
      ElMessage.success('已向管理员提交申请')
    } catch (_e) {
      // ignore
    } finally {
      onlyMine.value = true
    }
    return
  }

  await loadReports()
}

onMounted(async () => {
  try {
    currentUser.value = await api.getMe()
    await loadReports()
  } catch (e) {
    ElMessage.error(e.message || '加载医生任务失败')
  }
})
</script>

<style scoped>
.doctor-workbench {
  display: grid;
  grid-template-columns: 300px 1fr 380px;
  gap: 12px;
  height: calc(100vh - 130px);
}

.left-panel,
.middle-panel,
.right-panel {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  padding: 12px;
  overflow: hidden;
}

.left-panel {
  display: flex;
  flex-direction: column;
}

.filter-row,
.search-row,
.scope-row {
  margin-bottom: 10px;
}

.report-list-wrap {
  border: 1px dashed #d1d5db;
  border-radius: 8px;
  padding: 8px;
  margin-bottom: 20px;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.report-list-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  color: #6b7280;
  font-size: 12px;
}

.report-table-header {
  display: grid;
  grid-template-columns: 56px 1fr;
  padding: 6px 8px;
  border-bottom: 1px solid #e5e7eb;
  color: #6b7280;
  font-size: 12px;
}

.report-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}

.virtual-spacer {
  position: relative;
  width: 100%;
}

.virtual-content {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
}

.report-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px;
  height: 52px;
  box-sizing: border-box;
  border-radius: 6px;
  cursor: pointer;
}

.report-item:hover {
  background: #f3f4f6;
}

.report-item.active {
  background: #e0f2fe;
}

.report-item.done .report-id {
  color: #16a34a;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
}

.dot.done {
  background: #22c55e;
}

.dot.todo {
  background: #d1d5db;
}

.report-id {
  font-weight: 600;
  font-size: 13px;
}

.report-sub {
  font-size: 12px;
  color: #6b7280;
}

.progress-wrap {
  margin-top: auto;
}

.progress-title {
  margin-bottom: 6px;
  font-size: 12px;
  color: #6b7280;
}

.middle-panel {
  display: flex;
  flex-direction: column;
}

.middle-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.report-title {
  font-size: 16px;
  font-weight: 700;
}

.report-meta {
  color: #6b7280;
  font-size: 12px;
}

.middle-actions {
  display: flex;
  gap: 8px;
}

.report-sheet {
  flex: 1;
  overflow: auto;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
}

.sheet-head {
  border-bottom: 1px solid #e5e7eb;
  padding: 12px;
}

.sheet-head h2 {
  margin: 0 0 4px 0;
}

.sheet-body {
  padding: 12px;
}

.section-block {
  margin-bottom: 16px;
}

.section-block h3 {
  margin: 0 0 8px 0;
}

.section-content {
  line-height: 1.8;
  white-space: pre-wrap;
}

.section-content :deep(.hl-chip) {
  position: relative;
  display: inline-block;
  padding: 1px 4px;
  border-radius: 4px;
  cursor: pointer;
}

.section-content :deep(.hl-chip.pre) {
  background: #fef3c7;
  color: #92400e;
}

.section-content :deep(.hl-chip.manual) {
  background: #dbeafe;
  color: #1e40af;
}

.section-content :deep(.hl-mark) {
  position: absolute;
  top: -7px;
  right: -7px;
  width: 14px;
  height: 14px;
  line-height: 14px;
  border-radius: 999px;
  text-align: center;
  font-size: 10px;
  color: #fff;
  background: #ef4444;
}

.right-panel {
  display: flex;
  flex-direction: column;
}

.right-header {
  font-size: 15px;
  font-weight: 700;
  margin-bottom: 10px;
}

.cards {
  overflow-y: auto;
  padding-right: 2px;
}

.error-card {
  margin-bottom: 10px;
  border: 1px solid #e5e7eb;
  cursor: grab;
}

.error-card.selected {
  border-color: #3b82f6;
}

.card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-index {
  margin-left: 6px;
  color: #6b7280;
  font-size: 12px;
}

.card-field {
  font-size: 12px;
  color: #6b7280;
}

.card-body .row {
  font-size: 13px;
  line-height: 1.7;
}

.card-body .label {
  color: #6b7280;
}

.card-actions {
  margin-top: 8px;
  display: flex;
  gap: 8px;
}

@media (max-width: 1280px) {
  .doctor-workbench {
    grid-template-columns: 280px 1fr;
  }

  .right-panel {
    grid-column: 1 / 3;
    height: 300px;
  }
}
</style>
