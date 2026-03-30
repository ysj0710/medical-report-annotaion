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
          <span>任务列表（当前 {{ reportList.length }} / 共 {{ reportTotal }}）</span>
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
          <div class="report-meta">
            检查号：{{ currentReport?.ris_no || '-' }}
            <template v-if="showPatientSexInMeta"> 性别：{{ currentReport?.patient_sex || '未知' }}</template>
          </div>
        </div>
        <div class="middle-actions">
          <el-checkbox v-model="autoGoNextAfterSubmit" class="auto-next-toggle">完成之后自动进入下一个</el-checkbox>
          <el-button @click="goPrevReport">上一个</el-button>
          <el-button @click="goNextReport">下一个</el-button>
          <el-button type="primary" @click="createManualCardFromSelection" :disabled="isEditingLocked">标注选中文本</el-button>
          <el-button type="success" @click="submitReport" :loading="submitting" :disabled="!canSubmitCurrentReport">{{ submitButtonText }}</el-button>
          <el-button v-if="showCancelAnnotationButton" type="danger" plain @click="cancelSubmittedAnnotation">取消标注</el-button>
        </div>
      </div>

      <div class="report-sheet" v-if="currentReport">
        <div class="sheet-head">
          <h2>{{ reportHeaderTitle }}</h2>
          <div>项目：{{ currentReport.exam_item || '-' }}</div>
          <div class="sheet-meta-line">
            性别：{{ currentReport.patient_sex || '未知' }}　年龄：{{ currentReport.patient_age || '-' }}
          </div>
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
        <el-empty v-if="cards.length === 0" description="暂无纠错内容" />

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
              <el-select v-model="card.error_type" placeholder="错误类型" style="width: 100%; margin-bottom: 8px" @change="handleErrorTypeChange(card)">
                <el-option v-for="item in errorTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
              <div class="level-title">错误级别</div>
              <el-button-group class="severity-group">
                <el-button :type="card.severity === 'low' ? 'success' : 'default'" @click="card.severity = 'low'">低</el-button>
                <el-button :type="card.severity === 'medium' ? 'warning' : 'default'" @click="card.severity = 'medium'">中</el-button>
                <el-button :type="card.severity === 'high' ? 'danger' : 'default'" @click="card.severity = 'high'">高</el-button>
              </el-button-group>
              <div class="level-title">处理方式</div>
              <div class="process-method-group">
                <button
                  type="button"
                  :class="['process-method-btn', { active: card.process_method === PROCESS_METHOD.replace }]"
                  @click="handleManualProcessMethodSelect(card, PROCESS_METHOD.replace)"
                >
                  替换
                </button>
                <button
                  type="button"
                  :class="['process-method-btn', { active: card.process_method === PROCESS_METHOD.prompt }]"
                  @click="handleManualProcessMethodSelect(card, PROCESS_METHOD.prompt)"
                >
                  仅提示
                </button>
                <button
                  type="button"
                  :class="['process-method-btn', { active: card.process_method === PROCESS_METHOD.delete }]"
                  @click="handleManualProcessMethodSelect(card, PROCESS_METHOD.delete)"
                >
                  删除
                </button>
              </div>
              <el-input
                v-model="card.target"
                placeholder="替换后内容（仅提示/删除可不填写）"
                :class="{
                  'replace-target-input': card.process_method === PROCESS_METHOD.replace,
                  'replace-target-input-error': !!card._targetValidationError
                }"
                style="margin-bottom: 8px"
                @input="handleReplacementInput(card)"
                @focus="handleReplacementFocus(card)"
                @blur="handleReplacementBlur(card)"
              />
              <div v-if="card._targetValidationError" class="card-inline-error">{{ card._targetValidationError }}</div>
              <el-input
                v-model="card.alert_message"
                type="textarea"
                :rows="2"
                placeholder="建议说明"
                @input="handleSuggestionInput(card)"
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
              <el-button v-if="card.state === 'pending'" size="small" type="success" @click.stop="confirmPreCard(card)" :disabled="isEditingLocked">确认</el-button>
              <el-button v-if="card.state === 'pending'" size="small" @click.stop="editCard(card)" :disabled="isEditingLocked">修改</el-button>
              <el-button v-if="card.state === 'saved'" size="small" @click.stop="editCard(card)" :disabled="isEditingLocked">修改</el-button>
              <el-button v-if="card.state === 'editing'" size="small" type="primary" @click.stop="saveCard(card)" :disabled="isEditingLocked">保存</el-button>
              <el-button v-if="card.state === 'editing'" size="small" @click.stop="cancelEdit(card)">取消</el-button>
            </template>

            <template v-else>
              <el-button v-if="card.state !== 'editing'" size="small" @click.stop="editCard(card)" :disabled="isEditingLocked">修改</el-button>
              <el-button v-if="card.state === 'editing'" size="small" type="primary" @click.stop="saveCard(card)" :disabled="isEditingLocked">保存</el-button>
              <el-button v-if="card.state === 'editing'" size="small" @click.stop="cancelEdit(card)">取消</el-button>
            </template>
            <el-button
              size="small"
              type="danger"
              plain
              class="revoke-btn"
              @click.stop="deleteCard(card)"
              :disabled="isEditingLocked"
            >
              删除
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
const DOCTOR_LIST_PAGE_SIZE = 1000

