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
          <span>任务列表（{{ reportList.length }} 条）</span>
          <el-popover placement="bottom-end" :width="320" trigger="click">
            <template #reference>
              <el-button size="small" text>自定义字段</el-button>
            </template>
            <div class="column-selector">
              <div class="column-selector-head">
                <span>选择展示列</span>
                <el-button link type="primary" @click="resetColumns">重置默认</el-button>
              </div>
              <el-checkbox-group v-model="visibleColumnKeys">
                <el-checkbox
                  v-for="col in doctorTableColumns"
                  :key="col.key"
                  :label="col.key"
                  :disabled="visibleColumnKeys.length === 1 && visibleColumnKeys.includes(col.key)"
                >
                  {{ col.label }}
                </el-checkbox>
              </el-checkbox-group>
            </div>
          </el-popover>
        </div>

        <div class="table-frame">
          <el-table
            ref="doctorTableRef"
            :data="reportList"
            row-key="id"
            border
            stripe
            highlight-current-row
            height="100%"
            @row-click="openReport"
          >
            <el-table-column label="序号" type="index" width="64" />
            <el-table-column
              v-for="col in visibleColumns"
              :key="col.key"
              :prop="col.prop"
              :label="col.label"
              :width="col.width"
              :min-width="col.minWidth"
              :show-overflow-tooltip="col.overflow !== false"
            >
              <template v-if="col.key === 'status'" #default="{ row }">
                <el-tag :type="getStatusType(row.status)">{{ getStatusText(row.status) }}</el-tag>
              </template>
              <template v-else-if="col.key === 'imported_at'" #default="{ row }">
                {{ formatTime(row.imported_at) }}
              </template>
            </el-table-column>
          </el-table>
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
          <el-button type="primary" @click="createManualCardFromSelection" :disabled="isReportAnnotated">标注选中文本</el-button>
          <el-button @click="saveDraft" :loading="saving" :disabled="isReportAnnotated">暂存</el-button>
          <el-button type="success" @click="submitReport" :loading="submitting" :disabled="isReportAnnotated">完成标注</el-button>
          <el-button v-if="isReportAnnotated" type="danger" plain @click="cancelSubmittedAnnotation">取消标注</el-button>
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
        >
          <template #header>
            <div class="card-head">
              <div>
                <el-tag size="small" :type="card.kind === 'pre' ? 'warning' : 'primary'">
                  {{ card.kind === 'pre' ? '预标注' : '手动标注' }}
                </el-tag>
                <span class="card-index">#{{ idx + 1 }}</span>
              </div>
              <div class="card-field">{{ fieldText(card.content_type) }}</div>
            </div>
          </template>

          <div class="card-body">
            <div class="row"><span class="label">错误文本：</span>{{ card.source || '（缺失）' }}</div>
            <div class="row" v-if="card.target"><span class="label">替换内容：</span>{{ card.target || '-' }}</div>

            <div v-if="isEditing(card)">
              <el-select v-model="card.error_type" placeholder="错误类型" style="width: 100%; margin-bottom: 8px" @change="applyDefaultSeverity(card)">
                <el-option v-for="item in errorTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
              <el-button-group class="severity-group">
                <el-button :type="card.severity === 'low' ? 'success' : 'default'" @click="card.severity = 'low'">低风险</el-button>
                <el-button :type="card.severity === 'medium' ? 'warning' : 'default'" @click="card.severity = 'medium'">中风险</el-button>
                <el-button :type="card.severity === 'high' ? 'danger' : 'default'" @click="card.severity = 'high'">高风险</el-button>
              </el-button-group>
              <el-input
                v-model="card.target"
                placeholder="替换后内容"
                style="margin-bottom: 8px"
              />
              <el-input
                v-model="card.alert_message"
                type="textarea"
                :rows="2"
                placeholder="建议说明（删除/仅提示必填）"
              />
            </div>

            <div v-else>
              <div class="row"><span class="label">错误类型：</span>{{ errorTypeText(card.error_type) }}</div>
              <div class="row"><span class="label">错误级别：</span>{{ severityText(card.severity) }}</div>
              <div class="row"><span class="label">建议说明：</span>{{ card.alert_message || '-' }}</div>
            </div>
          </div>

          <div class="card-actions">
            <template v-if="card.kind === 'pre'">
              <el-button v-if="card.state === 'pending'" size="small" type="success" @click="confirmPreCard(card)" :disabled="isReportAnnotated">确认</el-button>
              <el-button v-if="card.state === 'pending'" size="small" @click="editCard(card)" :disabled="isReportAnnotated">修改</el-button>
              <el-button v-if="card.state === 'confirmed'" size="small" @click="editCard(card)" :disabled="isReportAnnotated">修改</el-button>
              <el-button v-if="card.state === 'saved'" size="small" @click="editCard(card)" :disabled="isReportAnnotated">修改</el-button>
              <el-button v-if="card.state === 'editing'" size="small" type="primary" @click="saveCard(card)" :disabled="isReportAnnotated">保存</el-button>
              <el-button v-if="card.state === 'editing'" size="small" @click="cancelEdit(card)">取消</el-button>
            </template>

            <template v-else>
              <el-button v-if="card.state !== 'editing'" size="small" @click="editCard(card)" :disabled="isReportAnnotated">修改</el-button>
              <el-button v-if="card.state === 'editing'" size="small" type="primary" @click="saveCard(card)" :disabled="isReportAnnotated">保存</el-button>
              <el-button v-if="card.state === 'editing'" size="small" @click="removeManualCard(card)">取消</el-button>
            </template>
          </div>
        </el-card>
      </div>
    </aside>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../api'

