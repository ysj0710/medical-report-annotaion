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

      <div class="scope-row" v-if="!props.isAdminMode">
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
          <el-checkbox v-model="autoGoNextAfterSubmit" class="auto-next-toggle">完成之后自动进入下一个</el-checkbox>
          <el-button @click="goPrevReport">上一个</el-button>
          <el-button @click="goNextReport">下一个</el-button>
          <el-button type="primary" @click="createManualCardFromSelection" :disabled="isReportAnnotated">标注选中文本</el-button>
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
      <div class="cards" ref="cardsContainerRef">
        <el-empty v-if="cards.length === 0" description="暂无纠错卡片" />

        <el-card
          v-for="(card, idx) in cards"
          :key="card.id"
          :data-card-id="card.id"
          :class="['error-card', { selected: selectedCardId === card.id }]"
          shadow="hover"
          @click="handleCardClick(card, $event)"
        >
          <template #header>
            <div class="card-head">
              <div>
                <el-tag size="small" :type="card.kind === 'pre' ? 'warning' : 'primary'">
                  {{ card.kind === 'pre' ? '预标注' : '手动标注' }}
                </el-tag>
                <sup class="card-index">{{ idx + 1 }}</sup>
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
              <div class="level-title">错误级别</div>
              <el-button-group class="severity-group">
                <el-button :type="card.severity === 'low' ? 'success' : 'default'" @click="card.severity = 'low'">低</el-button>
                <el-button :type="card.severity === 'medium' ? 'warning' : 'default'" @click="card.severity = 'medium'">中</el-button>
                <el-button :type="card.severity === 'high' ? 'danger' : 'default'" @click="card.severity = 'high'">高</el-button>
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
                placeholder="建议说明"
              />
            </div>

            <div v-else>
              <div class="row"><span class="label">错误类型：</span>{{ errorTypeText(card.error_type) }}</div>
              <div class="row"><span class="label">错误级别：</span>{{ severityText(card.severity) }}</div>
              <div class="row"><span class="label">建议说明：</span>{{ getCardSuggestionText(card) }}</div>
            </div>
          </div>

          <div class="card-actions">
            <template v-if="card.kind === 'pre'">
              <el-button v-if="card.state === 'pending'" size="small" type="success" @click.stop="confirmPreCard(card)" :disabled="isReportAnnotated">确认</el-button>
              <el-button v-if="card.state === 'pending'" size="small" @click.stop="editCard(card)" :disabled="isReportAnnotated">修改</el-button>
              <el-button v-if="card.state === 'saved'" size="small" @click.stop="editCard(card)" :disabled="isReportAnnotated">修改</el-button>
              <el-button v-if="card.state === 'editing'" size="small" type="primary" @click.stop="saveCard(card)" :disabled="isReportAnnotated">保存</el-button>
              <el-button v-if="card.state === 'editing'" size="small" @click.stop="cancelEdit(card)">取消</el-button>
            </template>

            <template v-else>
              <el-button v-if="card.state !== 'editing'" size="small" @click.stop="editCard(card)" :disabled="isReportAnnotated">修改</el-button>
              <el-button v-if="card.state === 'editing'" size="small" type="primary" @click.stop="saveCard(card)" :disabled="isReportAnnotated">保存</el-button>
              <el-button v-if="card.state === 'editing'" size="small" @click.stop="cancelEdit(card)">取消</el-button>
            </template>
            <el-button
              size="small"
              type="danger"
              plain
              class="revoke-btn"
              @click.stop="revokeCard(card)"
              :disabled="isReportAnnotated"
            >
              撤销
            </el-button>
          </div>
        </el-card>
      </div>
    </aside>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '../api'

const props = defineProps({
  isAdminMode: { type: Boolean, default: false },
  initialReportId: { type: Number, default: null }
})

const TASK_COLUMNS_STORAGE_KEY = 'doctor_task_visible_columns_v1'
const DISMISSED_PRE_STORAGE_KEY = 'doctor_dismissed_pre_cards_v1'

const activeFilter = ref('all')
const reportQuery = ref('')
const onlyMine = ref(true)
const currentUser = ref(null)

const doctorTableRef = ref(null)
const cardsContainerRef = ref(null)
const reportList = ref([])
const currentReport = ref(null)
const cards = ref([])
const selectedCardId = ref(null)