const activeFilter = ref(props.isAdminMode ? 'all' : 'unannotated')
const reportQuery = ref('')
const onlyMine = ref(true)
const currentUser = ref(null)

const doctorTableRef = ref(null)
const cardsContainerRef = ref(null)
const reportList = ref([])
const reportTotal = ref(0)
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
  typos: '文字错误',
  examitems: '检查项目不一致错误',
  typo_unit: '单位错误',
  typo_modality: '检查设备一致性错误',
  positions: '方位一致性错误',
  bodyParts: '部位不一致错误',
  typoTerms: '术语不一致',
  organectomys: '器官切除不一致错误',
  sexs: '性别不一致错误'
}

const errorTypeOptions = [
  { value: 'typos', label: '文字错误' },
  { value: 'examitems', label: '检查项目不一致错误' },
  { value: 'typo_unit', label: '单位错误' },
  { value: 'typo_modality', label: '检查设备一致性错误' },
  { value: 'positions', label: '方位一致性错误' },
  { value: 'bodyParts', label: '部位不一致错误' },
  { value: 'typoTerms', label: '术语不一致' },
  { value: 'organectomys', label: '器官切除不一致错误' },
  { value: 'sexs', label: '性别不一致错误' }
]

const reportHeaderTitle = computed(() => {
  const modality = currentReport.value?.modality || currentReport.value?.exam_item || '影像'
  return `${modality}检查报告单`
})

const progressPercent = computed(() => {
  if (!progress.value.total) return 0
  return Math.round((progress.value.done / progress.value.total) * 100)
})

const isEditingLockedStatus = (status) => ['SUBMITTED', 'DONE', 'REVIEW_ASSIGNED'].includes(status || '')
const canSubmitStatus = (status) => ['ASSIGNED', 'IN_PROGRESS', 'REVIEW_ASSIGNED', 'REVIEW_IN_PROGRESS'].includes(status || '')
const isDraftWorkflowStatus = (status) => ['ASSIGNED', 'IN_PROGRESS', 'REVIEW_IN_PROGRESS'].includes(status || '')

const isEditingLocked = computed(() => isEditingLockedStatus(currentReport.value?.status))
const canSubmitCurrentReport = computed(() => {
  if (!currentReport.value) return false
  return canSubmitStatus(currentReport.value.status)
})
const showCancelAnnotationButton = computed(() => {
  const status = currentReport.value?.status
  return status === 'SUBMITTED' || status === 'REVIEW_ASSIGNED'
})
const submitButtonText = computed(() => {
  const status = currentReport.value?.status
  if (status === 'REVIEW_ASSIGNED') return '确认无误'
  if (status === 'REVIEW_IN_PROGRESS') return '完成标注核验'
  return '完成标注'
})
const currentReportIndex = computed(() => {
  if (!currentReport.value) return -1
  return reportList.value.findIndex((item) => item.id === currentReport.value.id)
})
const showPatientSexInMeta = computed(() => {
  if (!currentReport.value) return false
  if (!normalizeInputText(currentReport.value.patient_sex)) return false
  return cards.value.some((card) => card.error_type === 'sexs')
})

const visibleColumns = computed(() => {
  const selected = new Set(visibleColumnKeys.value)
  return doctorTableColumns.filter((col) => selected.has(col.key))
})

watch(visibleColumnKeys, (val) => {
  localStorage.setItem(TASK_COLUMNS_STORAGE_KEY, JSON.stringify(val))
}, { deep: true })

const getStatusText = (status) => {
  const map = {
    ASSIGNED: '未标注',
    IN_PROGRESS: '标注中',
    SUBMITTED: '已标注',
    REVIEW_ASSIGNED: '待复核',
    REVIEW_IN_PROGRESS: '复核中',
    DONE: '已标注'
  }
  return map[status] || status
}