const TASK_COLUMNS_STORAGE_KEY = 'doctor_task_visible_columns_v1'

const activeFilter = ref('all')
const reportQuery = ref('')
const onlyMine = ref(true)
const currentUser = ref(null)

const doctorTableRef = ref(null)
const reportList = ref([])
const currentReport = ref(null)
const cards = ref([])
const selectedCardId = ref(null)

const saving = ref(false)
const submitting = ref(false)
const progress = ref({ done: 0, total: 0 })

const doctorTableColumns = [
  { key: 'ris_no', label: '检查号(RIS_NO)', prop: 'ris_no', width: 150 },
  { key: 'modality', label: '检查类型', prop: 'modality', width: 110 },
  { key: 'patient_sex', label: '性别', prop: 'patient_sex', width: 70 },
  { key: 'patient_age', label: '年龄', prop: 'patient_age', width: 80 },
  { key: 'exam_item', label: '检查项目', prop: 'exam_item', minWidth: 220 },
  { key: 'exam_mode', label: '检查模式', prop: 'exam_mode', width: 140 },
  { key: 'status', label: '状态', prop: 'status', width: 120, overflow: false },
  { key: 'imported_at', label: '导入时间', prop: 'imported_at', width: 180 }
]

const visibleColumnKeys = ref(doctorTableColumns.map((item) => item.key))

const ERROR_TYPE_MAP = {
  bodyParts: '部位错误',
  examitems: '检查项目错误',
  organectomys: '器官切除/缺如信息错误',
  positions: '体位/位置错误',
  sexs: '性别错误',
  typo_modality: '检查类型错写',
  typo_unit: '单位错写/错误',
  typos: '错别字/拼写错误',
  typoTerms: '术语错写/术语错误'
}

const errorTypeOptions = [
  { value: 'sexs', label: '性别错误' },
  { value: 'typos', label: '错别字/拼写错误' },
  { value: 'typoTerms', label: '术语错写/术语错误' },
  { value: 'bodyParts', label: '部位错误' },
  { value: 'examitems', label: '检查项目错误' },
  { value: 'typo_modality', label: '检查类型错写' },
  { value: 'typo_unit', label: '单位错写/错误' },
  { value: 'organectomys', label: '器官切除/缺如信息错误' },
  { value: 'positions', label: '体位/位置错误' }
]