const submitting = ref(false)
const autoGoNextAfterSubmit = ref(true)
const autoSaving = ref(false)
const autoSavePending = ref(false)
const progress = ref({ done: 0, total: 0 })
const dismissedPreCardKeysByReport = new Map()
let highlightFocusTimer = null

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
const currentReportIndex = computed(() => {
  if (!currentReport.value) return -1
  return reportList.value.findIndex((item) => item.id === currentReport.value.id)
})

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

const normalizeAlertType = (value) => {
  const text = String(value ?? '').trim()
  const matched = text.match(/^(-?\d+)\.0+$/)
  if (matched) {
    return matched[1]
  }
  return text
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
  return 'prompt'
}

const normalizeInputText = (value) => String(value ?? '').trim()

const buildReplaceSuggestionText = (source, target) => {
  const sourceText = normalizeInputText(source)
  const targetText = normalizeInputText(target)
  if (!sourceText || !targetText) return ''
  return `建议“${sourceText}”替换为“${targetText}”`
}

const buildActionSuggestionText = (card) => {
  const sourceText = normalizeInputText(card.source)
  const action = normalizeAction(card.action || inferActionByCard(card))
  if (action === 'replace') return buildReplaceSuggestionText(sourceText, card.target)
  if (action === 'delete' && sourceText) return `建议删除“${sourceText}”`
  if (action === 'prompt' && sourceText) return `请确认“${sourceText}”是否准确`
  return ''
}

const getCardSuggestionText = (card) => {
  const messageText = normalizeInputText(card.alert_message)
  if (messageText) return messageText
  const autoText = buildReplaceSuggestionText(card.source, card.target)
  return autoText || '-'
}

const inferActionByCard = (card) => {
  const alertType = normalizeAlertType(card.alert_type)
  const source = String(card.source || '').trim()
  const target = String(card.target || '').trim()
  const messageRaw = String(card.alert_message || '').trim()
  const promptHint = /不匹配|不符|请确认|需确认|建议核对|核对|矛盾|不一致|不相符|描述不符|与.+不符/
  if (
    /仅作提示|仅做提示/.test(messageRaw) ||
    (
      ['typo_modality', 'examitems'].includes(String(card.error_type || '')) &&
      promptHint.test(messageRaw)
    )
  ) return 'prompt'
  if (
    card.error_type === 'typo_modality' ||
    /不匹配|不符|请确认|需确认|建议核对|核对/.test(messageRaw)
  ) return 'prompt'
  if (alertType === '0') return 'prompt'
  if (target && target !== source) return 'replace'
  if (alertType === '2') return 'replace'
  if (/删除|删去|去掉|移除|多余|不应存在|应删除/.test(`${source}${messageRaw}`)) return 'delete'
  if (alertType === '1') return 'delete'
  if (/不匹配|提示|注意|建议|复查|随访|核对|检查类型/.test(messageRaw)) return 'prompt'
  if (card.error_type === 'organectomys') return 'delete'
  return 'prompt'
}

const syncActionToAlertType = (card) => {
  card.action = normalizeAction(card.action || inferActionByCard(card))
  const map = { replace: '2', delete: '1', prompt: '0' }
  card.alert_type = map[card.action]
}

const isEditing = (card) => card.state === 'editing'