const getStatusType = (status) => {
  if (status === 'SUBMITTED' || status === 'DONE') return 'success'
  if (status === 'IN_PROGRESS' || status === 'REVIEW_ASSIGNED' || status === 'REVIEW_IN_PROGRESS') return 'warning'
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

const getSectionNameByCard = (card) => {
  const normalized = normalizeContentType(card?.content_type)
  if (normalized === 'impression') return '诊断意见'
  if (normalized === 'description') return '检查所见'
  const raw = normalizeInputText(card?.content_type)
  if (raw.includes('诊断意见')) return '诊断意见'
  if (raw.includes('检查所见')) return '检查所见'
  return '检查所见'
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

const normalizeImportedSeverity = (value, errorType = '') => {
  const raw = String(value ?? '').trim().toLowerCase()
  if (['low', 'l', '1', '低', '轻', '轻度'].includes(raw)) return 'low'
  if (['medium', 'med', 'm', '2', '中', '中度'].includes(raw)) return 'medium'
  if (['high', 'h', '3', '高', '重', '重度'].includes(raw)) return 'high'
  return riskByErrorType(errorType || '')
}

const severityText = (v) => {
  const map = { low: '低', medium: '中', high: '高' }
  return map[v] || v || '-'
}

const errorTypeText = (type) => ERROR_TYPE_MAP[type] || type || '-'

const PROCESS_METHOD = {
  replace: '替换',
  prompt: '仅提示',
  delete: '删除'
}

const DELETE_HINT_PATTERN = /删除|删去|去掉|移除|多余|不应存在|应删除/

const PROCESS_METHOD_BY_ERROR_TYPE = {
  typos: PROCESS_METHOD.replace,
  examitems: PROCESS_METHOD.prompt,
  typo_unit: PROCESS_METHOD.prompt,
  typo_modality: PROCESS_METHOD.prompt,
  positions: PROCESS_METHOD.prompt,
  bodyParts: PROCESS_METHOD.prompt,
  typoTerms: PROCESS_METHOD.replace,
  organectomys: PROCESS_METHOD.prompt,
  sexs: PROCESS_METHOD.prompt
}

const processMethodToAction = (method) => {
  if (method === PROCESS_METHOD.replace) return 'replace'
  if (method === PROCESS_METHOD.delete) return 'delete'
  return 'prompt'
}

const actionToProcessMethod = (action) => {
  if (action === 'replace') return PROCESS_METHOD.replace
  if (action === 'delete') return PROCESS_METHOD.delete
  return PROCESS_METHOD.prompt
}

const normalizeProcessMethod = (value) => {
  if (value === PROCESS_METHOD.replace || value === 'replace' || value === '2') return PROCESS_METHOD.replace
  if (value === PROCESS_METHOD.delete || value === 'delete' || value === '1') return PROCESS_METHOD.delete
  return PROCESS_METHOD.prompt
}

const normalizeAction = (action) => processMethodToAction(normalizeProcessMethod(action))

const normalizeInputText = (value) => String(value ?? '').trim()

const buildReplaceSuggestionText = (source, target) => {
  const sourceText = normalizeInputText(source)
  const targetText = normalizeInputText(target)
  if (!sourceText || !targetText) return ''
  return `建议“${sourceText}”替换为“${targetText}”`
}

const buildDeleteSuggestionText = (source) => {
  const sourceText = normalizeInputText(source)
  if (!sourceText) return '建议删除'
  return `建议删除"${sourceText}"`
}

const buildReplaceSuggestionTextByCard = (card, replacementText) => {
  const source = normalizeInputText(card.source)
  const replacement = normalizeInputText(replacementText)
  if (!source || !replacement) return ''
  return `建议将"${source}"替换成"${replacement}"`
}

const buildActionSuggestionText = (card) => {
  const sourceText = normalizeInputText(card.source)
  const method = normalizeProcessMethod(card.process_method || actionToProcessMethod(card.action || inferActionByCard(card)))
  const action = processMethodToAction(method)
  if (action === 'replace') return buildReplaceSuggestionByErrorType(card, card.target)
  if (action === 'delete') return buildDeleteSuggestionText(sourceText)
  if (action === 'prompt' && sourceText) return `请确认“${sourceText}”是否准确`
  return ''
}

const getCardSuggestionText = (card) => {
  const messageText = normalizeInputText(card.alert_message)
  if (messageText) return messageText
  const autoText = buildActionSuggestionText(card)
  return autoText || '-'
}

const inferActionByCard = (card) => {
  if (card.process_method) return processMethodToAction(card.process_method)
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
  if (DELETE_HINT_PATTERN.test(`${source}${messageRaw}`)) return 'delete'
  if (alertType === '1') return 'delete'
  if (/不匹配|提示|注意|建议|复查|随访|核对|检查类型/.test(messageRaw)) return 'prompt'
  return 'prompt'
}

const syncActionToAlertType = (card) => {
  card.process_method = normalizeProcessMethod(card.process_method || actionToProcessMethod(card.action || inferActionByCard(card)))
  card.action = processMethodToAction(card.process_method)
  const map = { replace: '2', delete: '1', prompt: '0' }
  card.alert_type = map[card.action]
}

const extractBodyPart = () => {
  const item = normalizeInputText(currentReport.value?.exam_item)
  if (item) return item
  const text = `${currentReport.value?.description || ''} ${currentReport.value?.impression || ''}`
  const matched = text.match(/(头颅|颅脑|颈部|胸部|腹部|盆腔|膝关节|髋关节|肩关节|腰椎|胸椎|颈椎|脊柱|肝脏|胆囊|胰腺|脾脏|肾脏)/)
  return matched?.[1] || '当前检查部位'
}

const extractPositionWord = (card) => {
  const sourceText = normalizeInputText(card.source)
  const context = `${sourceText} ${currentReport.value?.description || ''}`
  const matched = context.match(/(左侧|右侧|双侧|左|右|上|下|前|后|内侧|外侧)/)
  return matched?.[1] || ''
}

const getDefaultProcessMethodByErrorType = (errorType) => PROCESS_METHOD_BY_ERROR_TYPE[errorType] || PROCESS_METHOD.delete

const buildPromptSuggestionByErrorType = (card) => {
  const source = normalizeInputText(card.source)
  const modality = normalizeInputText(currentReport.value?.modality) || '当前设备'
  const bodyPart = extractBodyPart()
  const patientSex = normalizeInputText(currentReport.value?.patient_sex) || '未知'
  const sectionName = getSectionNameByCard(card)

  switch (card.error_type) {
    case 'examitems':
      return '检查项目矛盾/报告漏写增强'
    case 'typo_unit':
      return '单位异常请检查核对'
    case 'typo_modality':
      return `"${source}"该描述与设备类型"${modality}"不符，请确认`
    case 'positions':
      return '方位不一致'
    case 'bodyParts':
      return `"${source}"与检查部位"${bodyPart}"矛盾`
    case 'typoTerms':
      return '专业术语有误'
    case 'organectomys':
      return `${sectionName}中，描述了与患者已记录的已切除脏器相矛盾的内容`
    case 'sexs':
      return `"${source}"与性别${patientSex}矛盾`
    default:
      return ''
  }
}

const buildReplaceSuggestionByErrorType = (card, replacementText) => {
  return buildReplaceSuggestionTextByCard(card, replacementText)
}

const buildReplaceBaseSuggestionByErrorType = (card) => {
  if (card.error_type === 'typoTerms') return '专业术语有误'
  return ''
}

const buildDeleteSuggestionByErrorType = (card) => buildDeleteSuggestionText(card.source)

const buildReplaceEmptyStateSuggestion = () => '请输入替换内容'

const appendSuggestionSentence = (baseText, appendText) => {
  const base = normalizeInputText(baseText)
  const append = normalizeInputText(appendText)
  if (!append) return base
  if (!base) return append
  if (base.includes(append)) return base
  if (/[。.!?！？]$/.test(base)) return `${base} ${append}`
  return `${base}。 ${append}`
}

const buildSuggestionByMethod = (card, method, options = {}) => {
  const normalizedMethod = normalizeProcessMethod(method)
  const replacementText = normalizeInputText(options.replacementText ?? card.target)
  if (normalizedMethod === PROCESS_METHOD.delete) {
    return buildDeleteSuggestionByErrorType(card)
  }
  if (normalizedMethod === PROCESS_METHOD.prompt) {
    return buildPromptSuggestionByErrorType(card) || (normalizeInputText(card.source) ? `请确认"${normalizeInputText(card.source)}"是否准确` : '请确认该处描述')
  }
  if (replacementText) {
    return buildReplaceSuggestionByErrorType(card, replacementText)
  }
  const replaceBaseSuggestion = buildReplaceBaseSuggestionByErrorType(card)
  if (replaceBaseSuggestion) return replaceBaseSuggestion
  return buildReplaceEmptyStateSuggestion()
}

const buildSuggestionByMethodWithReplacementAppend = (card, method, options = {}) => {
  const normalizedMethod = normalizeProcessMethod(method)
  const replacementText = normalizeInputText(options.replacementText ?? card.target)
  if (normalizedMethod === PROCESS_METHOD.replace) {
    return buildSuggestionByMethod(card, normalizedMethod, { replacementText })
  }
  const baseSuggestion = buildSuggestionByMethod(card, normalizedMethod, { replacementText: '' })
  if (!replacementText) return baseSuggestion
  const replacementSuggestion = buildReplaceSuggestionByErrorType(card, replacementText)
  return appendSuggestionSentence(baseSuggestion, replacementSuggestion)
}

const ensureMethodSuggestionCache = (card) => {
  if (!card || typeof card !== 'object') return {}
  if (!card._methodSuggestionCache || typeof card._methodSuggestionCache !== 'object') {
    card._methodSuggestionCache = {}
  }
  return card._methodSuggestionCache
}

const getCachedSuggestionByMethod = (card, method) => {
  const cache = ensureMethodSuggestionCache(card)
  return normalizeInputText(cache[normalizeProcessMethod(method)])
}

const setCachedSuggestionByMethod = (card, method, suggestionText) => {
  const cache = ensureMethodSuggestionCache(card)
  const key = normalizeProcessMethod(method)
  const text = normalizeInputText(suggestionText)
  if (text) {
    cache[key] = text
  } else {
    delete cache[key]
  }
}

const normalizeOrganectomySuggestionSection = (card) => {
  if (!card || card.error_type !== 'organectomys') return
  const message = normalizeInputText(card.alert_message)
  if (!message) return
  const template = /^(检查所见|诊断意见)中，描述了与患者已记录的已切除脏器相矛盾的内容$/
  if (!template.test(message)) return
  const normalized = `${getSectionNameByCard(card)}中，描述了与患者已记录的已切除脏器相矛盾的内容`
  if (message !== normalized) {
    card.alert_message = normalized
  }
}

const buildSuggestionByMethodWithCachedBase = (card, method, options = {}) => {
  const normalizedMethod = normalizeProcessMethod(method)
  const replacementText = normalizeInputText(options.replacementText ?? card.target)
  const preservedPromptBase = getCachedSuggestionByMethod(card, PROCESS_METHOD.prompt)

  if (card?._preserveBaseSuggestion && preservedPromptBase) {
    if (normalizedMethod === PROCESS_METHOD.prompt) {
      return preservedPromptBase
    }
    if (normalizedMethod === PROCESS_METHOD.delete) {
      return appendSuggestionSentence(preservedPromptBase, buildDeleteSuggestionByErrorType(card))
    }
    if (!replacementText) {
      return preservedPromptBase
    }
    return appendSuggestionSentence(
      preservedPromptBase,
      buildReplaceSuggestionByErrorType(card, replacementText)
    )
  }

  const cachedBase = getCachedSuggestionByMethod(card, normalizedMethod)
  if (!replacementText) {
    if (cachedBase) return cachedBase
    return buildSuggestionByMethodWithReplacementAppend(card, normalizedMethod, { replacementText: '' })
  }
  if (normalizedMethod === PROCESS_METHOD.replace) {
    return buildReplaceSuggestionByErrorType(card, replacementText)
  }
  if (cachedBase) {
    return appendSuggestionSentence(cachedBase, buildReplaceSuggestionByErrorType(card, replacementText))
  }
  return buildSuggestionByMethodWithReplacementAppend(card, normalizedMethod, { replacementText })
}

const enforceSuggestionLengthLimit = (card) => {
  if (!card) return
  const text = String(card.alert_message || '')
  if (text.length <= 500) return
  card.alert_message = text.slice(0, 500)
  ElMessage.warning('建议说明最多500字符，已自动截断')
}

const extractReplacementFromSuggestion = (message) => {
  const text = normalizeInputText(message)
  if (!text) return ''
  const patterns = [
    /改成[“"]([^”"]+)[”"]/,
    /替换(?:为|成)[“"]([^”"]+)[”"]/,
    /替换成[“"]([^”"]+)[”"]/,
    /替换为[“"]([^”"]+)[”"]/
  ]
  for (const pattern of patterns) {
    const matched = text.match(pattern)
    if (matched?.[1]) return normalizeInputText(matched[1])
  }
  const quoted = text.match(/[“"]([^”"]+)[”"]/g)
  if (quoted?.length) {
    const last = quoted[quoted.length - 1]
    return normalizeInputText(last.replace(/[“”"]/g, ''))
  }
  return ''
}

const inferProcessMethodFromImportedData = (card) => {
  const message = normalizeInputText(card.alert_message)
  if (/替换/.test(message)) {
    const extracted = extractReplacementFromSuggestion(message)
    if (extracted) card.target = extracted
    return PROCESS_METHOD.replace
  }
  if (DELETE_HINT_PATTERN.test(message)) return PROCESS_METHOD.delete
  if (!message) return PROCESS_METHOD.prompt
  return PROCESS_METHOD.prompt
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
  if (target?.closest('.card-actions, .el-input, .el-textarea, .el-select, .el-button, .process-method-btn')) {
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

const applyProcessMethodInputState = (card) => {
  card.process_method = normalizeProcessMethod(card.process_method)
  syncActionToAlertType(card)
}

const applyRuleBBySuggestion = (card) => {
  const suggestion = normalizeInputText(card.alert_message)
  if (!suggestion) return
  if (DELETE_HINT_PATTERN.test(suggestion)) card.process_method = PROCESS_METHOD.delete
  if (/替换/.test(suggestion)) card.process_method = PROCESS_METHOD.replace
  syncActionToAlertType(card)
}

const resetCardByErrorType = (card) => {
  card.manual_override = false
  card._methodSuggestionCache = {}
  card.target = ''
  card.process_method = getDefaultProcessMethodByErrorType(card.error_type)
  card.alert_message = buildSuggestionByMethod(card, card.process_method, { replacementText: '' })
  setCachedSuggestionByMethod(card, card.process_method, card.alert_message)
  enforceSuggestionLengthLimit(card)
  applyProcessMethodInputState(card)
}

const handleErrorTypeChange = (card) => {
  applyDefaultSeverity(card)
  resetCardByErrorType(card)
}

const handleManualProcessMethodSelect = (card, method) => {
  const nextMethod = normalizeProcessMethod(method)
  const currentMethod = normalizeProcessMethod(card.process_method)
  if (nextMethod === currentMethod) return
  const previousSuggestion = normalizeInputText(card.alert_message)
  if (previousSuggestion) {
    setCachedSuggestionByMethod(card, currentMethod, previousSuggestion)
  }
  card.process_method = nextMethod
  card.manual_override = true
  applyProcessMethodInputState(card)
  card.alert_message = buildSuggestionByMethodWithCachedBase(card, card.process_method, {
    replacementText: card.target
  })
  if (card.process_method !== PROCESS_METHOD.replace || normalizeInputText(card.target)) {
    card._targetValidationError = ''
  }
  setCachedSuggestionByMethod(card, card.process_method, card.alert_message)
  enforceSuggestionLengthLimit(card)
}

const handleReplacementInput = (card) => {
  card.target = String(card.target || '')
  card._targetValidationError = ''
}

const handleReplacementFocus = (_card) => {
  // 保持当前处理方式不变；在 blur 阶段根据替换内容重算建议说明。
}

const handleReplacementBlur = (card) => {
  const replacement = normalizeInputText(card.target)
  card.manual_override = true
  card.alert_message = buildSuggestionByMethodWithCachedBase(card, card.process_method, {
    replacementText: replacement
  })
  enforceSuggestionLengthLimit(card)
  syncActionToAlertType(card)
}

const handleSuggestionInput = (card) => {
  const prevMethod = normalizeProcessMethod(card.process_method)
  card.alert_message = String(card.alert_message || '')
  enforceSuggestionLengthLimit(card)
  setCachedSuggestionByMethod(card, prevMethod, card.alert_message)
  applyRuleBBySuggestion(card)
  const nextMethod = normalizeProcessMethod(card.process_method)
  if (nextMethod !== prevMethod) {
    setCachedSuggestionByMethod(card, nextMethod, card.alert_message)
  }
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
  const processMethod = normalizeProcessMethod(card.process_method)
  const replacementContent = processMethod === PROCESS_METHOD.replace ? normalizeInputText(card.target) : ''
  return {
    error_type: card.error_type || '',
    severity: card.severity || riskByErrorType(card.error_type || ''),
    location: fieldText(card.content_type),
    evidence_text: card.source || '',
    description: card.alert_message || '',
    suggestion: replacementContent,
    process_method: processMethod,
    replacement_content: replacementContent,
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
      action: card.action,
      process_method: processMethod
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
  const baseParams = {
    page: 1,
    page_size: 1,
    only_mine: props.isAdminMode ? false : onlyMine.value,
    lite: true
  }
  if (reportQuery.value) baseParams.q = reportQuery.value

  const [all, annotated] = await Promise.all([
    api.getDoctorReports({ ...baseParams, tab: 'all' }),
    api.getDoctorReports({ ...baseParams, tab: 'annotated' })
  ])

  progress.value = { done: annotated.total || 0, total: all.total || 0 }
}

const loadReports = async () => {
  const params = {
    tab: activeFilter.value,
    page: 1,
    page_size: DOCTOR_LIST_PAGE_SIZE,
    only_mine: props.isAdminMode ? false : onlyMine.value,
    lite: true
  }
  if (reportQuery.value) params.q = reportQuery.value

  const res = await api.getDoctorReports(params)
  reportList.value = res.items
  reportTotal.value = res.total || 0

  await loadProgress()

  if (!currentReport.value && reportList.value.length > 0) {
    const preferred = props.initialReportId
      ? reportList.value.find((item) => item.id === props.initialReportId)
      : null
    if (preferred) {
      await openReport(preferred)
    } else if (props.initialReportId) {
      await openReport({ id: props.initialReportId })
    } else {
      await openReport(reportList.value[0])
    }
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
      const importedSuggestion = normalizeInputText(
        item.alert_message || item.alert_msg || item.description || item.suggestion_message || item.suggestion_note || ''
      )
      const card = {
        id: `pre-${report.id}-${idx}`,
        kind: 'pre',
        origin_kind: 'pre',
        state: 'pending',
        content_type: item.content_type || '',
        source: item.source || '',
        target: item.target || '',
        alert_type: String(item.alert_type ?? '2'),
        alert_message: item.alert_message || item.alert_msg || item.description || item.suggestion_message || item.suggestion_note || '',
        error_type: item.err_type || 'typos',
        severity: normalizeImportedSeverity(item.error_level || item.severity, item.err_type || 'typos'),
        source_in_start: item.source_in_start,
        source_in_end: item.source_in_end,
        process_method: PROCESS_METHOD.prompt,
        manual_override: false,
        action: 'prompt',
        _preserveBaseSuggestion: !!importedSuggestion
      }
      card.process_method = normalizeProcessMethod(item.process_method || inferProcessMethodFromImportedData(card))
      if (!card.alert_message) {
        card.alert_message = buildSuggestionByMethodWithReplacementAppend(card, card.process_method, { replacementText: card.target })
      }
      enforceSuggestionLengthLimit(card)
      syncActionToAlertType(card)
      normalizeOrganectomySuggestionSection(card)
      if (importedSuggestion) {
        setCachedSuggestionByMethod(card, PROCESS_METHOD.prompt, importedSuggestion)
      }
      setCachedSuggestionByMethod(card, card.process_method, card.alert_message)

      const dedupKey = [
        normalizeContentType(card.content_type),
        String(card.source || '').trim(),
        String(card.target || '').trim(),
        String(card.alert_type || '').trim(),
        String(card.process_method || '').trim(),
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
    const importedSuggestion = normalizeInputText(item.description || '')
    const anchorKind = item.anchor?.kind
    const anchorState = item.anchor?.state
    const isPendingPre = anchorKind === 'pre' && anchorState === 'pending'
    const rawProcessMethod = item.process_method || item.anchor?.process_method || item.anchor?.action || ''
    const card = {
      id: `manual-${report.id}-${idx}`,
      kind: isPendingPre ? 'pre' : 'manual',
      origin_kind: item.anchor?.origin_kind || (anchorKind === 'pre' ? 'pre' : 'manual'),
      state: isPendingPre ? 'pending' : 'saved',
      content_type: item.anchor?.content_type || item.location || 'description',
      source: item.evidence_text || item.anchor?.source || '',
      target: item.replacement_content || item.suggestion || item.anchor?.target || '',
      alert_type: String(item.anchor?.alert_type ?? '2'),
      alert_message: item.description || '',
      error_type: item.error_type || 'typos',
      severity: normalizeImportedSeverity(item.severity || item.error_level, item.error_type || 'typos'),
      source_in_start: item.anchor?.source_in_start,
      source_in_end: item.anchor?.source_in_end,
      process_method: normalizeProcessMethod(rawProcessMethod),
      manual_override: false,
      action: normalizeAction(item.anchor?.action),
      _preserveBaseSuggestion: !!importedSuggestion
    }

    if (!normalizeInputText(rawProcessMethod)) {
      card.process_method = inferProcessMethodFromImportedData(card)
    }
    if (!normalizeInputText(card.alert_message)) {
      card.alert_message = buildSuggestionByMethodWithReplacementAppend(card, card.process_method, { replacementText: card.target })
    }
    enforceSuggestionLengthLimit(card)
    syncActionToAlertType(card)
    normalizeOrganectomySuggestionSection(card)
    if (importedSuggestion) {
      setCachedSuggestionByMethod(card, PROCESS_METHOD.prompt, importedSuggestion)
    }
    setCachedSuggestionByMethod(card, card.process_method, card.alert_message)
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
      String(card.process_method || '').trim(),
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
  const row = reportList.value.find((item) => item.id === report.id)
  if (row) {
    row.status = detail.status
  }

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
  if (!currentReport.value || isEditingLocked.value) return
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
  card.process_method = normalizeProcessMethod(card.process_method || actionToProcessMethod(card.action))
  card.manual_override = !!card.manual_override
  if (!card.alert_message) {
    card.alert_message = buildSuggestionByMethodWithReplacementAppend(card, card.process_method, { replacementText: card.target })
  }
  card._targetValidationError = ''
  setCachedSuggestionByMethod(card, card.process_method, card.alert_message)
  applyProcessMethodInputState(card)
  card._backup = { ...card }
  card.state = 'editing'
  selectedCardId.value = card.id
}

const prepareCardForSave = async (card, options = {}) => {
  const { showValidationDialog = true, allowAutoSuggestionWhenEmpty = false } = options

  card.target = normalizeInputText(card.target)
  card.alert_message = normalizeInputText(card.alert_message)
  card.process_method = normalizeProcessMethod(card.process_method)
  card.manual_override = !!card.manual_override
  card._targetValidationError = ''
  enforceSuggestionLengthLimit(card)
  applyDefaultSeverity(card)

  // 保存时若填写了替换内容，则处理方式自动切换为“替换”。
  if (card.target) {
    card.process_method = PROCESS_METHOD.replace
  }

  if (card.process_method === PROCESS_METHOD.replace && !normalizeInputText(card.target)) {
    card._targetValidationError = '请填写替换内容'
    return false
  }

  if (!card.alert_message) {
    if (allowAutoSuggestionWhenEmpty) {
      card.alert_message = buildSuggestionByMethodWithReplacementAppend(card, card.process_method, { replacementText: card.target })
    } else {
      if (showValidationDialog) {
        ElMessage.warning('请填写建议说明')
      }
      return false
    }
  }

  enforceSuggestionLengthLimit(card)
  syncActionToAlertType(card)

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

const deleteCard = async (card) => {
  if (!currentReport.value) return
  try {
    await ElMessageBox.confirm(
      '删除后将放弃对此选中文本的标注，是否继续？',
      '删除确认',
      { confirmButtonText: '确认删除', cancelButtonText: '返回', type: 'warning' }
    )
  } catch (_e) {
    return
  }

  clearHighlightFocus()
  if (card.kind === 'pre' || card.origin_kind === 'pre') {
    markPreCardDismissed(currentReport.value.id, card)
  }
  cards.value = cards.value.filter((item) => item.id !== card.id)
  if (selectedCardId.value === card.id) {
    selectedCardId.value = null
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

  const range = selection.rangeCount > 0 ? selection.getRangeAt(0) : null
  const anchorEl = selection.anchorNode?.nodeType === Node.ELEMENT_NODE
    ? selection.anchorNode
    : selection.anchorNode?.parentElement
  const commonAncestorEl = range
    ? (range.commonAncestorContainer?.nodeType === Node.ELEMENT_NODE
      ? range.commonAncestorContainer
      : range.commonAncestorContainer?.parentElement)
    : null
  const fieldBlock = commonAncestorEl?.closest('[data-field]') || anchorEl?.closest('[data-field]')
  const field = fieldBlock?.dataset?.field || 'description'
  const contentEl = fieldBlock?.querySelector('.section-content') || null

  const shouldSkipNode = (textNode) => {
    const parent = textNode?.parentElement
    if (!parent) return true
    return !!parent.closest('.hl-mark, .hl-prompt-icon, .hl-prompt-triangle')
  }

  const computeOffsetByBoundary = (rootEl, boundaryNode, boundaryOffset) => {
    if (!rootEl || !boundaryNode) return null
    try {
      const offsetRange = document.createRange()
      offsetRange.setStart(rootEl, 0)
      offsetRange.setEnd(boundaryNode, boundaryOffset)
      const fragment = offsetRange.cloneContents()
      const container = document.createElement('div')
      container.appendChild(fragment)
      container.querySelectorAll('.hl-mark, .hl-prompt-icon, .hl-prompt-triangle').forEach((el) => el.remove())
      return container.textContent?.length ?? 0
    } catch (_e) {
      return null
    }
  }

  let sourceInStart = null
  let sourceInEnd = null
  if (range && contentEl && contentEl.contains(range.startContainer) && contentEl.contains(range.endContainer)) {
    const startOffset = computeOffsetByBoundary(contentEl, range.startContainer, range.startOffset)
    const endOffset = computeOffsetByBoundary(contentEl, range.endContainer, range.endOffset)
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
    process_method: PROCESS_METHOD.replace,
    manual_override: false,
    action: 'replace'
  }
  // 手动新建卡片时保持建议说明为空，显示输入框 placeholder“建议说明”。
  newCard.alert_message = ''
  enforceSuggestionLengthLimit(newCard)
  syncActionToAlertType(newCard)

  cards.value.push(newCard)
  selectedCardId.value = newCard.id
  scrollToCard(newCard.id)
}

const remindUnsubmitted = async (offset = 1) => {
  if (!currentReport.value || !isDraftWorkflowStatus(currentReport.value.status)) return 'pass'
  const directionText = offset < 0 ? '上一份' : '下一份'
  const submitText = submitButtonText.value
  try {
    await ElMessageBox.confirm(
      `该报告已暂存，暂未确认提交。你可以立即${submitText}，或继续查看${directionText}报告。`,
      '切换提示',
      {
        confirmButtonText: `立即${submitText}`,
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

  if (intent === 'submit' && currentReport.value && canSubmitStatus(currentReport.value.status)) {
    const canSubmit = await ensurePreCardsReadyBeforeSubmit()
    if (!canSubmit) return
    try {
      await api.submitAnnotation(currentReport.value.id, buildPayload())
      const nextStatus = currentReport.value.status === 'REVIEW_IN_PROGRESS' ? 'DONE' : 'SUBMITTED'
      updateCurrentReportStatusLocally(nextStatus)
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
  if (currentReport.value?.status === 'REVIEW_ASSIGNED') return true
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
  if (!currentReport.value || !canSubmitCurrentReport.value) return
  const canSubmit = await ensurePreCardsReadyBeforeSubmit()
  if (!canSubmit) return

  const previousReportId = currentReport.value.id
  const previousIndex = currentReportIndex.value
  const targetReportIdByCurrentOrder = (() => {
    if (!reportList.value.length) return null
    const baseIdx = reportList.value.findIndex((item) => item.id === previousReportId)
    if (baseIdx < 0) return null
    if (!autoGoNextAfterSubmit.value) return previousReportId
    const nextIdx = (baseIdx + 1 + reportList.value.length) % reportList.value.length
    return reportList.value[nextIdx]?.id || null
  })()

  submitting.value = true
  try {
    await api.submitAnnotation(currentReport.value.id, buildPayload())
    ElMessage.success(submitButtonText.value)
    await loadReports()

    const offset = autoGoNextAfterSubmit.value ? 1 : 0
    const targetReport =
      reportList.value.find((item) => item.id === targetReportIdByCurrentOrder) ||
      resolveReportAfterSubmit(previousReportId, previousIndex, offset)

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
  if (!currentReport.value || !showCancelAnnotationButton.value) return
  const reportId = currentReport.value.id
  const isReviewTask = currentReport.value.status === 'REVIEW_ASSIGNED'
  const confirmText = isReviewTask
    ? '确认后将进入复核修改状态，是否继续？'
    : '取消后，当前报告将回到待标注状态，是否继续？'
  const titleText = isReviewTask ? '开始复核修改' : '取消标注确认'
  const successText = isReviewTask
    ? '已进入复核修改状态，请完成核验后提交'
    : '已取消标注，当前报告已恢复为可编辑状态'
  try {
    await ElMessageBox.confirm(
      confirmText,
      titleText,
      {
        confirmButtonText: '确认取消',
        cancelButtonText: '返回',
        type: 'warning'
      }
    )
    await api.cancelAnnotation(reportId)
    ElMessage.success(successText)
    await loadReports()
    const refreshed = reportList.value.find((item) => item.id === reportId)
    if (refreshed) {
      await openReport(refreshed)
    } else if (currentReport.value) {
      // loadReports() 在当前报告不在列表时会自动切换到第一条，这里保持该结果即可。
      doctorTableRef.value?.setCurrentRow(currentReport.value)
    } else if (reportList.value.length > 0) {
      await openReport(reportList.value[0])
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
  height: calc(100vh - 170px);
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

.sheet-meta-line {
  margin-top: 2px;
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

.process-method-group {
  display: flex;
  width: 100%;
  gap: 8px;
  margin-bottom: 8px;
}

.process-method-btn {
  flex: 1;
  height: 30px;
  border: 1px solid #111827;
  border-radius: 4px;
  background: #f9fafb;
  color: #111827;
  cursor: pointer;
}

.process-method-btn.active {
  background: #f59e0b;
  border-color: #d97706;
  color: #111827;
  font-weight: 600;
}

.replace-target-input :deep(.el-input__wrapper) {
  box-shadow: 0 0 0 1px #f59e0b inset;
}

.replace-target-input-error :deep(.el-input__wrapper) {
  box-shadow: 0 0 0 1px #ef4444 inset;
}

.card-inline-error {
  margin-top: -4px;
  margin-bottom: 8px;
  font-size: 12px;
  line-height: 1.4;
  color: #ef4444;
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