const reportHeaderTitle = computed(() => {
  const modality = currentReport.value?.modality || currentReport.value?.exam_item || '影像'
  return `${modality}检查报告单`
})

const progressPercent = computed(() => {
  if (!progress.value.total) return 0
  return Math.round((progress.value.done / progress.value.total) * 100)
})

const isReportAnnotated = computed(() => isAnnotated(currentReport.value?.status))

const visibleColumns = computed(() => {
  const selected = new Set(visibleColumnKeys.value)
  return doctorTableColumns.filter((col) => selected.has(col.key))
})

watch(visibleColumnKeys, (val) => {
  localStorage.setItem(TASK_COLUMNS_STORAGE_KEY, JSON.stringify(val))
}, { deep: true })

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

const getStatusType = (status) => {
  if (status === 'SUBMITTED' || status === 'DONE') return 'success'
  if (status === 'IN_PROGRESS') return 'warning'
  return 'info'
}

const formatTime = (value) => {
  if (!value) return '-'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '-'
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const resetColumns = () => {
  visibleColumnKeys.value = doctorTableColumns.map((item) => item.key)
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

const errorTypeText = (type) => ERROR_TYPE_MAP[type] || type || '-'

const normalizeAction = (action) => {
  if (['replace', 'delete', 'prompt'].includes(action)) return action
  return 'replace'
}

const hasPreReplacementByTargetAndMessage = (card) => {
  const source = String(card.source || '').trim()
  const target = String(card.target || '').trim()
  const message = String(card.alert_message || '')

  if (!target) return false
  if (source && target === source) return false

  const replaceHint = /替换|改为|应改为|修正为|更正为|应为|改成|改写/
  const nonReplaceHint = /删除|删去|去掉|移除|仅作提示|仅做提示|提示|注意|建议|复查|随访/
  if (replaceHint.test(message)) return true
  if (nonReplaceHint.test(message)) return false
  return true
}

const inferActionByCard = (card) => {
  const alertType = String(card.alert_type ?? '').trim()
  const source = String(card.source || '')
  const target = String(card.target || '')
  const messageRaw = String(card.alert_message || '')

  if (card.kind === 'pre') {
    if (alertType === '1') return 'delete'
    if (alertType === '3') return 'prompt'
    if (hasPreReplacementByTargetAndMessage(card)) return 'replace'
    if (/删除|删去|去掉|移除/.test(`${source}${messageRaw}`)) return 'delete'
    return 'prompt'
  }

  if (alertType === '1') return 'delete'
  if (alertType === '3') return 'prompt'
  if (target.trim()) return 'replace'

  const combined = `${source}${messageRaw}`
  if (/删除|删去|去掉|移除/.test(combined)) return 'delete'
  if (/提示|注意|建议|复查|随访/.test(combined)) return 'prompt'
  if (card.error_type === 'organectomys') return 'delete'

  return 'replace'
}

const syncActionToAlertType = (card) => {
  card.action = normalizeAction(card.action || inferActionByCard(card))
  const map = { replace: '2', delete: '1', prompt: '3' }
  card.alert_type = map[card.action]
}

const chooseActionOnConfirm = async (card) => {
  if (String(card.target || '').trim()) {
    card.action = 'replace'
    syncActionToAlertType(card)
    return true
  }

  if (!String(card.alert_message || '').trim()) {
    ElMessage.warning('当替换内容为空时，请先填写建议说明，再确认处理方式')
    return false
  }

  try {
    await ElMessageBox.confirm(
      '替换内容为空，请确认处理方式',
      '错误处理方式确认',
      {
        confirmButtonText: '删除内容并提示',
        cancelButtonText: '仅作提示',
        distinguishCancelAndClose: true,
        closeOnClickModal: false,
        closeOnPressEscape: false,
        type: 'warning'
      }
    )
    card.action = 'delete'
    syncActionToAlertType(card)
    return true
  } catch (e) {
    if (e === 'cancel') {
      card.action = 'prompt'
      syncActionToAlertType(card)
      return true
    }
    return false
  }
}

const isEditing = (card) => card.state === 'editing'

const applyDefaultSeverity = (card) => {
  if (!card.severity) card.severity = riskByErrorType(card.error_type)
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

  if ((Number.isInteger(parsedStart) && parsedStart < 0) || (Number.isInteger(parsedEnd) && parsedEnd < 0)) {
    return { start: 0, end: 0, missing: true }
  }

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
      return { start, end, missing: false }
    }
  }

  if (source) {
    const index = text.indexOf(source)
    if (index >= 0) return { start: index, end: index + source.length, missing: false }
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
        end: range.end,
        missing: !!range.missing
      }
    })
    .filter(Boolean)

  const sorted = rawHighlights
    .sort((a, b) => (a.start - b.start) || (a.end - b.end) || (a.index - b.index))

  const grouped = []
  for (const h of sorted) {
    const last = grouped[grouped.length - 1]
    if (!last) {
      grouped.push({ start: h.start, end: h.end, cards: [h], missing: h.missing })
      continue
    }

    if (h.start === last.start && h.end === last.end) {
      last.cards.push(h)
      last.missing = last.missing || h.missing
      continue
    }

    if (h.start < last.end && !h.missing) {
      continue
    }

    grouped.push({ start: h.start, end: h.end, cards: [h], missing: h.missing })
  }

  return grouped
}