const getSafeSelectorValue = (value) => {
  const text = String(value ?? '')
  if (typeof CSS !== 'undefined' && typeof CSS.escape === 'function') {
    return CSS.escape(text)
  }
  return text.replace(/["\\]/g, '\\$&')
}

const scrollToCard = async (cardId, behavior = 'smooth') => {
  await nextTick()
  const container = cardsContainerRef.value
  if (!container || !cardId) return
  const safeId = getSafeSelectorValue(cardId)
  const cardEl = container.querySelector(`.error-card[data-card-id="${safeId}"]`)
  cardEl?.scrollIntoView({ behavior, block: 'nearest' })
}

const clearHighlightFocus = () => {
  document.querySelectorAll('.section-content .hl-chip.hl-focus').forEach((el) => {
    el.classList.remove('hl-focus')
  })
  if (highlightFocusTimer) {
    clearTimeout(highlightFocusTimer)
    highlightFocusTimer = null
  }
}

const getHighlightElementByCardId = (cardId) => {
  const safeId = getSafeSelectorValue(cardId)
  const chip = document.querySelector(`.section-content .hl-chip[data-card-id="${safeId}"]`)
  if (chip) return chip
  const mark = document.querySelector(`.section-content .hl-mark[data-card-id="${safeId}"]`)
  return mark?.closest('.hl-chip') || mark || null
}

const focusCardHighlight = async (card, options = {}) => {
  if (!card?.id) return
  const { scrollToText = true, scrollToCardList = false } = options
  selectedCardId.value = card.id
  if (scrollToCardList) {
    await scrollToCard(card.id)
  }
  await nextTick()
  const target = getHighlightElementByCardId(card.id)
  if (!target) return
  clearHighlightFocus()
  if (scrollToText) {
    target.scrollIntoView({ behavior: 'smooth', block: 'center', inline: 'nearest' })
  }
  target.classList.add('hl-focus')
  highlightFocusTimer = window.setTimeout(() => {
    target.classList.remove('hl-focus')
    highlightFocusTimer = null
  }, 1500)
}

const handleCardClick = async (card, event) => {
  const target = event?.target
  if (target?.closest('.card-actions, .el-input, .el-textarea, .el-select, .el-button')) {
    return
  }
  await focusCardHighlight(card, { scrollToText: true, scrollToCardList: false })
}

const ensureDismissedSet = (reportId) => {
  if (!dismissedPreCardKeysByReport.has(reportId)) {
    dismissedPreCardKeysByReport.set(reportId, new Set())
  }
  return dismissedPreCardKeysByReport.get(reportId)
}

const persistDismissedPreCardKeys = () => {
  const payload = {}
  dismissedPreCardKeysByReport.forEach((set, reportId) => {
    if (set.size > 0) {
      payload[String(reportId)] = Array.from(set)
    }
  })
  localStorage.setItem(DISMISSED_PRE_STORAGE_KEY, JSON.stringify(payload))
}

const restoreDismissedPreCardKeys = () => {
  const raw = localStorage.getItem(DISMISSED_PRE_STORAGE_KEY)
  if (!raw) return
  try {
    const parsed = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object') return
    Object.entries(parsed).forEach(([reportId, keys]) => {
      if (!Array.isArray(keys) || !keys.length) return
      const numericReportId = Number(reportId)
      if (!Number.isFinite(numericReportId)) return
      dismissedPreCardKeysByReport.set(numericReportId, new Set(keys.map((item) => String(item))))
    })
  } catch (_e) {
    localStorage.removeItem(DISMISSED_PRE_STORAGE_KEY)
  }
}

const markPreCardDismissed = (reportId, card) => {
  if (!reportId || !card) return
  ensureDismissedSet(reportId).add(buildCardAnchorKey(card))
  persistDismissedPreCardKeys()
}

const unmarkPreCardDismissed = (reportId, card) => {
  if (!reportId || !card) return
  const set = dismissedPreCardKeysByReport.get(reportId)
  if (!set) return
  set.delete(buildCardAnchorKey(card))
  if (set.size === 0) {
    dismissedPreCardKeysByReport.delete(reportId)
  }
  persistDismissedPreCardKeys()
}

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
    const promptIcon = action === 'prompt' ? '<span class="hl-prompt-triangle">!</span>' : ''
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
    scrollToCard(mark.dataset.cardId)
    return
  }
  const chip = event.target.closest('.hl-chip')
  if (!chip) return
  const cardId = chip.dataset.cardId
  if (!cardId) return
  selectedCardId.value = cardId
  scrollToCard(cardId)
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
      origin_kind: card.origin_kind,
      state: card.state,
      action: card.action
    }
  }
}