const renderBadges = (cardsInRange) => {
  return cardsInRange
    .map((card, idx) => `<span class="hl-mark" data-card-id="${card.id}" style="right:${-7 - idx * 14}px">${card.index}</span>`)
    .join('')
}

const getHighlightedHtml = (field) => {
  const text = getReportTextByField(field)
  if (!text) return '无'

  const highlights = buildHighlights(field)
  if (!highlights.length) return escapeHtml(text)

  let cursor = 0
  const parts = []
  for (const h of highlights) {
    const safeStart = Math.max(0, Math.min(text.length, h.start))
    const safeEnd = Math.max(safeStart, Math.min(text.length, h.end))

    if (safeStart >= cursor) {
      parts.push(escapeHtml(text.slice(cursor, safeStart)))
    }

    const primaryCard = h.cards[0]
    const badge = renderBadges(h.cards)

    if (h.missing || safeStart === safeEnd) {
      const missingText = primaryCard.source || '缺失文本'
      const replacement = `<span class="hl-chip missing" data-card-id="${primaryCard.id}" title="${escapeHtml(primaryCard.alert_message || '')}">[缺失: ${escapeHtml(missingText)}]${badge}</span>`
      parts.push(replacement)
      cursor = safeStart
      continue
    }

    const sourceText = text.slice(safeStart, safeEnd)
    const action = normalizeAction(primaryCard.action)
    const baseClass = h.cards.some((card) => card.kind === 'manual') ? 'hl-chip manual' : 'hl-chip pre'
    const actionClass = action === 'delete' ? 'hl-delete' : action === 'prompt' ? 'hl-prompt' : 'hl-replace'
    const promptIcon = action === 'prompt' ? '<span class="hl-prompt-icon">!</span>' : ''
    const replacement = `<span class="${baseClass} ${actionClass}" data-card-id="${primaryCard.id}" title="${escapeHtml(primaryCard.alert_message || '')}">${escapeHtml(sourceText)}${promptIcon}${badge}</span>`
    parts.push(replacement)
    cursor = safeEnd
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
    suggestion: card.action === 'replace' ? (card.target || '') : '',
    anchor: {
      content_type: normalizeContentType(card.content_type),
      source_in_start: card.source_in_start,
      source_in_end: card.source_in_end,
      alert_type: card.alert_type,
      source: card.source,
      target: card.target,
      kind: card.kind,
      state: card.state,
      action: card.action
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
        alert_type: String(item.alert_type ?? '2'),
        alert_message: item.alert_message || item.alert_msg || '',
        error_type: item.err_type || 'typos',
        severity: riskByErrorType(item.err_type || 'typos'),
        source_in_start: item.source_in_start,
        source_in_end: item.source_in_end,
        action: 'replace'
      }
      card.action = inferActionByCard(card)
      if (card.action !== 'replace') {
        card.target = ''
      }
      syncActionToAlertType(card)

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

  return annotation.error_items.map((item, idx) => {
    const card = {
      id: `manual-${report.id}-${idx}`,
      kind: 'manual',
      state: 'saved',
      content_type: item.anchor?.content_type || item.location || 'description',
      source: item.evidence_text || item.anchor?.source || '',
      target: item.suggestion || item.anchor?.target || '',
      alert_type: String(item.anchor?.alert_type ?? '2'),
      alert_message: item.description || '',
      error_type: item.error_type || 'typos',
      severity: item.severity || riskByErrorType(item.error_type || 'typos'),
      source_in_start: item.anchor?.source_in_start,
      source_in_end: item.anchor?.source_in_end,
      action: normalizeAction(item.anchor?.action)
    }

    if (!['replace', 'delete', 'prompt'].includes(card.action)) {
      card.action = inferActionByCard(card)
    }
    syncActionToAlertType(card)
    return card
  })
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

  await nextTick()
  doctorTableRef.value?.setCurrentRow(report)
}

const editCard = (card) => {
  card._backup = { ...card }
  card.state = 'editing'
  selectedCardId.value = card.id
}

const saveCard = async (card) => {
  applyDefaultSeverity(card)
  const ok = await chooseActionOnConfirm(card)
  if (!ok) return

  if (['delete', 'prompt'].includes(card.action) && !String(card.alert_message || '').trim()) {
    ElMessage.warning('删除内容并提示/仅作提示时，建议说明不能为空')
    return
  }

  card.state = 'saved'
  card._backup = null
  ElMessage.success('卡片已保存')
}

const cancelEdit = (card) => {
  if (card._backup) {
    Object.assign(card, card._backup)
  }
  card._backup = null
}

const removeManualCard = (card) => {
  cards.value = cards.value.filter((item) => item.id !== card.id)
}

const confirmPreCard = async (card) => {
  applyDefaultSeverity(card)
  const ok = await chooseActionOnConfirm(card)
  if (!ok) return
  card.state = 'confirmed'
  card._backup = null
  ElMessage.success('已确认预标注处理方式')
}

const createManualCardFromSelection = () => {
  if (!currentReport.value) {
    ElMessage.warning('请先选择一条报告')
    return
  }

  const selection = window.getSelection()
  const selectedTextRaw = selection?.toString() || ''
  if (!selectedTextRaw.trim()) {
    ElMessage.warning('请先在中间报告中选中要标注的文本')
    return
  }
  const selectedText = selectedTextRaw

  const anchorEl = selection.anchorNode?.parentElement
  const fieldBlock = anchorEl?.closest('[data-field]')
  const field = fieldBlock?.dataset?.field || 'description'
  const contentEl = fieldBlock?.querySelector('.section-content') || null
  const range = selection.rangeCount > 0 ? selection.getRangeAt(0) : null

  const shouldSkipNode = (textNode) => {
    const parent = textNode?.parentElement
    if (!parent) return true
    return !!parent.closest('.hl-mark, .hl-prompt-icon')
  }

  const computeOffsetByTextNode = (rootEl, targetNode, targetOffset) => {
    if (!rootEl || !targetNode || targetNode.nodeType !== Node.TEXT_NODE) return null
    const walker = document.createTreeWalker(rootEl, NodeFilter.SHOW_TEXT)
    let total = 0
    while (walker.nextNode()) {
      const node = walker.currentNode
      if (shouldSkipNode(node)) continue
      if (node === targetNode) {
        return total + Math.min(targetOffset, node.textContent?.length || 0)
      }
      total += node.textContent?.length || 0
    }
    return null
  }

  let sourceInStart = null
  let sourceInEnd = null
  if (range && contentEl && contentEl.contains(range.startContainer) && contentEl.contains(range.endContainer)) {
    const startOffset = computeOffsetByTextNode(contentEl, range.startContainer, range.startOffset)
    const endOffset = computeOffsetByTextNode(contentEl, range.endContainer, range.endOffset)
    if (Number.isInteger(startOffset) && Number.isInteger(endOffset) && endOffset > startOffset) {
      sourceInStart = startOffset
      sourceInEnd = endOffset
    }
  }

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
    source_in_start: sourceInStart,
    source_in_end: sourceInEnd,
    action: 'replace'
  }

  cards.value.push(newCard)
  selectedCardId.value = newCard.id
}

const saveDraft = async () => {
  if (!currentReport.value || isReportAnnotated.value) return
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
  if (!currentReport.value || isReportAnnotated.value) return
  submitting.value = true
  try {
    await api.submitAnnotation(currentReport.value.id, buildPayload())
    ElMessage.success('标注完成')
    await loadReports()
    const latest = reportList.value.find((item) => item.id === currentReport.value?.id)
    if (latest) {
      await openReport(latest)
    }
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    submitting.value = false
  }
}

const cancelSubmittedAnnotation = async () => {
  if (!currentReport.value || !isReportAnnotated.value) return
  try {
    await ElMessageBox.confirm(
      '取消后将清空当前报告已提交标注，并回到待标注状态，是否继续？',
      '取消标注确认',
      {
        confirmButtonText: '确认取消',
        cancelButtonText: '返回',
        type: 'warning'
      }
    )
    await api.cancelAnnotation(currentReport.value.id)
    ElMessage.success('已取消，您可以重新标注')
    await openReport(currentReport.value)
    await loadReports()
  } catch (_e) {
    // ignore
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
    const storedColumns = localStorage.getItem(TASK_COLUMNS_STORAGE_KEY)
    if (storedColumns) {
      const parsed = JSON.parse(storedColumns)
      const allowed = new Set(doctorTableColumns.map((item) => item.key))
      const clean = Array.isArray(parsed) ? parsed.filter((key) => allowed.has(key)) : []
      if (clean.length) visibleColumnKeys.value = clean
    }

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
  grid-template-columns: 360px 1fr 380px;
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
  align-items: center;
  margin-bottom: 8px;
  color: #374151;
  font-size: 12px;
}

.column-selector {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.column-selector-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: #6b7280;
  font-size: 12px;
}

.table-frame {
  flex: 1;
  min-height: 0;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  overflow: hidden;
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

.section-content :deep(.hl-chip.hl-delete) {
  text-decoration: line-through;
  text-decoration-thickness: 2px;
  background: #fee2e2;
  color: #991b1b;
}

.section-content :deep(.hl-chip.hl-prompt) {
  background: #fee2e2;
  color: #991b1b;
  border: 1px dashed #ef4444;
}

.section-content :deep(.hl-chip.missing) {
  background: #fff7ed;
  color: #b45309;
  border: 1px dashed #f59e0b;
}

.section-content :deep(.hl-prompt-icon) {
  display: inline-block;
  width: 12px;
  height: 12px;
  line-height: 12px;
  border-radius: 999px;
  text-align: center;
  margin-left: 3px;
  font-size: 10px;
  font-weight: 700;
  color: #fff;
  background: #f97316;
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
  cursor: default;
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

.severity-group {
  width: 100%;
  margin-bottom: 8px;
}

.severity-group :deep(.el-button) {
  width: 33.33%;
}

.card-actions {
  margin-top: 8px;
  display: flex;
  gap: 8px;
}

@media (max-width: 1280px) {
  .doctor-workbench {
    grid-template-columns: 1fr;
    height: auto;
  }

  .left-panel,
  .middle-panel,
  .right-panel {
    min-height: 320px;
  }
}
</style>