const buildPayload = () => {
  const validCards = cards.value.filter((card) => {
    if (card.kind === 'pre') return card.state === 'saved'
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
  const params = {
    tab: activeFilter.value,
    page: 1,
    page_size: 1000,
    only_mine: props.isAdminMode ? false : onlyMine.value
  }
  if (reportQuery.value) params.q = reportQuery.value

  const res = await api.getDoctorReports(params)
  reportList.value = res.items

  await loadProgress()

  if (!currentReport.value && reportList.value.length > 0) {
    const preferred = props.initialReportId
      ? reportList.value.find((item) => item.id === props.initialReportId)
      : null
    await openReport(preferred || reportList.value[0])
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
        origin_kind: 'pre',
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
    const anchorKind = item.anchor?.kind
    const anchorState = item.anchor?.state
    const isPendingPre = anchorKind === 'pre' && anchorState === 'pending'
    const card = {
      id: `manual-${report.id}-${idx}`,
      kind: isPendingPre ? 'pre' : 'manual',
      origin_kind: item.anchor?.origin_kind || (anchorKind === 'pre' ? 'pre' : 'manual'),
      state: isPendingPre ? 'pending' : 'saved',
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

const buildCardAnchorKey = (card) => {
  return [
    normalizeContentType(card.content_type),
    String(card.source || '').trim(),
    String(card.source_in_start ?? ''),
    String(card.source_in_end ?? '')
  ].join('||')
}

const openReport = async (report) => {
  const detail = await api.getDoctorReport(report.id)
  currentReport.value = detail

  const preCards = buildPreCards(detail)
  const manualCards = buildManualCardsFromAnnotation(detail)
  const dismissedKeys = dismissedPreCardKeysByReport.get(detail.id) || new Set()
  const visiblePreCards = preCards.filter((card) => !dismissedKeys.has(buildCardAnchorKey(card)))
  const savedAnchorKeys = new Set(manualCards.map((card) => buildCardAnchorKey(card)))
  const remainingPreCards = visiblePreCards.filter((card) => !savedAnchorKeys.has(buildCardAnchorKey(card)))
  cards.value = dedupeCards([...manualCards, ...remainingPreCards])
  selectedCardId.value = cards.value[0]?.id || null

  await nextTick()
  doctorTableRef.value?.setCurrentRow(report)
}

const updateCurrentReportStatusLocally = (status) => {
  if (!currentReport.value) return
  currentReport.value.status = status
  const row = reportList.value.find((item) => item.id === currentReport.value.id)
  if (row) row.status = status
}

const autoSaveAfterInteraction = async () => {
  if (!currentReport.value || isReportAnnotated.value) return
  if (autoSaving.value) {
    autoSavePending.value = true
    return
  }
  autoSaving.value = true
  try {
    await api.saveDraft(currentReport.value.id, buildPayload())
    if (currentReport.value.status === 'ASSIGNED') {
      updateCurrentReportStatusLocally('IN_PROGRESS')
    }
    await loadProgress()
  } catch (e) {
    ElMessage.error(e.message || '自动暂存失败')
  } finally {
    autoSaving.value = false
    if (autoSavePending.value) {
      autoSavePending.value = false
      await autoSaveAfterInteraction()
    }
  }
}

const editCard = (card) => {
  card._backup = { ...card }
  card.state = 'editing'
  selectedCardId.value = card.id
}

const prepareCardForSave = async (card, options = {}) => {
  const { showValidationDialog = true, allowAutoSuggestionWhenEmpty = false } = options

  card.target = normalizeInputText(card.target)
  card.alert_message = normalizeInputText(card.alert_message)
  applyDefaultSeverity(card)

  const hasTarget = !!card.target
  const hasAlertMessage = !!card.alert_message

  if (!hasTarget && !hasAlertMessage) {
    if (allowAutoSuggestionWhenEmpty) {
      card.action = inferActionByCard(card)
      card.alert_message = buildActionSuggestionText(card) || '请复核该处表述是否准确'
    } else {
      if (showValidationDialog) {
        try {
          await ElMessageBox.alert(
            '非替换操作请填写建议说明，或填写替换后内容后再保存。',
            '保存前校验',
            { confirmButtonText: '我知道了', type: 'warning' }
          )
        } catch (_e) {
          // ignore close action
        }
      }
      return false
    }
  }

  if (hasTarget) {
    card.action = 'replace'
    if (!card.alert_message) {
      card.alert_message = buildReplaceSuggestionText(card.source, card.target)
    }
  } else {
    card.action = inferActionByCard(card)
  }

  syncActionToAlertType(card)

  if (card.action !== 'replace') {
    card.target = ''
    if (!card.alert_message) {
      card.alert_message = buildActionSuggestionText(card)
    }
  }

  return true
}

const saveCard = async (card) => {
  const canSave = await prepareCardForSave(card)
  if (!canSave) return
  if (card.kind === 'pre') {
    card.kind = 'manual'
    card.origin_kind = 'pre'
    unmarkPreCardDismissed(currentReport.value?.id, card)
  }
  card.state = 'saved'
  card._backup = null
  await autoSaveAfterInteraction()
}

const cancelEdit = (card) => {
  if (card._backup) {
    Object.assign(card, card._backup)
  }
  card._backup = null
}

const revokeCard = async (card) => {
  if (!currentReport.value) return
  try {
    await ElMessageBox.confirm(
      '撤销后将删除当前纠错卡片，是否继续？',
      '撤销确认',
      { confirmButtonText: '确认撤销', cancelButtonText: '返回', type: 'warning' }
    )
  } catch (_e) {
    return
  }

  if (card.kind === 'pre' || card.origin_kind === 'pre') {
    markPreCardDismissed(currentReport.value.id, card)
  }
  cards.value = cards.value.filter((item) => item.id !== card.id)
  if (selectedCardId.value === card.id) {
    selectedCardId.value = cards.value[0]?.id || null
  }
  await autoSaveAfterInteraction()
}

const confirmPreCard = async (card) => {
  const canSave = await prepareCardForSave(card, {
    showValidationDialog: false,
    allowAutoSuggestionWhenEmpty: true
  })
  if (!canSave) return
  card.kind = 'manual'
  card.origin_kind = 'pre'
  unmarkPreCardDismissed(currentReport.value?.id, card)
  card.state = 'saved'
  card._backup = null
  await autoSaveAfterInteraction()
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
    origin_kind: 'manual',
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
  scrollToCard(newCard.id)
}

const remindUnsubmitted = async (offset = 1) => {
  if (!currentReport.value || isReportAnnotated.value) return 'pass'
  const directionText = offset < 0 ? '上一份' : '下一份'
  try {
    await ElMessageBox.confirm(
      `该报告已暂存，暂未确认标注完成。你可以立即确认完成标注，或继续查看${directionText}报告。`,
      '切换提示',
      {
        confirmButtonText: '立即确认完成标注',
        cancelButtonText: `仍要查看${directionText}报告`,
        distinguishCancelAndClose: true,
        closeOnClickModal: false,
        closeOnPressEscape: true,
        type: 'warning'
      }
    )
    return 'submit'
  } catch (e) {
    if (e === 'cancel') return 'pass'
    return 'abort'
  }
}

const switchReportByOffset = async (offset) => {
  if (!reportList.value.length) return
  const intent = await remindUnsubmitted(offset)
  if (intent === 'abort') return
  const previousReportId = currentReport.value?.id
  const currentIdx = currentReportIndex.value
  const total = reportList.value.length
  const baseIdx = currentIdx < 0 ? 0 : currentIdx
  const targetIdx = (baseIdx + offset + total) % total
  const fallbackTargetId = reportList.value[targetIdx]?.id

  if (intent === 'submit' && currentReport.value && !isReportAnnotated.value) {
    const canSubmit = await ensurePreCardsReadyBeforeSubmit()
    if (!canSubmit) return
    try {
      await api.submitAnnotation(currentReport.value.id, buildPayload())
      updateCurrentReportStatusLocally('SUBMITTED')
      await loadReports()
    } catch (e) {
      ElMessage.error(e.message || '完成标注失败，未切换报告')
      return
    }
  }

  let nextReport = null
  if (intent === 'submit' && previousReportId) {
    const newIndex = reportList.value.findIndex((item) => item.id === previousReportId)
    if (newIndex >= 0) {
      const adjustedIdx = (newIndex + offset + reportList.value.length) % reportList.value.length
      nextReport = reportList.value[adjustedIdx]
    }
  }
  if (!nextReport && fallbackTargetId) {
    nextReport = reportList.value.find((item) => item.id === fallbackTargetId) || null
  }
  if (!nextReport && reportList.value.length) {
    nextReport = reportList.value[0]
  }
  if (nextReport) {
    await openReport(nextReport)
  }
}

const goPrevReport = async () => switchReportByOffset(-1)
const goNextReport = async () => switchReportByOffset(1)

const clearCurrentReport = () => {
  currentReport.value = null
  cards.value = []
  selectedCardId.value = null
  doctorTableRef.value?.setCurrentRow(null)
}

const resolveReportAfterSubmit = (previousReportId, previousIndex, offset = 0) => {
  if (!reportList.value.length) return null

  const sameIdx = reportList.value.findIndex((item) => item.id === previousReportId)
  if (sameIdx >= 0) {
    const targetIdx = (sameIdx + offset + reportList.value.length) % reportList.value.length
    return reportList.value[targetIdx] || null
  }

  const normalizedIdx = Math.min(Math.max(previousIndex, 0), reportList.value.length - 1)
  return reportList.value[normalizedIdx] || null
}

const autoConfirmPendingPreCards = async () => {
  const pendingCards = cards.value.filter((card) => card.kind === 'pre' && card.state === 'pending')
  if (!pendingCards.length) return

  for (const card of pendingCards) {
    await prepareCardForSave(card, {
      showValidationDialog: false,
      allowAutoSuggestionWhenEmpty: true
    })
    card.kind = 'manual'
    card.origin_kind = 'pre'
    unmarkPreCardDismissed(currentReport.value?.id, card)
    card.state = 'saved'
    card._backup = null
  }
}

const ensurePreCardsReadyBeforeSubmit = async () => {
  const pendingPreCount = cards.value.filter((card) => card.kind === 'pre' && card.state === 'pending').length
  if (pendingPreCount <= 0) return true

  try {
    await ElMessageBox.confirm(
      '存在未确认的预标注，是否自动完成确认，并执行完成标注操作？',
      '完成前确认',
      {
        confirmButtonText: '是',
        cancelButtonText: '否',
        type: 'warning'
      }
    )
    await autoConfirmPendingPreCards()
    return true
  } catch (_e) {
    return false
  }
}

const submitReport = async () => {
  if (!currentReport.value || isReportAnnotated.value) return
  const canSubmit = await ensurePreCardsReadyBeforeSubmit()
  if (!canSubmit) return

  const previousReportId = currentReport.value.id
  const previousIndex = currentReportIndex.value
  submitting.value = true
  try {
    await api.submitAnnotation(currentReport.value.id, buildPayload())
    ElMessage.success('标注完成')
    await loadReports()

    const offset = autoGoNextAfterSubmit.value ? 1 : 0
    const targetReport = resolveReportAfterSubmit(previousReportId, previousIndex, offset)
    if (targetReport) {
      await openReport(targetReport)
    } else {
      clearCurrentReport()
    }
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    submitting.value = false
  }
}

const cancelSubmittedAnnotation = async () => {
  if (!currentReport.value || !isReportAnnotated.value) return
  const reportId = currentReport.value.id
  try {
    await ElMessageBox.confirm(
      '取消后，当前报告将回到待标注状态，是否继续？',
      '取消标注确认',
      {
        confirmButtonText: '确认取消',
        cancelButtonText: '返回',
        type: 'warning'
      }
    )
    await api.cancelAnnotation(reportId)
    ElMessage.success('已取消标注，当前报告已恢复为可编辑状态')
    await loadReports()
    const refreshed = reportList.value.find((item) => item.id === reportId)
    if (refreshed) {
      await openReport(refreshed)
    } else {
      clearCurrentReport()
    }
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

onBeforeUnmount(() => {
  clearHighlightFocus()
})

onMounted(async () => {
  try {
    const storedColumns = localStorage.getItem(TASK_COLUMNS_STORAGE_KEY)
    if (storedColumns) {
      const parsed = JSON.parse(storedColumns)
      const allowed = new Set(doctorTableColumns.map((item) => item.key))
      const clean = Array.isArray(parsed) ? parsed.filter((key) => allowed.has(key)) : []
      if (clean.length) visibleColumnKeys.value = clean
    }
    restoreDismissedPreCardKeys()

    currentUser.value = await api.getMe()
    if (props.isAdminMode) {
      onlyMine.value = false
    }
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
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 8px;
}

.auto-next-toggle {
  margin-right: 2px;
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
  color: #b91c1c;
  border: 1px solid #ef4444;
  font-weight: 600;
}

.section-content :deep(.hl-chip.missing) {
  background: #fff7ed;
  color: #b45309;
  border: 1px dashed #f59e0b;
}

.section-content :deep(.hl-chip.hl-focus) {
  box-shadow: 0 0 0 3px rgba(245, 158, 11, 0.45);
  animation: chip-focus-pulse 0.8s ease-in-out 2;
}

.section-content :deep(.hl-prompt-triangle) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 13px;
  height: 12px;
  margin-left: 4px;
  font-size: 9px;
  line-height: 1;
  font-weight: 800;
  color: #fff;
  background: #dc2626;
  clip-path: polygon(50% 0%, 0% 100%, 100% 100%);
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

@keyframes chip-focus-pulse {
  0% { transform: scale(1); }
  50% { transform: scale(1.05); }
  100% { transform: scale(1); }
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
  cursor: pointer;
}

.error-card.selected {
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.12);
}

.card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-index {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 14px;
  height: 14px;
  line-height: 14px;
  margin-left: 6px;
  border-radius: 999px;
  text-align: center;
  font-size: 10px;
  color: #fff;
  background: #ef4444;
  vertical-align: super;
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

.level-title {
  margin-bottom: 6px;
  font-size: 12px;
  color: #6b7280;
}

.severity-group :deep(.el-button) {
  width: 33.33%;
}

.card-actions {
  margin-top: 8px;
  display: flex;
  gap: 8px;
}

.revoke-btn {
  margin-left: auto;
}

</style>
