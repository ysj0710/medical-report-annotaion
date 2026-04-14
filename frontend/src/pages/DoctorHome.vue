<template>
  <div class="doctor-workbench">
    <aside class="left-panel">
      <div class="filter-row">
        <el-radio-group v-model="activeFilter" size="small" @change="loadReports">
          <el-radio-button value="all">全部</el-radio-button>
          <el-radio-button value="unannotated">未标注</el-radio-button>
          <el-radio-button value="annotated">已标注</el-radio-button>
          <el-radio-button value="review">待复核</el-radio-button>
          <el-radio-button value="reviewed">已复核</el-radio-button>
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
                  :value="col.key"
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
                <el-tag :type="getStatusType(row)">{{ getStatusText(row) }}</el-tag>
              </template>
              <template v-else-if="col.key === 'imported_at'" #default="{ row }">
                {{ formatTime(row.imported_at) }}
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>

      <div class="progress-wrap">
        <div class="progress-title">{{ progressTitle }} {{ progress.done }}/{{ progress.total }}</div>
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
          <el-button type="primary" @click="createManualCardFromSelection" :disabled="isEditingLocked">标注选中文本（Q）</el-button>
          <el-button type="success" @click="submitReport" :loading="submitting" :disabled="!canSubmitCurrentReport">{{ submitButtonText }}（S）</el-button>
          <el-button
            v-if="showCancelAnnotationButton"
            type="danger"
            plain
            @click="handleCancelAnnotationAction"
            :disabled="isCancelAnnotationActionDisabled"
            :class="{ 'cancel-annotation-btn-blocked': isCancelAnnotationBlockedByReview }"
          >
            {{ cancelAnnotationButtonText }}（D）
          </el-button>
          <div class="action-shortcut-hint">
            快捷键：Q 标注选中文本，S {{ submitButtonText }}<template v-if="showCancelAnnotationButton">，D {{ cancelAnnotationButtonText }}</template>
          </div>
        </div>
      </div>

      <div v-if="currentReport" class="report-sheet-shell">
        <div ref="reportSheetRef" class="report-sheet" @scroll="hideHighlightTooltip">
          <div class="sheet-head">
            <h2>{{ reportHeaderTitle }}</h2>
            <div>项目：{{ currentReport.exam_item || '-' }}</div>
            <div class="sheet-meta-line">
              性别：{{ currentReport.patient_sex || '未知' }}　年龄：{{ currentReport.patient_age || '-' }}
            </div>
            <div v-if="requiresDistributionBeforeAnnotation" class="distribution-warning-strip">
              请先分发报告给用户，再开始协同标注。当前待分发报告在管理员端仅支持查看，不支持直接标注。
            </div>
            <div v-else-if="isViewOnlyAccessibleReport" class="distribution-warning-strip">
              该报告当前未分配给你。你拥有“查看全部”权限，因此可以查看内容，但不能编辑、提交或参与协同标注。
            </div>
            <div v-if="!requiresDistributionBeforeAnnotation && !isViewOnlyAccessibleReport" class="collaboration-strip">
              <div class="collaboration-users">
                <span class="collaboration-label">协同标注</span>
                <span
                  v-for="participant in collaborationParticipants"
                  :key="participant.user_id"
                  :class="['collaboration-user', { me: participant.is_me, editor: participant.is_editor }]"
                >
                  {{ participant.username }}{{ participant.is_me ? '（你）' : '' }}
                </span>
                <span v-if="collaborationParticipants.length === 0" class="collaboration-empty">当前仅你在线</span>
              </div>
              <div :class="['collaboration-state', { locked: isCollaborationEditingLocked }]">
                {{ collaborationStatusText }}
              </div>
            </div>
          </div>

          <div ref="sheetBodyRef" class="sheet-body">
            <div class="section-block" data-field="description" @click="handleHighlightClick">
              <h3>【检查所见】</h3>
              <div
                class="section-content"
                v-html="getHighlightedHtml('description')"
                @mouseup="handleSectionSelectionMouseUp"
                @mousemove="handleHighlightTooltipMove"
                @mouseleave="hideHighlightTooltip"
              ></div>
            </div>
            <div class="section-block" data-field="impression" @click="handleHighlightClick">
              <h3>【诊断意见】</h3>
              <div
                class="section-content"
                v-html="getHighlightedHtml('impression')"
                @mouseup="handleSectionSelectionMouseUp"
                @mousemove="handleHighlightTooltipMove"
                @mouseleave="hideHighlightTooltip"
              ></div>
            </div>
          </div>
        </div>

        <div class="report-sheet-tooltip-layer">
          <div
            v-if="highlightTooltip.visible && highlightTooltip.text"
            ref="highlightTooltipRef"
            class="floating-highlight-tooltip"
            :style="highlightTooltipStyle"
          >
            <div v-if="highlightTooltip.title" class="floating-highlight-tooltip-title">
              {{ highlightTooltip.title }}
            </div>
            <div class="floating-highlight-tooltip-body">{{ highlightTooltip.text }}</div>
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
              <div class="card-head-main">
                <el-tag size="small" :type="card.kind === 'pre' ? 'warning' : 'primary'">
                  {{ card.kind === 'pre' ? '预标注' : '手动标注' }}
                </el-tag>
                <span class="error-type-badge-wrap">
                  <span class="error-type-emphasis header">{{ errorTypeText(card.error_type) }}</span>
                  <sup class="card-index">{{ getErrorTypeBadgeNumber(card.error_type) }}</sup>
                </span>
              </div>
              <div class="card-field">{{ fieldText(card.content_type) }}</div>
            </div>
          </template>

          <div class="card-body">
            <div class="row">
              <span class="label">错误文本：</span>
              <span>{{ card.source || '（缺失）' }}</span>
            </div>
            <div class="row" v-if="isReplaceMethod(card) && card.target"><span class="label">替换内容：</span>{{ card.target || '-' }}</div>

            <div v-if="isEditing(card)">
              <el-select v-model="card.error_type" placeholder="错误类型" style="width: 100%; margin-bottom: 8px" @change="handleErrorTypeChange(card)" :disabled="isEditingLocked">
                <el-option v-for="item in errorTypeOptions" :key="item.value" :label="item.label" :value="item.value" />
              </el-select>
              <div class="level-title">错误级别</div>
              <div class="severity-group">
                <button
                  type="button"
                  :class="['severity-btn', 'severity-btn-low', { active: card.severity === 'low' }]"
                  disabled
                >
                  低
                </button>
                <button
                  type="button"
                  :class="['severity-btn', 'severity-btn-medium', { active: card.severity === 'medium' }]"
                  disabled
                >
                  中
                </button>
                <button
                  type="button"
                  :class="['severity-btn', 'severity-btn-high', { active: card.severity === 'high' }]"
                  disabled
                >
                  高
                </button>
              </div>
              <div class="level-title">处理方式</div>
              <div class="process-method-group">
                <button
                  type="button"
                  :class="['process-method-btn', { active: card.process_method === PROCESS_METHOD.replace }]"
                  @click="handleManualProcessMethodSelect(card, PROCESS_METHOD.replace)"
                  :disabled="isEditingLocked || isProcessMethodDisabled(card, PROCESS_METHOD.replace)"
                >
                  替换
                </button>
                <button
                  type="button"
                  :class="['process-method-btn', { active: card.process_method === PROCESS_METHOD.prompt }]"
                  @click="handleManualProcessMethodSelect(card, PROCESS_METHOD.prompt)"
                  :disabled="isEditingLocked || isProcessMethodDisabled(card, PROCESS_METHOD.prompt)"
                >
                  仅提示
                </button>
                <button
                  type="button"
                  :class="['process-method-btn', { active: card.process_method === PROCESS_METHOD.delete }]"
                  @click="handleManualProcessMethodSelect(card, PROCESS_METHOD.delete)"
                  :disabled="isEditingLocked || isProcessMethodDisabled(card, PROCESS_METHOD.delete)"
                >
                  删除
                </button>
              </div>
              <el-input
                v-model="card.target"
                placeholder="替换后内容"
                :class="{
                  'replace-target-input': card.process_method === PROCESS_METHOD.replace,
                  'replace-target-input-error': !!card._targetValidationError
                }"
                style="margin-bottom: 8px"
                @input="handleReplacementInput(card)"
                :disabled="isEditingLocked || !isReplaceMethod(card)"
              />
              <div v-if="card._targetValidationError" class="card-inline-error">{{ card._targetValidationError }}</div>
              <div class="level-title">建议说明</div>
              <div class="suggestion-readonly">{{ getCardSuggestionText(card) }}</div>
            </div>

            <div v-else>
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
              <el-button v-if="showCancelEditButton(card)" size="small" @click.stop="cancelEdit(card)">取消</el-button>
            </template>

            <template v-else>
              <el-button v-if="card.state !== 'editing'" size="small" @click.stop="editCard(card)" :disabled="isEditingLocked">修改</el-button>
              <el-button v-if="card.state === 'editing'" size="small" type="primary" @click.stop="saveCard(card)" :disabled="isEditingLocked">保存</el-button>
              <el-button v-if="showCancelEditButton(card)" size="small" @click.stop="cancelEdit(card)">取消</el-button>
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

const TASK_COLUMNS_STORAGE_KEY_PREFIX = 'doctor_task_visible_columns_by_user_v2'
const DISMISSED_PRE_STORAGE_KEY_PREFIX = 'doctor_dismissed_pre_cards_by_user_v2'
const LEGACY_TASK_COLUMNS_STORAGE_KEY = 'doctor_task_visible_columns_v1'
const LEGACY_DISMISSED_PRE_STORAGE_KEY = 'doctor_dismissed_pre_cards_v1'
const DOCTOR_LIST_PAGE_SIZE = 1000
const REPORT_UPDATES_WS_KEEPALIVE_MS = 15000
const REPORT_UPDATES_WS_RECONNECT_MS = 1500
const COLLABORATION_HIDDEN_POLL_MS = 12000
const COLLABORATION_WS_KEEPALIVE_MS = 5000
const COLLABORATION_WS_EDIT_KEEPALIVE_MS = 2500
const COLLABORATION_WS_RECONNECT_MS = 1500
const COLLABORATION_WS_REQUEST_TIMEOUT_MS = 4000
const COLLABORATION_ACTIVITY_WINDOW_MS = 8000
const COLLABORATION_SELECTION_SYNC_DEBOUNCE_MS = 80
const LOCAL_SELECTION_ACTIVITY_HOLD_MS = 260
const COLLABORATION_ACTIVITY_LABEL_MAX_LENGTH = 80
const COLLABORATION_SELECTION_TEXT_MAX_LENGTH = 96

const activeFilter = ref(props.isAdminMode ? 'all' : 'unannotated')
const reportQuery = ref('')
const onlyMine = ref(true)
const currentUser = ref(null)

const doctorTableRef = ref(null)
const cardsContainerRef = ref(null)
const highlightTooltipRef = ref(null)
const reportSheetRef = ref(null)
const sheetBodyRef = ref(null)
const allReportList = ref([])
const reportList = ref([])
const reportTotal = ref(0)
const currentReport = ref(null)
const collaborationState = ref(null)
const collaborationUnavailable = ref(false)
const collaborationUnavailableNotified = ref(false)
const collaborationSocketConnected = ref(false)
const localCollaborationActivity = ref(null)
const currentAnnotationUpdatedAt = ref(null)
const remoteAnnotationRefreshing = ref(false)
const cards = ref([])
const selectedCardId = ref(null)
const createEmptyHighlightHtmlCache = () => ({
  description: { signature: '', html: '' },
  impression: { signature: '', html: '' }
})
const highlightHtmlCache = ref(createEmptyHighlightHtmlCache())

const submitting = ref(false)
const autoGoNextAfterSubmit = ref(true)
const autoSaving = ref(false)
const autoSavePending = ref(false)
const annotationProgress = ref({ done: 0, total: 0 })
const reviewProgress = ref({ done: 0, total: 0 })
const overallProgress = ref({ done: 0, total: 0 })
const highlightTooltip = ref({
  visible: false,
  title: '',
  text: '',
  left: 0,
  top: 0
})
const dismissedPreCardKeysByReport = new Map()
let highlightFocusTimer = null
let cardFocusTimer = null
let collaborationSocket = null
let collaborationSocketReportId = null
let collaborationSocketKeepAliveTimer = null
let collaborationSocketReconnectTimer = null
let collaborationSocketSessionId = 0
let collaborationSocketRequestSeq = 0
let collaborationSocketUrlCandidates = []
let collaborationSocketUrlIndex = 0
const collaborationSocketPendingRequests = new Map()
let lastLocalEditActivityAt = 0
let activeTooltipAnchor = null
let collaborationSelectionSyncTimer = null
let reportListLoadRequestSeq = 0
let reportUpdatesSocket = null
let reportUpdatesSocketKeepAliveTimer = null
let reportUpdatesSocketReconnectTimer = null
let reportUpdatesSocketSessionId = 0
let reportUpdatesSocketUrlCandidates = []
let reportUpdatesSocketUrlIndex = 0
let localSelectionActivityHoldUntil = 0
let lastPublishedActivitySignature = ''

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

const ERROR_TYPE_BADGE_ORDER = [
  'typos',
  'examitems',
  'typo_unit',
  'typo_modality',
  'positions',
  'bodyParts',
  'typoTerms',
  'organectomys',
  'sexs'
]

const FIXED_ERROR_TYPE_BADGE_MAP = Object.fromEntries(
  ERROR_TYPE_BADGE_ORDER.map((type, index) => [type, index + 1])
)

const dynamicErrorTypeBadgeMap = new Map()

const reportHeaderTitle = computed(() => {
  const modality = currentReport.value?.modality || currentReport.value?.exam_item || '影像'
  return `${modality}检查报告单`
})

const progress = computed(() => (
  activeFilter.value === 'all'
    ? overallProgress.value
    : ['review', 'reviewed'].includes(activeFilter.value)
      ? reviewProgress.value
      : annotationProgress.value
))
const progressTitle = computed(() => (
  activeFilter.value === 'all'
    ? '总体进度'
    : ['review', 'reviewed'].includes(activeFilter.value)
    ? '复核进度'
    : '工作进度'
))

const progressPercent = computed(() => {
  if (!progress.value.total) return 0
  return Math.round((progress.value.done / progress.value.total) * 100)
})

const highlightTooltipStyle = computed(() => ({
  left: `${highlightTooltip.value.left}px`,
  top: `${highlightTooltip.value.top}px`
}))

const isEditingLockedStatus = (status) => ['SUBMITTED', 'DONE', 'REVIEW_ASSIGNED'].includes(status || '')
const canSubmitStatus = (status) => ['ASSIGNED', 'IN_PROGRESS', 'REVIEW_ASSIGNED', 'REVIEW_IN_PROGRESS'].includes(status || '')
const isDraftWorkflowStatus = (status) => ['ASSIGNED', 'IN_PROGRESS', 'REVIEW_IN_PROGRESS'].includes(status || '')
const resolveBaseStatus = (reportLike) => reportLike?.status || ''
const getAnnotationStatus = (reportLike) => reportLike?.annotation_status || reportLike?.annotation?.status || ''
const getReviewCompletedUserIds = (reportLike) => Array.isArray(reportLike?.review_completed_user_ids) ? reportLike.review_completed_user_ids : []
const isReviewTask = (reportLike) => !!(
  reportLike?.is_review_task ||
  ['REVIEW_ASSIGNED', 'REVIEW_IN_PROGRESS'].includes(resolveBaseStatus(reportLike)) ||
  reportLike?.reviewer_doctor_id ||
  reportLike?.review_assigned_at ||
  getReviewCompletedUserIds(reportLike).length
)
const isAssignedReviewer = (reportLike) => !!reportLike?.is_current_user_assigned_reviewer
const hasCurrentUserCompletedReview = (reportLike) => !!reportLike?.has_current_user_completed_review
const isCurrentUserAnnotator = (reportLike) => {
  const currentUserId = currentUser.value?.id
  if (!currentUserId) return false
  return (
    reportLike?.annotator_doctor_id === currentUserId ||
    (
      !isReviewTask(reportLike) &&
      reportLike?.assigned_doctor_id === currentUserId
    )
  )
}
const isCurrentUserReviewOwner = (reportLike) => isAssignedReviewer(reportLike) || hasCurrentUserCompletedReview(reportLike)
const isInAnnotationTaskPool = (reportLike) => {
  if (props.isAdminMode) {
    return (
      !isReviewTask(reportLike) ||
      !!reportLike?.annotator_doctor_id ||
      getAnnotationStatus(reportLike) === 'SUBMITTED'
    )
  }
  return isCurrentUserAnnotator(reportLike)
}
const isInReviewTaskPool = (reportLike) => {
  if (props.isAdminMode) return isReviewTask(reportLike)
  return isCurrentUserReviewOwner(reportLike)
}
const isCurrentUserTaskOwner = (reportLike) => isCurrentUserAnnotator(reportLike) || isCurrentUserReviewOwner(reportLike)
const isAdminImportedReport = (reportLike) => props.isAdminMode && resolveBaseStatus(reportLike) === 'IMPORTED'
const requiresDistributionBeforeAnnotation = computed(() => isAdminImportedReport(currentReport.value))
const isViewOnlyAccessibleReport = computed(() => {
  if (props.isAdminMode) return false
  if (currentUser.value?.role !== 'doctor') return false
  if (!currentUser.value?.can_view_all) return false
  return !isCurrentUserTaskOwner(currentReport.value)
})

const getDisplayStatus = (reportLike) => {
  const baseStatus = resolveBaseStatus(reportLike)
  if (props.isAdminMode) return baseStatus
  if (
    isReviewTask(reportLike) &&
    isCurrentUserAnnotator(reportLike) &&
    !isCurrentUserReviewOwner(reportLike)
  ) {
    return 'SUBMITTED'
  }
  return baseStatus
}

const isAnnotatedDisplayStatus = (reportLike) => {
  if (!isInAnnotationTaskPool(reportLike)) return false
  if (props.isAdminMode) {
    return (
      ['SUBMITTED', 'REVIEW_ASSIGNED', 'REVIEW_IN_PROGRESS', 'DONE'].includes(resolveBaseStatus(reportLike)) ||
      getAnnotationStatus(reportLike) === 'SUBMITTED'
    )
  }
  const displayStatus = getDisplayStatus(reportLike)
  return displayStatus === 'SUBMITTED' || displayStatus === 'DONE'
}

const isUnannotatedDisplayStatus = (reportLike) => {
  if (!isInAnnotationTaskPool(reportLike)) return false
  if (isReviewTask(reportLike)) return false
  return ['IMPORTED', 'ASSIGNED', 'IN_PROGRESS'].includes(getDisplayStatus(reportLike))
}

const isPendingReviewDisplayStatus = (reportLike) => {
  if (!['REVIEW_ASSIGNED', 'REVIEW_IN_PROGRESS'].includes(getDisplayStatus(reportLike))) return false
  if (props.isAdminMode) return true
  return isAssignedReviewer(reportLike)
}

const isReviewedDisplayStatus = (reportLike) => {
  if (!isReviewTask(reportLike)) return false
  if (getDisplayStatus(reportLike) !== 'DONE') return false
  if (props.isAdminMode) return true
  return hasCurrentUserCompletedReview(reportLike) || isAssignedReviewer(reportLike)
}

const getReportsForFilter = (items, filter) => {
  if (filter === 'review') {
    return items.filter((item) => isPendingReviewDisplayStatus(item))
  }
  if (filter === 'reviewed') {
    return items.filter((item) => isReviewedDisplayStatus(item))
  }
  if (filter === 'annotated') {
    return items.filter((item) => isAnnotatedDisplayStatus(item))
  }
  if (filter === 'unannotated') {
    return items.filter((item) => isUnannotatedDisplayStatus(item))
  }
  return items
}

const filterReportsByActiveFilter = (items) => getReportsForFilter(items, activeFilter.value)

const resolveBestAvailableFilter = (items) => {
  const candidates = ['unannotated', 'review', 'reviewed', 'annotated', 'all']
  return candidates.find((filter) => getReportsForFilter(items, filter).length > 0) || 'all'
}

const buildAnnotationProgress = (items) => {
  const annotationItems = items.filter((item) => isInAnnotationTaskPool(item))
  const total = annotationItems.length
  const done = annotationItems.filter((item) => isAnnotatedDisplayStatus(item)).length
  return { done, total }
}

const buildReviewProgress = (items) => {
  const reviewItems = items.filter((item) => isInReviewTaskPool(item))
  const done = reviewItems.filter((item) => (
    getDisplayStatus(item) === 'DONE' || getReviewCompletedUserIds(item).length > 0
  )).length
  return { done, total: reviewItems.length }
}

const buildOverallProgress = (items) => {
  const annotationProgressValue = buildAnnotationProgress(items)
  const reviewProgressValue = buildReviewProgress(items)
  return {
    done: annotationProgressValue.done + reviewProgressValue.done,
    total: annotationProgressValue.total + reviewProgressValue.total
  }
}

const syncCurrentReportSummaryFromRow = (row) => {
  if (!currentReport.value || !row || currentReport.value.id !== row.id) return
  currentReport.value.status = row.status
  currentReport.value.annotation_status = row.annotation_status
  currentReport.value.annotation_submitted_at = row.annotation_submitted_at
  currentReport.value.assigned_doctor_id = row.assigned_doctor_id
  currentReport.value.annotator_doctor_id = row.annotator_doctor_id
  currentReport.value.reviewer_doctor_id = row.reviewer_doctor_id
  currentReport.value.submitted_at = row.submitted_at
  currentReport.value.review_completed_at = row.review_completed_at
  currentReport.value.review_completed_user_ids = row.review_completed_user_ids
  currentReport.value.review_completed_users = row.review_completed_users
  currentReport.value.is_review_task = row.is_review_task
  currentReport.value.is_current_user_assigned_reviewer = row.is_current_user_assigned_reviewer
  currentReport.value.has_current_user_completed_review = row.has_current_user_completed_review
}

const syncReportCollectionsFromAllReports = () => {
  reportList.value = filterReportsByActiveFilter(allReportList.value)
  reportTotal.value = reportList.value.length
  annotationProgress.value = buildAnnotationProgress(allReportList.value)
  reviewProgress.value = buildReviewProgress(allReportList.value)
  overallProgress.value = buildOverallProgress(allReportList.value)

  const currentRow = currentReport.value
    ? allReportList.value.find((item) => item.id === currentReport.value.id)
    : null
  if (currentRow) {
    syncCurrentReportSummaryFromRow(currentRow)
  }
}

const collaborationParticipants = computed(() => collaborationState.value?.participants || [])
const currentEditorUserId = computed(() => collaborationState.value?.current_editor_user_id || null)
const currentEditorUsername = computed(() => collaborationState.value?.current_editor_username || '')
const currentEditorRole = computed(() => collaborationState.value?.current_editor_role || '')
const currentCollaborationActivityUserId = computed(() => collaborationState.value?.current_activity_user_id || null)
const currentCollaborationActivityUsername = computed(() => collaborationState.value?.current_activity_username || '')
const currentCollaborationActivityRole = computed(() => collaborationState.value?.current_activity_role || '')
const currentCollaborationActivityIsEditor = computed(() => !!collaborationState.value?.current_activity_is_editor)
const currentCollaborationActivity = computed(() => collaborationState.value?.current_activity || null)
const isCurrentUserEditor = computed(() => {
  const userId = currentUser.value?.id
  return !!userId && currentEditorUserId.value === userId
})
const hasRemoteCollaborationActivity = computed(() => {
  const userId = currentUser.value?.id
  return !!(
    currentCollaborationActivity.value &&
    currentCollaborationActivityUserId.value &&
    currentCollaborationActivityUserId.value !== userId
  )
})
const isCollaborationEditingLocked = computed(() => {
  if (!currentReport.value) return false
  if (collaborationUnavailable.value) return false
  return !!collaborationState.value?.is_edit_locked
})

const currentDisplayStatus = computed(() => getDisplayStatus(currentReport.value))
const isEditingLocked = computed(() => {
  return requiresDistributionBeforeAnnotation.value || isViewOnlyAccessibleReport.value || isEditingLockedStatus(currentDisplayStatus.value) || isCollaborationEditingLocked.value
})
const canSubmitCurrentReport = computed(() => {
  if (!currentReport.value) return false
  if (requiresDistributionBeforeAnnotation.value) return false
  if (isViewOnlyAccessibleReport.value) return false
  if (isCollaborationEditingLocked.value) return false
  return canSubmitStatus(currentDisplayStatus.value)
})
const isAnnotatedTabReviewLocked = computed(() => {
  if (!currentReport.value) return false
  if (activeFilter.value !== 'annotated') return false
  if (!isReviewTask(currentReport.value)) return false
  return !isCurrentUserReviewOwner(currentReport.value)
})
const isCancelAnnotationBlockedByReview = computed(() => {
  if (!currentReport.value) return false
  if (!isReviewTask(currentReport.value)) return false
  return isAnnotatedTabReviewLocked.value || !isCurrentUserReviewOwner(currentReport.value)
})
const showCancelAnnotationButton = computed(() => {
  if (!currentReport.value) return false
  if (isViewOnlyAccessibleReport.value) return false
  if (requiresDistributionBeforeAnnotation.value) return false
  if (isCancelAnnotationBlockedByReview.value) return true
  const status = currentDisplayStatus.value
  if (isReviewTask(currentReport.value)) return status === 'DONE'
  const annotationStatus = getAnnotationStatus(currentReport.value)
  if (annotationStatus === 'SUBMITTED') return true
  return ['SUBMITTED', 'DONE'].includes(status)
})
const isCancelAnnotationActionDisabled = computed(() => isCollaborationEditingLocked.value)
const cancelAnnotationButtonText = computed(() => {
  if (isCancelAnnotationBlockedByReview.value) return '取消标注'
  if (
    ['review', 'reviewed'].includes(activeFilter.value) &&
    isReviewTask(currentReport.value) &&
    currentDisplayStatus.value === 'DONE'
  ) {
    return '取消复核'
  }
  return '取消标注'
})
const submitButtonText = computed(() => {
  if (isReviewTask(currentReport.value)) {
    return isAssignedReviewer(currentReport.value) ? '完成标注核验' : '确认无误'
  }
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
const collaborationActivityText = computed(() => {
  const activity = currentCollaborationActivity.value
  if (!activity) return ''
  const label = normalizeInputText(activity.label)
  if (label) return label
  const selectionText = normalizeInputText(activity.selection_text)
  if (activity.status === 'selecting') {
    return selectionText ? `正在框选“${selectionText.slice(0, 16)}”` : '正在框选文本'
  }
  if (activity.status === 'editing') {
    return selectionText ? `正在标注“${selectionText.slice(0, 16)}”` : '正在编辑标注'
  }
  return '正在协同标注'
})
const collaborationStatusText = computed(() => {
  if (!currentReport.value) return ''
  if (requiresDistributionBeforeAnnotation.value) {
    return '待分发报告不支持管理员直接标注'
  }
  if (isViewOnlyAccessibleReport.value) {
    if (currentEditorUserId.value) {
      const roleText = currentEditorRole.value === 'admin' ? '管理员' : '专家'
      return `该报告未分配给你，你当前仅可查看。${roleText}${currentEditorUsername.value || '其他用户'}正在协同标注`
    }
    return '该报告未分配给你，你当前仅可查看，不能编辑或参与协同标注'
  }
  if (collaborationUnavailable.value) {
    return '协同服务暂不可用，当前已切换为单人标注模式'
  }
  if (isCollaborationEditingLocked.value) {
    const roleText = currentEditorRole.value === 'admin' ? '管理员' : '专家'
    return `${roleText}${currentEditorUsername.value || '其他用户'} ${collaborationActivityText.value || '正在标注'}，你当前为只读查看`
  }
  if (hasRemoteCollaborationActivity.value) {
    const roleTextValue = currentCollaborationActivityRole.value === 'admin' ? '管理员' : '专家'
    return `${roleTextValue}${currentCollaborationActivityUsername.value || '其他用户'} ${collaborationActivityText.value || '正在框选文本'}，当前尚未锁定报告`
  }
  if (isCurrentUserEditor.value) {
    return `${collaborationActivityText.value || '当前由你操控'}，停止操作几秒后，其他协作者可接管`
  }
  if (collaborationParticipants.value.length > 1) {
    return '当前无人锁定，任一协作者操作后将获得编辑权'
  }
  return '当前无人协同，可直接开始标注'
})

const visibleColumns = computed(() => {
  const selected = new Set(visibleColumnKeys.value)
  return doctorTableColumns.filter((col) => selected.has(col.key))
})

watch(visibleColumnKeys, (val) => {
  persistVisibleColumnKeys(val)
}, { deep: true })

const getStatusText = (reportLike) => {
  const baseStatus = resolveBaseStatus(reportLike)
  const map = {
    IMPORTED: '待分发',
    ASSIGNED: '未标注',
    IN_PROGRESS: '标注中',
    SUBMITTED: '已标注',
    REVIEW_ASSIGNED: '待复核',
    REVIEW_IN_PROGRESS: '复核中',
    DONE: '已完成'
  }
  const displayStatus = getDisplayStatus(reportLike)
  return map[displayStatus] || baseStatus || displayStatus
}

const getStatusType = (reportLike) => {
  const displayStatus = getDisplayStatus(reportLike)
  if (displayStatus === 'DONE') return 'success'
  if (displayStatus === 'SUBMITTED') return 'primary'
  if (displayStatus === 'IN_PROGRESS' || displayStatus === 'REVIEW_ASSIGNED' || displayStatus === 'REVIEW_IN_PROGRESS') return 'warning'
  return 'info'
}

const formatTime = (value) => {
  if (!value) return '-'
  const d = new Date(value)
  if (Number.isNaN(d.getTime())) return '-'
  const pad = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

const roleText = (role) => {
  if (role === 'admin') return '管理员'
  if (role === 'doctor') return '专家'
  return '用户'
}

const noteLocalEditActivity = () => {
  lastLocalEditActivityAt = Date.now()
}

const buildCollaborationLockMessage = (state, actionText = '编辑') => {
  const ownerName = state?.current_editor_username || '其他用户'
  return `${roleText(state?.current_editor_role)}${ownerName}正在标注这份报告，当前无法${actionText}`
}

const buildLocalCollaborationFallbackState = (reportId, options = {}) => {
  const { granted = null } = options
  const now = new Date().toISOString()
  const me = currentUser.value
  const canEdit = !isViewOnlyAccessibleReport.value
  const isEditor = !!granted && !!me && canEdit

  return {
    report_id: reportId,
    participants: me && canEdit ? [{
      user_id: me.id,
      username: me.username,
      role: me.role,
      is_me: true,
      is_editor: isEditor,
      last_seen_at: now,
      last_activity_at: isEditor ? now : null
    }] : [],
    current_editor_user_id: isEditor ? me.id : null,
    current_editor_username: isEditor ? me.username : null,
    current_editor_role: isEditor ? me.role : null,
    current_activity_user_id: isEditor ? me.id : null,
    current_activity_username: isEditor ? me.username : null,
    current_activity_role: isEditor ? me.role : null,
    current_activity_is_editor: isEditor,
    current_activity: isEditor ? localCollaborationActivity.value : null,
    is_edit_locked: false,
    can_edit: canEdit,
    granted,
    expires_at: null,
    annotation_updated_at: currentAnnotationUpdatedAt.value
  }
}

const toTimeMs = (value) => {
  if (!value) return 0
  const time = new Date(value).getTime()
  return Number.isFinite(time) ? time : 0
}

const trimCollaborationText = (value, maxLength) => {
  const text = String(value ?? '').trim()
  if (!text) return null
  return text.length > maxLength ? text.slice(0, maxLength) : text
}

const cloneCollaborationActivity = (activity) => {
  if (!activity || !activity.status) return null
  return {
    status: String(activity.status || '').trim().toLowerCase() || null,
    label: trimCollaborationText(activity.label, COLLABORATION_ACTIVITY_LABEL_MAX_LENGTH),
    content_type: String(activity.content_type || '').trim().toLowerCase() || null,
    selection_start: Number.isInteger(activity.selection_start) ? activity.selection_start : null,
    selection_end: Number.isInteger(activity.selection_end) ? activity.selection_end : null,
    selection_text: trimCollaborationText(activity.selection_text, COLLABORATION_SELECTION_TEXT_MAX_LENGTH)
  }
}

const toSignaturePart = (value) => {
  if (value === null || value === undefined) return ''
  return String(value).trim()
}

const buildHighlightCardSignature = (card) => {
  return [
    toSignaturePart(card?.id),
    toSignaturePart(card?.kind),
    toSignaturePart(card?.origin_kind),
    toSignaturePart(card?.state),
    toSignaturePart(card?.content_type),
    toSignaturePart(card?.source),
    toSignaturePart(card?.source_in_start),
    toSignaturePart(card?.source_in_end),
    toSignaturePart(card?.action),
    toSignaturePart(card?.process_method),
    toSignaturePart(card?.alert_message)
  ].join('::')
}

const buildActivityRenderSignature = (activity) => {
  const normalized = cloneCollaborationActivity(activity)
  if (!normalized) return ''
  return [
    toSignaturePart(normalized.status),
    toSignaturePart(normalized.label),
    toSignaturePart(normalized.content_type),
    toSignaturePart(normalized.selection_start),
    toSignaturePart(normalized.selection_end),
    toSignaturePart(normalized.selection_text)
  ].join('::')
}

const buildParticipantRenderSignature = (participant) => {
  return [
    toSignaturePart(participant?.user_id),
    toSignaturePart(participant?.username),
    toSignaturePart(participant?.role),
    participant?.is_me ? '1' : '0',
    participant?.is_editor ? '1' : '0'
  ].join('::')
}

const buildCollaborationStateRenderSignature = (state) => {
  if (!state) return ''
  const participants = Array.isArray(state.participants)
    ? state.participants.map(buildParticipantRenderSignature).sort().join('||')
    : ''
  return [
    toSignaturePart(state.report_id),
    participants,
    toSignaturePart(state.current_editor_user_id),
    toSignaturePart(state.current_editor_username),
    toSignaturePart(state.current_editor_role),
    toSignaturePart(state.current_activity_user_id),
    toSignaturePart(state.current_activity_username),
    toSignaturePart(state.current_activity_role),
    state.current_activity_is_editor ? '1' : '0',
    state.is_edit_locked ? '1' : '0',
    state.can_edit ? '1' : '0',
    buildActivityRenderSignature(state.current_activity)
  ].join('@@')
}

const highlightCardsSignature = computed(() => {
  return cards.value.map(buildHighlightCardSignature).join('||')
})

const remoteCollaborationHighlightSignature = computed(() => {
  if (!hasRemoteCollaborationActivity.value) return ''
  return [
    toSignaturePart(currentCollaborationActivityUserId.value),
    currentCollaborationActivityIsEditor.value ? '1' : '0',
    buildActivityRenderSignature(currentCollaborationActivity.value)
  ].join('@@')
})

const clearHighlightHtmlCache = (field = null) => {
  if (field && highlightHtmlCache.value[field]) {
    highlightHtmlCache.value[field] = { signature: '', html: '' }
    return
  }
  highlightHtmlCache.value = createEmptyHighlightHtmlCache()
}

const buildCollaborationLabel = (status, field, text) => {
  const fieldName = fieldText(field)
  const shortText = normalizeInputText(text).slice(0, 18)
  if (status === 'selecting') {
    return shortText ? `${fieldName}已选中：${shortText}` : `${fieldName}正在选中文本`
  }
  return shortText ? `${fieldName}标注中：${shortText}` : `${fieldName}正在编辑标注`
}

const buildCollaborationActivityFromSelection = (selection) => {
  if (!selection?.field) return null
  return cloneCollaborationActivity({
    status: 'selecting',
    label: buildCollaborationLabel('selecting', selection.field, selection.selectedText),
    content_type: selection.field,
    selection_start: selection.sourceInStart,
    selection_end: selection.sourceInEnd,
    selection_text: selection.selectedText
  })
}

const buildCollaborationActivityFromCard = (card) => {
  if (!card) return null
  const field = normalizeContentType(card.content_type) || 'description'
  const sourceText = normalizeInputText(card.source)
  return cloneCollaborationActivity({
    status: 'editing',
    label: buildCollaborationLabel('editing', field, sourceText),
    content_type: field,
    selection_start: Number.isInteger(card.source_in_start) ? card.source_in_start : null,
    selection_end: Number.isInteger(card.source_in_end) ? card.source_in_end : null,
    selection_text: sourceText
  })
}

const setLocalCollaborationActivity = (activity) => {
  localCollaborationActivity.value = cloneCollaborationActivity(activity)
}

const clearLocalCollaborationActivity = () => {
  localCollaborationActivity.value = null
  localSelectionActivityHoldUntil = 0
}

const getCollaborationIntentForLocalActivity = () => {
  if (isCurrentUserEditor.value) return 'edit'
  return localCollaborationActivity.value?.status === 'editing' ? 'edit' : 'view'
}

const getHeartbeatActivityPayload = (intent) => {
  if (intent === 'release') return null
  return cloneCollaborationActivity(localCollaborationActivity.value)
}

const getReportAnnotationUpdatedAt = (reportLike) => {
  return reportLike?.annotation?.updated_at || null
}

const setCurrentAnnotationUpdatedAt = (value) => {
  currentAnnotationUpdatedAt.value = value || null
  if (currentReport.value?.annotation) {
    currentReport.value.annotation.updated_at = value || null
  }
}

const applyReportDetail = async (detail, options = {}) => {
  const { keepSelectedCard = false, tableRow = null } = options
  const previousSelectedCardId = keepSelectedCard ? selectedCardId.value : null

  currentReport.value = detail
  setCurrentAnnotationUpdatedAt(getReportAnnotationUpdatedAt(detail))
  clearHighlightHtmlCache()

  const row = allReportList.value.find((item) => item.id === detail.id) || reportList.value.find((item) => item.id === detail.id)
  if (row) {
    row.status = detail.status
    row.annotation_status = detail.annotation_status
    row.annotation_submitted_at = detail.annotation_submitted_at
    row.review_completed_at = detail.review_completed_at
    row.review_completed_user_ids = detail.review_completed_user_ids
    row.review_completed_users = detail.review_completed_users
    row.is_review_task = detail.is_review_task
    row.is_current_user_assigned_reviewer = detail.is_current_user_assigned_reviewer
    row.has_current_user_completed_review = detail.has_current_user_completed_review
  }
  syncReportCollectionsFromAllReports()

  const preCards = buildPreCards(detail)
  const manualCards = buildManualCardsFromAnnotation(detail)
  const dismissedKeys = dismissedPreCardKeysByReport.get(detail.id) || new Set()
  const visiblePreCards = preCards.filter((card) => !dismissedKeys.has(buildCardAnchorKey(card)))
  const savedAnchorKeys = new Set(manualCards.map((card) => buildCardAnchorKey(card)))
  const remainingPreCards = visiblePreCards.filter((card) => !savedAnchorKeys.has(buildCardAnchorKey(card)))
  cards.value = dedupeCards([...manualCards, ...remainingPreCards])

  if (previousSelectedCardId && cards.value.some((card) => card.id === previousSelectedCardId)) {
    selectedCardId.value = previousSelectedCardId
  } else {
    selectedCardId.value = cards.value[0]?.id || null
  }

  await nextTick()
  doctorTableRef.value?.setCurrentRow(
    tableRow ||
    allReportList.value.find((item) => item.id === detail.id) ||
    reportList.value.find((item) => item.id === detail.id) ||
    detail
  )
}

const refreshCurrentReportFromServer = async (options = {}) => {
  const { silent = true } = options
  if (!currentReport.value?.id || remoteAnnotationRefreshing.value) return

  const reportId = currentReport.value.id
  remoteAnnotationRefreshing.value = true
  try {
    const detail = await api.getDoctorReport(reportId)
    if (currentReport.value?.id !== reportId) return
    await applyReportDetail(detail, {
      keepSelectedCard: true,
      tableRow: allReportList.value.find((item) => item.id === reportId) || reportList.value.find((item) => item.id === reportId) || currentReport.value
    })
  } catch (e) {
    if (!silent) {
      ElMessage.error(e.message || '同步最新标注内容失败')
    }
  } finally {
    remoteAnnotationRefreshing.value = false
  }
}

const maybeRefreshAnnotationFromCollaborationState = async (state) => {
  if (!state || !currentReport.value || state.report_id !== currentReport.value.id) return
  if (isCurrentUserEditor.value) return
  if (cards.value.some((card) => card.state === 'editing')) return

  const remoteUpdatedAtMs = toTimeMs(state.annotation_updated_at)
  const localUpdatedAtMs = toTimeMs(currentAnnotationUpdatedAt.value)
  if (!remoteUpdatedAtMs || remoteUpdatedAtMs <= localUpdatedAtMs) return

  await refreshCurrentReportFromServer({ silent: true })
}

const applyCollaborationState = (nextState, options = {}) => {
  const { announceLoss = true } = options
  const previousState = collaborationState.value
  const previousEditorId = previousState?.current_editor_user_id
  const currentUserId = currentUser.value?.id
  if (
    buildCollaborationStateRenderSignature(previousState) ===
    buildCollaborationStateRenderSignature(nextState)
  ) {
    return
  }
  collaborationState.value = nextState || null
  if (
    announceLoss &&
    currentUserId &&
    previousEditorId === currentUserId &&
    nextState?.current_editor_user_id &&
    nextState.current_editor_user_id !== currentUserId
  ) {
    ElMessage.warning(`${roleText(nextState.current_editor_role)}${nextState.current_editor_username || '其他用户'}已接管当前报告`)
  }
}

const clearCollaborationSocketKeepAliveTimer = () => {
  if (collaborationSocketKeepAliveTimer) {
    clearTimeout(collaborationSocketKeepAliveTimer)
    collaborationSocketKeepAliveTimer = null
  }
}

const clearCollaborationSocketReconnectTimer = () => {
  if (collaborationSocketReconnectTimer) {
    clearTimeout(collaborationSocketReconnectTimer)
    collaborationSocketReconnectTimer = null
  }
}

const clearPendingCollaborationSocketRequests = (message = '协同连接已断开') => {
  collaborationSocketPendingRequests.forEach((pending) => {
    clearTimeout(pending.timer)
    pending.reject(new Error(message))
  })
  collaborationSocketPendingRequests.clear()
}

const clearCollaborationSelectionSyncTimer = () => {
  if (collaborationSelectionSyncTimer) {
    clearTimeout(collaborationSelectionSyncTimer)
    collaborationSelectionSyncTimer = null
  }
}

const canUseCollaborationSocket = (reportId = currentReport.value?.id) => {
  if (!reportId) return false
  return !!(
    collaborationSocket &&
    collaborationSocketConnected.value &&
    collaborationSocket.readyState === WebSocket.OPEN &&
    collaborationSocketReportId === reportId
  )
}

const getCollaborationSocketKeepAliveDelay = () => {
  if (typeof document !== 'undefined' && document.hidden) {
    return COLLABORATION_HIDDEN_POLL_MS
  }
  const isLocallyEditing =
    isCurrentUserEditor.value &&
    (Date.now() - lastLocalEditActivityAt) < COLLABORATION_ACTIVITY_WINDOW_MS
  return isLocallyEditing ? COLLABORATION_WS_EDIT_KEEPALIVE_MS : COLLABORATION_WS_KEEPALIVE_MS
}

const getCollaborationSocketKeepAliveIntent = () => {
  const isLocallyEditing =
    isCurrentUserEditor.value &&
    (Date.now() - lastLocalEditActivityAt) < COLLABORATION_ACTIVITY_WINDOW_MS
  return isLocallyEditing ? 'edit' : 'view'
}

const handleIncomingCollaborationState = async (state, options = {}) => {
  const { announceLoss = true } = options
  if (currentReport.value?.id === state?.report_id) {
    applyCollaborationState(state, { announceLoss })
    await maybeRefreshAnnotationFromCollaborationState(state)
  }
}

const sendCollaborationSocketIntent = async (intent = 'view', options = {}) => {
  const { reportId = currentReport.value?.id, awaitState = true, announceLoss = true } = options
  if (!canUseCollaborationSocket(reportId)) return null

  const payload = {
    intent,
    activity: getHeartbeatActivityPayload(intent)
  }

  if (!awaitState) {
    collaborationSocket.send(JSON.stringify(payload))
    return null
  }

  const requestId = `ws-${reportId}-${Date.now()}-${++collaborationSocketRequestSeq}`
  payload.request_id = requestId

  const state = await new Promise((resolve, reject) => {
    const timer = window.setTimeout(() => {
      collaborationSocketPendingRequests.delete(requestId)
      reject(new Error('协同响应超时'))
    }, COLLABORATION_WS_REQUEST_TIMEOUT_MS)

    collaborationSocketPendingRequests.set(requestId, {
      timer,
      announceLoss,
      resolve,
      reject
    })

    try {
      collaborationSocket.send(JSON.stringify(payload))
    } catch (e) {
      clearTimeout(timer)
      collaborationSocketPendingRequests.delete(requestId)
      reject(e)
    }
  })

  return state
}

const scheduleCollaborationSocketKeepAlive = () => {
  clearCollaborationSocketKeepAliveTimer()
  const reportId = collaborationSocketReportId
  const sessionId = collaborationSocketSessionId
  if (!canUseCollaborationSocket(reportId)) return

  collaborationSocketKeepAliveTimer = window.setTimeout(async () => {
    if (sessionId !== collaborationSocketSessionId || !canUseCollaborationSocket(reportId)) return
    try {
      await sendCollaborationSocketIntent(getCollaborationSocketKeepAliveIntent(), {
        reportId,
        awaitState: false,
        announceLoss: true
      })
    } catch (_e) {
      // ignore and let close/reconnect handle fallback
    } finally {
      if (sessionId === collaborationSocketSessionId) {
        scheduleCollaborationSocketKeepAlive()
      }
    }
  }, getCollaborationSocketKeepAliveDelay())
}

const scheduleCollaborationSocketReconnect = (sessionId, reportId) => {
  clearCollaborationSocketReconnectTimer()
  if (!reportId || sessionId !== collaborationSocketSessionId || currentReport.value?.id !== reportId) return
  collaborationSocketReconnectTimer = window.setTimeout(() => {
    if (sessionId !== collaborationSocketSessionId || currentReport.value?.id !== reportId) return
    startCollaborationSocket(reportId, {
      urlCandidates: collaborationSocketUrlCandidates,
      candidateIndex: collaborationSocketUrlIndex
    })
  }, COLLABORATION_WS_RECONNECT_MS)
}

const stopCollaborationSocket = (options = {}) => {
  const { close = true } = options
  collaborationSocketSessionId += 1
  collaborationSocketConnected.value = false
  clearCollaborationSocketKeepAliveTimer()
  clearCollaborationSocketReconnectTimer()
  clearPendingCollaborationSocketRequests()

  const socket = collaborationSocket
  collaborationSocket = null
  collaborationSocketReportId = null
  collaborationSocketUrlCandidates = []
  collaborationSocketUrlIndex = 0

  if (close && socket) {
    try {
      socket.close(1000, 'normal-close')
    } catch (_e) {
      // ignore
    }
  }
}

const openCollaborationSocketCandidate = (reportId, sessionId, urlCandidates, candidateIndex) => {
  const wsUrl = urlCandidates[candidateIndex]
  if (!wsUrl) return false

  collaborationSocketReportId = reportId
  collaborationSocketUrlCandidates = [...urlCandidates]
  collaborationSocketUrlIndex = candidateIndex

  const socket = new WebSocket(wsUrl)
  collaborationSocket = socket
  let opened = false

  socket.addEventListener('open', () => {
    if (sessionId !== collaborationSocketSessionId || collaborationSocket !== socket || collaborationSocketReportId !== reportId) {
      try {
        socket.close(1000, 'stale-connection')
      } catch (_e) {
        // ignore
      }
      return
    }
    opened = true
    collaborationUnavailable.value = false
    collaborationUnavailableNotified.value = false
    collaborationSocketConnected.value = true
    scheduleCollaborationSocketKeepAlive()
    void sendCollaborationSocketIntent('view', {
      reportId,
      awaitState: true,
      announceLoss: false
    }).catch(() => {
      // ignore and let the regular reconnect / fallback flow handle it
    })
  })

  socket.addEventListener('message', (event) => {
    if (sessionId !== collaborationSocketSessionId || collaborationSocket !== socket || collaborationSocketReportId !== reportId) return
    void (async () => {
      try {
        const payload = JSON.parse(event.data || '{}')
        const requestId = String(payload.request_id || '').trim()
        if (payload.type === 'error') {
          const pending = requestId ? collaborationSocketPendingRequests.get(requestId) : null
          if (pending) {
            clearTimeout(pending.timer)
            collaborationSocketPendingRequests.delete(requestId)
            pending.reject(new Error(payload.message || '协同状态更新失败'))
          }
          return
        }

        if (payload.type !== 'state' || !payload.state) return

        const pending = requestId ? collaborationSocketPendingRequests.get(requestId) : null
        if (pending) {
          clearTimeout(pending.timer)
          collaborationSocketPendingRequests.delete(requestId)
          pending.resolve(payload.state)
        }

        await handleIncomingCollaborationState(payload.state, {
          announceLoss: pending?.announceLoss ?? true
        })
      } catch (_e) {
        // ignore malformed websocket payloads
      }
    })()
  })

  socket.addEventListener('close', () => {
    if (sessionId !== collaborationSocketSessionId) return
    const reportStillOpen = currentReport.value?.id === reportId
    collaborationSocketConnected.value = false
    clearCollaborationSocketKeepAliveTimer()
    clearPendingCollaborationSocketRequests()
    if (collaborationSocket === socket) {
      collaborationSocket = null
    }
    if (!reportStillOpen) return

    if (!opened && candidateIndex + 1 < urlCandidates.length) {
      openCollaborationSocketCandidate(reportId, sessionId, urlCandidates, candidateIndex + 1)
      return
    }

    scheduleCollaborationSocketReconnect(sessionId, reportId)
  })

  socket.addEventListener('error', () => {
    collaborationSocketConnected.value = false
  })

  return true
}

const startCollaborationSocket = (reportId, options = {}) => {
  if (!reportId || typeof WebSocket === 'undefined') return false
  const {
    urlCandidates = api.buildCollaborationWebSocketUrls(reportId),
    candidateIndex = 0
  } = options
  if (!Array.isArray(urlCandidates) || !urlCandidates.length) return false

  stopCollaborationSocket()

  const sessionId = collaborationSocketSessionId
  return openCollaborationSocketCandidate(
    reportId,
    sessionId,
    urlCandidates,
    Math.max(0, Math.min(candidateIndex, urlCandidates.length - 1))
  )
}

const syncCollaborationHttp = async (intent = 'view', options = {}) => {
  const { silent = true, reportId = currentReport.value?.id, announceLoss = true } = options
  if (!reportId) return null
  if (collaborationUnavailable.value) {
    const fallbackState = buildLocalCollaborationFallbackState(reportId, {
      granted: intent === 'edit' ? true : null
    })
    if (currentReport.value?.id === reportId) {
      applyCollaborationState(fallbackState, { announceLoss: false })
    }
    return fallbackState
  }
  try {
    const state = await api.collaborationHeartbeat(reportId, intent, getHeartbeatActivityPayload(intent))
    if (currentReport.value?.id === reportId) {
      applyCollaborationState(state, { announceLoss })
      await maybeRefreshAnnotationFromCollaborationState(state)
    }
    return state
  } catch (e) {
    collaborationUnavailable.value = true
    const fallbackState = buildLocalCollaborationFallbackState(reportId, {
      granted: intent === 'edit' ? true : null
    })
    if (currentReport.value?.id === reportId) {
      applyCollaborationState(fallbackState, { announceLoss: false })
    }
    if (!collaborationUnavailableNotified.value) {
      collaborationUnavailableNotified.value = true
      ElMessage.warning('协同服务暂不可用，已切换为单人标注模式')
    }
    if (!silent) {
      ElMessage.error(e.message || '协同状态更新失败')
    }
    return fallbackState
  }
}

const syncCollaboration = async (intent = 'view', options = {}) => {
  const { reportId = currentReport.value?.id, announceLoss = true } = options
  if (!reportId) return null

  if (canUseCollaborationSocket(reportId)) {
    try {
      const state = await sendCollaborationSocketIntent(intent, {
        reportId,
        awaitState: true,
        announceLoss
      })
      if (state) {
        await handleIncomingCollaborationState(state, { announceLoss })
        return state
      }
    } catch (_e) {
      // fallback to HTTP heartbeat below
    }
  }

  return syncCollaborationHttp(intent, options)
}

const publishLocalCollaborationActivity = async () => {
  if (!currentReport.value?.id) return
  const intent = getCollaborationIntentForLocalActivity()
  const activitySignature = [
    String(currentReport.value.id),
    intent,
    buildActivityRenderSignature(localCollaborationActivity.value)
  ].join('@@')
  if (activitySignature === lastPublishedActivitySignature) return
  lastPublishedActivitySignature = activitySignature

  if (canUseCollaborationSocket(currentReport.value.id)) {
    try {
      if (intent === 'edit') {
        noteLocalEditActivity()
      }
      await sendCollaborationSocketIntent(intent, {
        reportId: currentReport.value.id,
        awaitState: false,
        announceLoss: false
      })
      scheduleCollaborationSocketKeepAlive()
      return
    } catch (_e) {
      // fallback to HTTP heartbeat below
    }
  }

  await syncCollaborationHttp(intent, {
    silent: true,
    reportId: currentReport.value.id,
    announceLoss: false
  })
}

const clearReportUpdatesSocketKeepAliveTimer = () => {
  if (reportUpdatesSocketKeepAliveTimer) {
    clearTimeout(reportUpdatesSocketKeepAliveTimer)
    reportUpdatesSocketKeepAliveTimer = null
  }
}

const clearReportUpdatesSocketReconnectTimer = () => {
  if (reportUpdatesSocketReconnectTimer) {
    clearTimeout(reportUpdatesSocketReconnectTimer)
    reportUpdatesSocketReconnectTimer = null
  }
}

const scheduleReportUpdatesSocketKeepAlive = (sessionId) => {
  clearReportUpdatesSocketKeepAliveTimer()
  if (
    typeof window === 'undefined' ||
    sessionId !== reportUpdatesSocketSessionId ||
    !reportUpdatesSocket ||
    reportUpdatesSocket.readyState !== WebSocket.OPEN
  ) {
    return
  }

  reportUpdatesSocketKeepAliveTimer = window.setTimeout(() => {
    if (
      sessionId !== reportUpdatesSocketSessionId ||
      !reportUpdatesSocket ||
      reportUpdatesSocket.readyState !== WebSocket.OPEN
    ) {
      return
    }
    try {
      reportUpdatesSocket.send('ping')
    } catch (_e) {
      // ignore and let reconnect handle it
    } finally {
      scheduleReportUpdatesSocketKeepAlive(sessionId)
    }
  }, REPORT_UPDATES_WS_KEEPALIVE_MS)
}

const scheduleReportUpdatesSocketReconnect = (sessionId) => {
  clearReportUpdatesSocketReconnectTimer()
  if (typeof window === 'undefined' || sessionId !== reportUpdatesSocketSessionId) return

  reportUpdatesSocketReconnectTimer = window.setTimeout(() => {
    if (sessionId !== reportUpdatesSocketSessionId) return
    startReportUpdatesSocket({
      urlCandidates: reportUpdatesSocketUrlCandidates,
      candidateIndex: reportUpdatesSocketUrlIndex
    })
  }, REPORT_UPDATES_WS_RECONNECT_MS)
}

const stopReportUpdatesSocket = (options = {}) => {
  const { close = true } = options
  reportUpdatesSocketSessionId += 1
  clearReportUpdatesSocketKeepAliveTimer()
  clearReportUpdatesSocketReconnectTimer()

  const socket = reportUpdatesSocket
  reportUpdatesSocket = null
  reportUpdatesSocketUrlCandidates = []
  reportUpdatesSocketUrlIndex = 0

  if (close && socket) {
    try {
      socket.close(1000, 'normal-close')
    } catch (_e) {
      // ignore
    }
  }
}

const handleReportUpdatesMessage = async (payload) => {
  if (payload?.type !== 'reports-updated') return
  await loadReports({ silent: true })
}

const openReportUpdatesSocketCandidate = (sessionId, urlCandidates, candidateIndex) => {
  const wsUrl = urlCandidates[candidateIndex]
  if (!wsUrl || typeof WebSocket === 'undefined') return false

  reportUpdatesSocketUrlCandidates = [...urlCandidates]
  reportUpdatesSocketUrlIndex = candidateIndex

  const socket = new WebSocket(wsUrl)
  reportUpdatesSocket = socket
  let opened = false

  socket.addEventListener('open', () => {
    if (sessionId !== reportUpdatesSocketSessionId || reportUpdatesSocket !== socket) {
      try {
        socket.close(1000, 'stale-connection')
      } catch (_e) {
        // ignore
      }
      return
    }
    opened = true
    clearReportUpdatesSocketReconnectTimer()
    scheduleReportUpdatesSocketKeepAlive(sessionId)
    void loadReports({ silent: true })
  })

  socket.addEventListener('message', (event) => {
    if (sessionId !== reportUpdatesSocketSessionId || reportUpdatesSocket !== socket) return
    try {
      const payload = JSON.parse(event.data || '{}')
      void handleReportUpdatesMessage(payload)
    } catch (_e) {
      // ignore malformed payloads
    }
  })

  socket.addEventListener('close', () => {
    if (sessionId !== reportUpdatesSocketSessionId) return
    clearReportUpdatesSocketKeepAliveTimer()
    if (reportUpdatesSocket === socket) {
      reportUpdatesSocket = null
    }

    if (!opened && candidateIndex + 1 < urlCandidates.length) {
      openReportUpdatesSocketCandidate(sessionId, urlCandidates, candidateIndex + 1)
      return
    }

    scheduleReportUpdatesSocketReconnect(sessionId)
  })

  socket.addEventListener('error', () => {
    clearReportUpdatesSocketKeepAliveTimer()
  })

  return true
}

const startReportUpdatesSocket = (options = {}) => {
  if (typeof WebSocket === 'undefined') return false
  const {
    urlCandidates = api.buildReportUpdatesWebSocketUrls(),
    candidateIndex = 0
  } = options
  if (!Array.isArray(urlCandidates) || !urlCandidates.length) return false

  stopReportUpdatesSocket()

  const sessionId = reportUpdatesSocketSessionId
  return openReportUpdatesSocketCandidate(
    sessionId,
    urlCandidates,
    Math.max(0, Math.min(candidateIndex, urlCandidates.length - 1))
  )
}

const handleDocumentVisibilityChange = () => {
  const isVisible = typeof document === 'undefined' || !document.hidden
  if (isVisible) {
    if (!reportUpdatesSocket || reportUpdatesSocket.readyState !== WebSocket.OPEN) {
      startReportUpdatesSocket()
    }
    void loadReports({ silent: true })
  }
  const reportId = currentReport.value?.id
  if (!reportId) return
  if (requiresDistributionBeforeAnnotation.value || isViewOnlyAccessibleReport.value) return
  if (canUseCollaborationSocket(reportId)) {
    clearCollaborationSocketKeepAliveTimer()
    if (typeof document !== 'undefined' && !document.hidden) {
      void sendCollaborationSocketIntent(getCollaborationSocketKeepAliveIntent(), {
        reportId,
        awaitState: false,
        announceLoss: true
      })
    }
    scheduleCollaborationSocketKeepAlive()
    return
  }
  if (!collaborationUnavailable.value && typeof document !== 'undefined' && !document.hidden) {
    startCollaborationSocket(reportId)
  }
}

const handleWindowResize = () => {
  if (highlightTooltip.value.visible && activeTooltipAnchor) {
    void showHighlightTooltip(activeTooltipAnchor)
  }
}

const startCollaborationRealtime = async () => {
  if (!currentReport.value?.id) {
    stopCollaborationSocket()
    collaborationState.value = null
    return
  }
  if (requiresDistributionBeforeAnnotation.value || isViewOnlyAccessibleReport.value) {
    stopCollaborationSocket()
    collaborationState.value = null
    return
  }

  collaborationUnavailable.value = false
  collaborationUnavailableNotified.value = false
  const reportId = currentReport.value.id
  const socketStarted = startCollaborationSocket(reportId)
  if (!socketStarted) {
    await syncCollaborationHttp('view', { silent: true, reportId, announceLoss: false })
  }
}

const releaseCollaboration = async (reportId, options = {}) => {
  const { silent = true } = options
  if (!reportId) return
  const usingSocket = canUseCollaborationSocket(reportId)
  if (usingSocket) {
    try {
      await sendCollaborationSocketIntent('release', {
        reportId,
        awaitState: false,
        announceLoss: false
      })
    } catch (_e) {
      // ignore and let socket close trigger server-side release fallback
    } finally {
      stopCollaborationSocket()
      if (currentReport.value?.id === reportId) {
        collaborationState.value = null
      }
    }
    return
  }
  if (collaborationUnavailable.value) {
    stopCollaborationSocket()
    if (currentReport.value?.id === reportId) {
      collaborationState.value = null
    }
    return
  }
  try {
    await api.collaborationHeartbeat(reportId, 'release')
  } catch (e) {
    if (!silent) {
      ElMessage.error(e.message || '释放协同锁失败')
    }
  } finally {
    if (currentReport.value?.id === reportId) {
      collaborationState.value = null
    }
  }
}

const ensureEditAccess = async (actionText = '编辑') => {
  if (!currentReport.value) return false
  if (requiresDistributionBeforeAnnotation.value) {
    ElMessage.warning('请先分发报告给用户，再开始协同标注')
    return false
  }
  if (isViewOnlyAccessibleReport.value) {
    ElMessage.warning('该报告未分配给你，你当前仅支持查看，不能编辑或参与协同标注')
    return false
  }
  if (isCurrentUserEditor.value) {
    noteLocalEditActivity()
    return true
  }

  const state = await syncCollaboration('edit', {
    silent: true,
    reportId: currentReport.value.id,
    announceLoss: false
  })
  if (state?.granted) {
    noteLocalEditActivity()
    return true
  }
  if (state) {
    ElMessage.warning(buildCollaborationLockMessage(state, actionText))
  }
  return false
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
  if (['typos', 'typo_modality', 'typoTerms'].includes(errorType)) return 'low'
  if (['examitems'].includes(errorType)) return 'medium'
  if (['typo_unit', 'positions', 'organectomys', 'sexs', 'bodyParts'].includes(errorType)) return 'high'
  return 'medium'
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

const PROCESS_METHOD_RULES_BY_ERROR_TYPE = {
  typos: [PROCESS_METHOD.replace, PROCESS_METHOD.delete],
  examitems: [PROCESS_METHOD.prompt],
  typo_unit: [PROCESS_METHOD.replace, PROCESS_METHOD.prompt],
  typo_modality: [PROCESS_METHOD.prompt],
  positions: [PROCESS_METHOD.prompt],
  bodyParts: [PROCESS_METHOD.prompt],
  typoTerms: [PROCESS_METHOD.replace, PROCESS_METHOD.prompt],
  organectomys: [PROCESS_METHOD.prompt],
  sexs: [PROCESS_METHOD.prompt]
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

const getErrorTypeBadgeNumber = (errorType) => {
  const normalizedType = normalizeInputText(errorType)
  if (!normalizedType) return '-'
  if (FIXED_ERROR_TYPE_BADGE_MAP[normalizedType]) {
    return FIXED_ERROR_TYPE_BADGE_MAP[normalizedType]
  }
  if (!dynamicErrorTypeBadgeMap.has(normalizedType)) {
    dynamicErrorTypeBadgeMap.set(normalizedType, 10 + dynamicErrorTypeBadgeMap.size)
  }
  return dynamicErrorTypeBadgeMap.get(normalizedType)
}

const getAllowedProcessMethodsByErrorType = (errorType) => {
  return PROCESS_METHOD_RULES_BY_ERROR_TYPE[errorType] || [
    PROCESS_METHOD.replace,
    PROCESS_METHOD.prompt,
    PROCESS_METHOD.delete
  ]
}

const getDefaultProcessMethodByErrorType = (errorType) => {
  return getAllowedProcessMethodsByErrorType(errorType)[0] || PROCESS_METHOD.prompt
}

const isProcessMethodAllowed = (errorType, method) => {
  return getAllowedProcessMethodsByErrorType(errorType).includes(normalizeProcessMethod(method))
}

const normalizeProcessMethodByErrorType = (errorType, method) => {
  const normalizedMethod = normalizeProcessMethod(method)
  if (isProcessMethodAllowed(errorType, normalizedMethod)) return normalizedMethod
  return getDefaultProcessMethodByErrorType(errorType)
}

const isReplaceMethod = (card) => {
  return normalizeProcessMethod(card?.process_method) === PROCESS_METHOD.replace
}

const isProcessMethodDisabled = (card, method) => {
  return !isProcessMethodAllowed(card?.error_type, method)
}

const buildReplaceSuggestionText = (source, target) => {
  const sourceText = normalizeInputText(source)
  const targetText = normalizeInputText(target)
  if (!sourceText || !targetText) return ''
  return `建议将“${sourceText}”替换为“${targetText}”`
}

const buildDeleteSuggestionText = (source) => {
  const sourceText = normalizeInputText(source)
  if (!sourceText) return '建议删除'
  return `建议删除“${sourceText}”`
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
  card.process_method = normalizeProcessMethodByErrorType(
    card.error_type,
    card.process_method || actionToProcessMethod(card.action || inferActionByCard(card))
  )
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

const shouldPrefillTargetByErrorType = (errorType) =>
  getDefaultProcessMethodByErrorType(errorType) === PROCESS_METHOD.replace

const buildPromptSuggestionByErrorType = (card) => {
  const source = normalizeInputText(card.source)
  const modality = normalizeInputText(currentReport.value?.modality) || '当前设备'
  const bodyPart = extractBodyPart()
  const patientSex = normalizeInputText(currentReport.value?.patient_sex) || '未知'
  const sectionName = getSectionNameByCard(card)

  switch (card.error_type) {
    case 'examitems':
      return '请核对检查项目是否一致'
    case 'typo_unit':
      return source ? `请核对“${source}”的单位是否正确` : '请核对单位是否正确'
    case 'typo_modality':
      return source ? `请核对“${source}”与设备类型“${modality}”是否一致` : `请核对设备类型“${modality}”是否一致`
    case 'positions':
      return source ? `请核对“${source}”的方位描述是否一致` : '请核对方位描述是否一致'
    case 'bodyParts':
      return source ? `请核对“${source}”与检查部位“${bodyPart}”是否一致` : `请核对内容与检查部位“${bodyPart}”是否一致`
    case 'typoTerms':
      return source ? `请核对“${source}”的术语是否准确` : '请核对专业术语是否准确'
    case 'organectomys':
      return `${sectionName}中，描述了与患者已记录的已切除脏器相矛盾的内容`
    case 'sexs':
      return source ? `请核对“${source}”与性别“${patientSex}”是否一致` : `请核对内容与性别“${patientSex}”是否一致`
    default:
      return source ? `请核对“${source}”是否准确` : '请核对该处描述'
  }
}

const buildReplaceSuggestionByErrorType = (card, replacementText) => {
  return buildReplaceSuggestionText(card?.source, replacementText)
}

const buildDeleteSuggestionByErrorType = (card) => buildDeleteSuggestionText(card.source)

const buildSuggestionByMethod = (card, method, options = {}) => {
  const normalizedMethod = normalizeProcessMethodByErrorType(card?.error_type, method)
  const replacementText = normalizeInputText(options.replacementText ?? card.target)
  if (normalizedMethod === PROCESS_METHOD.delete) {
    return buildDeleteSuggestionByErrorType(card)
  }
  if (normalizedMethod === PROCESS_METHOD.prompt) {
    return buildPromptSuggestionByErrorType(card)
  }
  if (!replacementText) return '请先填写替换内容'
  return buildReplaceSuggestionByErrorType(card, replacementText)
}

const buildSuggestionByMethodWithReplacementAppend = (card, method, options = {}) => {
  return buildSuggestionByMethod(card, method, options)
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
  card.alert_message = buildSuggestionByMethod(card, PROCESS_METHOD.prompt)
}

const buildSuggestionByMethodWithCachedBase = (card, method, options = {}) => {
  return buildSuggestionByMethod(card, method, options)
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

const getCardReplacementText = (card) => {
  const targetText = normalizeInputText(card?.target)
  if (targetText) return targetText
  return extractReplacementFromSuggestion(card?.alert_message)
}

const inferProcessMethodFromImportedData = (card) => {
  const message = normalizeInputText(card.alert_message)
  const defaultMethod = getDefaultProcessMethodByErrorType(card.error_type)
  if (/替换/.test(message)) {
    if (!isProcessMethodAllowed(card.error_type, PROCESS_METHOD.replace)) return defaultMethod
    const extracted = extractReplacementFromSuggestion(message)
    if (extracted) card.target = extracted
    return PROCESS_METHOD.replace
  }
  if (DELETE_HINT_PATTERN.test(message) && isProcessMethodAllowed(card.error_type, PROCESS_METHOD.delete)) {
    return PROCESS_METHOD.delete
  }
  if (!message) return defaultMethod
  if (isProcessMethodAllowed(card.error_type, PROCESS_METHOD.prompt)) return PROCESS_METHOD.prompt
  return defaultMethod
}

const syncCardSuggestion = (card, options = {}) => {
  if (!card) return ''
  const suggestion = buildSuggestionByMethod(card, card.process_method, options)
  card.alert_message = suggestion
  enforceSuggestionLengthLimit(card)
  return card.alert_message
}

const getCardSuggestionText = (card) => {
  return normalizeInputText(buildSuggestionByMethod(card, card?.process_method, {
    replacementText: card?.target
  })) || '-'
}

const isEditing = (card) => card.state === 'editing'

const showCancelEditButton = (card) => {
  if (!isEditing(card)) return false
  const backup = card?._backup
  return card?.kind === 'pre' || backup?.kind === 'pre' || backup?.state === 'saved'
}

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

const clearCardFocus = () => {
  document.querySelectorAll('.error-card.card-focus').forEach((el) => {
    el.classList.remove('card-focus')
  })
  if (cardFocusTimer) {
    clearTimeout(cardFocusTimer)
    cardFocusTimer = null
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

const focusCardInList = async (card, options = {}) => {
  if (!card?.id) return
  const { scrollToCardList = true } = options
  selectedCardId.value = card.id
  if (scrollToCardList) {
    await scrollToCard(card.id)
  }
  await nextTick()
  const container = cardsContainerRef.value
  if (!container) return
  const safeId = getSafeSelectorValue(card.id)
  const cardEl = container.querySelector(`.error-card[data-card-id="${safeId}"]`)
  if (!cardEl) return
  clearCardFocus()
  cardEl.classList.add('card-focus')
  cardFocusTimer = window.setTimeout(() => {
    cardEl.classList.remove('card-focus')
    cardFocusTimer = null
  }, 1800)
}

const findSubmitBlockingCard = () => {
  const incompleteNewManualCard = cards.value.find((card) =>
    card.kind === 'manual' &&
    card.state === 'editing' &&
    !card._backup
  )
  if (incompleteNewManualCard) {
    return {
      card: incompleteNewManualCard,
      message: '当前新增的选中文本标注未完成，请先填写并保存，或删除该标注卡片后再完成标注。'
    }
  }

  const editingCard = cards.value.find((card) => card.state === 'editing')
  if (!editingCard) return null

  return {
    card: editingCard,
    message: editingCard.kind === 'pre'
      ? '当前有修改中的预标注卡片未完成，请先保存、取消或删除该标注卡片后再完成标注。'
      : '当前有修改中的标注卡片未完成，请先保存、取消或删除该标注卡片后再完成标注。'
  }
}

const ensureCardsReadyBeforeSubmit = async () => {
  const blocking = findSubmitBlockingCard()
  if (!blocking) return true

  await focusCardInList(blocking.card, { scrollToCardList: true })

  ElMessage.warning({
    message: blocking.message,
    duration: 3500,
    grouping: true
  })

  await focusCardInList(blocking.card, { scrollToCardList: true })
  return false
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

const getScopedStorageUserKey = () => {
  const userId = currentUser.value?.id
  return userId ? String(userId) : ''
}

const getTaskColumnsStorageKey = () => {
  const userKey = getScopedStorageUserKey()
  return userKey ? `${TASK_COLUMNS_STORAGE_KEY_PREFIX}:${userKey}` : ''
}

const getDismissedPreStorageKey = () => {
  const userKey = getScopedStorageUserKey()
  return userKey ? `${DISMISSED_PRE_STORAGE_KEY_PREFIX}:${userKey}` : ''
}

const persistVisibleColumnKeys = (columnKeys) => {
  const storageKey = getTaskColumnsStorageKey()
  if (!storageKey) return
  localStorage.setItem(storageKey, JSON.stringify(columnKeys))
  localStorage.removeItem(LEGACY_TASK_COLUMNS_STORAGE_KEY)
}

const restoreVisibleColumnKeys = () => {
  const storageKey = getTaskColumnsStorageKey()
  if (!storageKey) return
  const storedColumns = localStorage.getItem(storageKey)
  if (!storedColumns) return
  try {
    const parsed = JSON.parse(storedColumns)
    const allowed = new Set(doctorTableColumns.map((item) => item.key))
    const clean = Array.isArray(parsed) ? parsed.filter((key) => allowed.has(key)) : []
    if (clean.length) visibleColumnKeys.value = clean
  } catch (_e) {
    localStorage.removeItem(storageKey)
  }
}

const persistDismissedPreCardKeys = () => {
  const storageKey = getDismissedPreStorageKey()
  if (!storageKey) return
  const payload = {}
  dismissedPreCardKeysByReport.forEach((set, reportId) => {
    if (set.size > 0) {
      payload[String(reportId)] = Array.from(set)
    }
  })
  localStorage.setItem(storageKey, JSON.stringify(payload))
  localStorage.removeItem(LEGACY_DISMISSED_PRE_STORAGE_KEY)
}

const restoreDismissedPreCardKeys = () => {
  const storageKey = getDismissedPreStorageKey()
  if (!storageKey) return
  const raw = localStorage.getItem(storageKey)
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
    localStorage.removeItem(storageKey)
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
  card.severity = riskByErrorType(card.error_type)
}

const applyProcessMethodInputState = (card) => {
  card.process_method = normalizeProcessMethodByErrorType(card.error_type, card.process_method)
  syncActionToAlertType(card)
  syncCardSuggestion(card)
}

const resetCardByErrorType = (card) => {
  card.manual_override = false
  card.process_method = getDefaultProcessMethodByErrorType(card.error_type)
  applyDefaultSeverity(card)
  applyProcessMethodInputState(card)
}

const handleErrorTypeChange = (card) => {
  noteLocalEditActivity()
  applyDefaultSeverity(card)
  resetCardByErrorType(card)
}

const handleManualProcessMethodSelect = (card, method) => {
  noteLocalEditActivity()
  const nextMethod = normalizeProcessMethodByErrorType(card.error_type, method)
  const currentMethod = normalizeProcessMethodByErrorType(card.error_type, card.process_method)
  if (nextMethod === currentMethod) return
  if (!isProcessMethodAllowed(card.error_type, nextMethod)) return
  card.process_method = nextMethod
  card.manual_override = true
  applyProcessMethodInputState(card)
  card._targetValidationError = ''
}

const handleReplacementInput = (card) => {
  noteLocalEditActivity()
  card.target = String(card.target || '')
  card._targetValidationError = ''
  if (isReplaceMethod(card)) {
    syncCardSuggestion(card, { replacementText: card.target })
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
  const hasExplicitStart = Number.isInteger(parsedStart)
  const hasExplicitEnd = Number.isInteger(parsedEnd)
  const hasExplicitRange = hasExplicitStart || hasExplicitEnd

  if ((hasExplicitStart && parsedStart < 0) || (hasExplicitEnd && parsedEnd < 0)) {
    return { start: 0, end: 0, missing: true }
  }

  const candidates = []
  if (hasExplicitStart && hasExplicitEnd) {
    candidates.push([parsedStart, parsedEnd], [parsedStart - 1, parsedEnd - 1])
  }
  if (hasExplicitStart && source) {
    candidates.push([parsedStart, parsedStart + source.length], [parsedStart - 1, parsedStart - 1 + source.length])
  }

  for (const [rawStart, rawEnd] of candidates) {
    const start = Math.max(0, rawStart)
    const end = Math.min(text.length, Math.max(start, rawEnd))
    if (!source || text.slice(start, end) === source) {
      return { start, end, missing: false }
    }
  }

  if (hasExplicitRange) {
    return null
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

  const rawHighlights = cards.value
    .filter((card) => normalizeContentType(card.content_type) === field)
    .map((card) => {
      const range = resolveRange(text, card)
      if (!range) return null
      return {
        ...card,
        index: getErrorTypeBadgeNumber(card.error_type),
        start: range.start,
        end: range.end,
        missing: !!range.missing
      }
    })
    .filter(Boolean)

  const remoteActivity = hasRemoteCollaborationActivity.value
    ? currentCollaborationActivity.value
    : null
  if (
    remoteActivity &&
    !isCurrentUserEditor.value &&
    normalizeContentType(remoteActivity.content_type) === field
  ) {
    const activityRange = resolveRange(text, {
      source: remoteActivity.selection_text || '',
      source_in_start: remoteActivity.selection_start,
      source_in_end: remoteActivity.selection_end
    })
    if (activityRange && !activityRange.missing && activityRange.end > activityRange.start) {
      rawHighlights.push({
        id: '__remote-collaboration__',
        kind: 'collaboration-activity',
        origin_kind: 'collaboration-activity',
        action: 'prompt',
        alert_message: remoteActivity.label || collaborationActivityText.value || '协作者正在标注',
        activity_status: remoteActivity.status || 'editing',
        source: remoteActivity.selection_text || '',
        index: 0,
        start: activityRange.start,
        end: activityRange.end,
        missing: false
      })
    }
  }

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

const buildHighlightTooltip = (card) => {
  if (card?.kind === 'collaboration-activity') {
    return {
      title: card.activity_status === 'selecting' ? '对方已选中' : '对方标注中',
      text: card.alert_message || '协作者正在处理这段内容'
    }
  }
  const suggestionText = getCardSuggestionText(card)
  if (!suggestionText || suggestionText === '-') return ''
  return {
    title: errorTypeText(card?.error_type),
    text: suggestionText
  }
}

const renderBadges = (cardsInRange) => {
  const badgeHtml = cardsInRange
    .filter((card) => Number(card.index) > 0)
    .map((card) => `<span class="hl-mark" data-card-id="${card.id}">${card.index}</span>`)
    .join('')
  return badgeHtml ? `<span class="hl-badge-stack">${badgeHtml}</span>` : ''
}

const buildHighlightCacheSignature = (field, text) => {
  return [
    toSignaturePart(currentReport.value?.id),
    field,
    text,
    highlightCardsSignature.value,
    remoteCollaborationHighlightSignature.value,
    isCurrentUserEditor.value ? '1' : '0'
  ].join('@@')
}

const getHighlightedHtml = (field) => {
  const text = getReportTextByField(field)
  if (!text) return '无'

  const cacheSignature = buildHighlightCacheSignature(field, text)
  const cached = highlightHtmlCache.value[field]
  if (cached?.signature === cacheSignature) {
    return cached.html
  }

  const highlights = buildHighlights(field)
  if (!highlights.length) {
    const html = escapeHtml(text)
    highlightHtmlCache.value[field] = { signature: cacheSignature, html }
    return html
  }

  let cursor = 0
  const parts = []
  for (const h of highlights) {
    const safeStart = Math.max(0, Math.min(text.length, h.start))
    const safeEnd = Math.max(safeStart, Math.min(text.length, h.end))

    if (safeStart >= cursor) {
      parts.push(escapeHtml(text.slice(cursor, safeStart)))
    }

    const collaborationCard = h.cards.find((card) => card.kind === 'collaboration-activity')
    const persistedCards = h.cards.filter((card) => card.kind !== 'collaboration-activity')
    const primaryCard = persistedCards[0] || collaborationCard || h.cards[0]
    const badge = renderBadges(persistedCards)
    const tooltipText = buildHighlightTooltip(primaryCard)
    const tooltipAttr = tooltipText
      ? ` data-tooltip-title="${escapeHtml(tooltipText.title || '')}" data-tooltip="${escapeHtml(tooltipText.text || '')}"`
      : ''

    if (h.missing || safeStart === safeEnd) {
      const missingText = primaryCard.source || '缺失文本'
      const replacement = `<span class="hl-chip missing" data-card-id="${primaryCard.id}"${tooltipAttr}>[缺失: ${escapeHtml(missingText)}]${badge}</span>`
      parts.push(replacement)
      cursor = safeStart
      continue
    }

    const sourceText = text.slice(safeStart, safeEnd)
    const action = normalizeAction(primaryCard.action)
    const baseClass = collaborationCard
      ? 'hl-chip hl-collaboration-live'
      : h.cards.some((card) => card.kind === 'manual') ? 'hl-chip manual' : 'hl-chip pre'
    const actionClass = action === 'delete' ? 'hl-delete' : action === 'prompt' ? 'hl-prompt' : 'hl-replace'
    const promptIcon = action === 'prompt' && !collaborationCard ? '<span class="hl-prompt-triangle">!</span>' : ''
    const collaborationStatus = collaborationCard
      ? `<span class="hl-collab-status">${collaborationCard.activity_status === 'selecting' ? '对方已选中' : '对方标注中'}</span>`
      : ''
    const replacementText = action === 'replace' ? getCardReplacementText(primaryCard) : ''
    const sourceHtml = action === 'replace'
      ? `<span class="hl-source-strike">${escapeHtml(sourceText)}</span>`
      : escapeHtml(sourceText)
    const replaceSuffix = action === 'replace' && replacementText
      ? `<span class="hl-replace-target">[${escapeHtml(replacementText)}]</span>`
      : ''
    const replacement = `<span class="${baseClass} ${actionClass}" data-card-id="${primaryCard.id}"${tooltipAttr}>${sourceHtml}${replaceSuffix}${promptIcon}${badge}${collaborationStatus}</span>`
    parts.push(replacement)
    cursor = safeEnd
  }

  parts.push(escapeHtml(text.slice(cursor)))
  const html = parts.join('')
  highlightHtmlCache.value[field] = { signature: cacheSignature, html }
  return html
}

const getClosestTooltipChip = (target) => {
  const element = target?.nodeType === Node.ELEMENT_NODE ? target : target?.parentElement
  if (!element?.closest) return null
  return element.closest('.hl-chip[data-tooltip]')
}

const hideHighlightTooltip = () => {
  activeTooltipAnchor = null
  highlightTooltip.value.visible = false
  highlightTooltip.value.title = ''
  highlightTooltip.value.text = ''
}

const showHighlightTooltip = async (chipEl) => {
  const tooltipText = normalizeInputText(chipEl?.dataset?.tooltip)
  const tooltipTitle = normalizeInputText(chipEl?.dataset?.tooltipTitle)
  if (!chipEl || !tooltipText) {
    hideHighlightTooltip()
    return
  }

  activeTooltipAnchor = chipEl
  highlightTooltip.value.visible = true
  highlightTooltip.value.title = tooltipTitle
  highlightTooltip.value.text = tooltipText

  await nextTick()
  if (activeTooltipAnchor !== chipEl) return

  const tooltipEl = highlightTooltipRef.value
  const reportSheetEl = reportSheetRef.value
  const sheetBodyEl = sheetBodyRef.value
  if (!tooltipEl || !reportSheetEl) return

  const chipRect = chipEl.getBoundingClientRect()
  const reportSheetRect = reportSheetEl.getBoundingClientRect()
  const sheetBodyRect = sheetBodyEl?.getBoundingClientRect() || reportSheetRect
  const tooltipWidth = tooltipEl.offsetWidth || 0
  const tooltipHeight = tooltipEl.offsetHeight || 0
  const viewportPadding = 12
  const offset = 12

  const boundaryLeft = Math.max(reportSheetRect.left, sheetBodyRect.left) + viewportPadding
  const boundaryRight = Math.min(reportSheetRect.right, sheetBodyRect.right) - viewportPadding
  const boundaryTop = Math.max(reportSheetRect.top, sheetBodyRect.top) + viewportPadding
  const boundaryBottom = Math.min(reportSheetRect.bottom, sheetBodyRect.bottom) - viewportPadding

  let left = chipRect.left + (chipRect.width / 2) - (tooltipWidth / 2)
  left = Math.max(boundaryLeft, Math.min(left, boundaryRight - tooltipWidth))

  let top = chipRect.top - tooltipHeight - offset
  if (top < boundaryTop) {
    top = chipRect.bottom + offset
  }
  top = Math.max(boundaryTop, Math.min(top, boundaryBottom - tooltipHeight))

  highlightTooltip.value.left = Math.max(viewportPadding, left - reportSheetRect.left)
  highlightTooltip.value.top = Math.max(viewportPadding, top - reportSheetRect.top)
}

const handleHighlightTooltipMove = (event) => {
  const chipEl = getClosestTooltipChip(event.target)
  if (!chipEl) {
    if (highlightTooltip.value.visible) hideHighlightTooltip()
    return
  }
  if (activeTooltipAnchor === chipEl && highlightTooltip.value.visible) return
  showHighlightTooltip(chipEl)
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
  if (!cardId || cardId === '__remote-collaboration__') return
  selectedCardId.value = cardId
  scrollToCard(cardId)
}

const cardToErrorItem = (card) => {
  const processMethod = normalizeProcessMethodByErrorType(card.error_type, card.process_method)
  const replacementContent = processMethod === PROCESS_METHOD.replace ? normalizeInputText(card.target) : ''
  return {
    error_type: card.error_type || '',
    severity: card.severity || riskByErrorType(card.error_type || ''),
    location: fieldText(card.content_type),
    evidence_text: card.source || '',
    description: getCardSuggestionText(card),
    suggestion: replacementContent,
    process_method: processMethod,
    replacement_content: replacementContent,
    anchor: {
      content_type: normalizeContentType(card.content_type),
      source_in_start: card.source_in_start,
      source_in_end: card.source_in_end,
      alert_type: card.alert_type,
      source: card.source,
      target: replacementContent,
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

const loadReports = async (options = {}) => {
  const { silent = false } = options
  const requestSeq = ++reportListLoadRequestSeq
  const params = {
    tab: 'all',
    page: 1,
    page_size: DOCTOR_LIST_PAGE_SIZE,
    only_mine: props.isAdminMode ? false : onlyMine.value,
    lite: true
  }
  if (reportQuery.value) params.q = reportQuery.value

  const res = await api.getDoctorReports(params)
  if (requestSeq !== reportListLoadRequestSeq) return
  allReportList.value = res.items || []

  syncReportCollectionsFromAllReports()

  if (silent) {
    const currentRow = currentReport.value
      ? reportList.value.find((item) => item.id === currentReport.value.id)
      : null
    doctorTableRef.value?.setCurrentRow(currentRow || null)
    return
  }

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
      clearCurrentReport()
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
      const importedErrorType = item.err_type || 'typos'
      const importedTarget = normalizeInputText(item.target)
      const importedSuggestionText = normalizeInputText(
        item.alert_message || item.alert_msg || item.description || item.suggestion_message || item.suggestion_note || ''
      )
      const card = {
        id: `pre-${report.id}-${idx}`,
        kind: 'pre',
        origin_kind: 'pre',
        state: 'pending',
        content_type: item.content_type || '',
        source: item.source || '',
        target: shouldPrefillTargetByErrorType(importedErrorType) ? importedTarget : '',
        alert_type: String(item.alert_type ?? '2'),
        alert_message: importedSuggestionText,
        error_type: importedErrorType,
        severity: riskByErrorType(importedErrorType),
        source_in_start: item.source_in_start,
        source_in_end: item.source_in_end,
        process_method: PROCESS_METHOD.prompt,
        manual_override: false,
        action: 'prompt'
      }
      card.process_method = normalizeProcessMethodByErrorType(card.error_type, item.process_method || inferProcessMethodFromImportedData(card))
      applyProcessMethodInputState(card)

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
    const importedSuggestionText = normalizeInputText(item.description || '')
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
      alert_message: importedSuggestionText,
      error_type: item.error_type || 'typos',
      severity: riskByErrorType(item.error_type || 'typos'),
      source_in_start: item.anchor?.source_in_start,
      source_in_end: item.anchor?.source_in_end,
      process_method: normalizeProcessMethodByErrorType(item.error_type || 'typos', rawProcessMethod),
      manual_override: false,
      action: normalizeAction(item.anchor?.action)
    }

    if (!normalizeInputText(rawProcessMethod)) {
      card.process_method = inferProcessMethodFromImportedData(card)
    }
    applyProcessMethodInputState(card)
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
  const previousReportId = currentReport.value?.id
  if (previousReportId && previousReportId !== report.id) {
    clearLocalCollaborationActivity()
    await releaseCollaboration(previousReportId, { silent: true })
  }

  const detail = await api.getDoctorReport(report.id)
  await applyReportDetail(detail, {
    keepSelectedCard: false,
    tableRow: report
  })
  await startCollaborationRealtime()
}

const updateCurrentReportStatusLocally = (status, options = {}) => {
  const { refreshCollections = true } = options
  if (!currentReport.value) return
  currentReport.value.status = status
  const row = allReportList.value.find((item) => item.id === currentReport.value.id) || reportList.value.find((item) => item.id === currentReport.value.id)
  if (row) row.status = status
  if (refreshCollections) {
    syncReportCollectionsFromAllReports()
  }
}

const updateCurrentAnnotationStatusLocally = (status, options = {}) => {
  const { refreshCollections = true } = options
  if (!currentReport.value) return
  currentReport.value.annotation_status = status
  if (currentReport.value.annotation) {
    currentReport.value.annotation.status = status
  }
  const row = allReportList.value.find((item) => item.id === currentReport.value.id) || reportList.value.find((item) => item.id === currentReport.value.id)
  if (row) {
    row.annotation_status = status
  }
  if (refreshCollections) {
    syncReportCollectionsFromAllReports()
  }
}

const markCurrentReportSubmittedLocally = () => {
  if (!currentReport.value) return
  if (['REVIEW_ASSIGNED', 'REVIEW_IN_PROGRESS'].includes(resolveBaseStatus(currentReport.value))) {
    updateCurrentReportStatusLocally('DONE', { refreshCollections: false })
    updateCurrentAnnotationStatusLocally('SUBMITTED', { refreshCollections: false })
    syncReportCollectionsFromAllReports()
    return
  }
  if (isAdminImportedReport(currentReport.value)) {
    updateCurrentAnnotationStatusLocally('SUBMITTED', { refreshCollections: false })
    syncReportCollectionsFromAllReports()
    return
  }
  updateCurrentReportStatusLocally('SUBMITTED', { refreshCollections: false })
  updateCurrentAnnotationStatusLocally('SUBMITTED', { refreshCollections: false })
  syncReportCollectionsFromAllReports()
}

const autoSaveAfterInteraction = async () => {
  if (!currentReport.value || isEditingLocked.value) return
  noteLocalEditActivity()
  if (autoSaving.value) {
    autoSavePending.value = true
    return
  }
  autoSaving.value = true
  try {
    const response = await api.saveDraft(currentReport.value.id, buildPayload())
    setCurrentAnnotationUpdatedAt(response?.saved_at || new Date().toISOString())
    if (currentReport.value.status === 'ASSIGNED') {
      updateCurrentReportStatusLocally('IN_PROGRESS')
      updateCurrentAnnotationStatusLocally('DRAFT')
    } else if (currentReport.value.status === 'REVIEW_ASSIGNED') {
      updateCurrentReportStatusLocally('REVIEW_IN_PROGRESS')
      updateCurrentAnnotationStatusLocally('DRAFT')
    } else if (isAdminImportedReport(currentReport.value)) {
      updateCurrentAnnotationStatusLocally('DRAFT')
    }
  } catch (e) {
    await syncCollaboration('view', { silent: true, reportId: currentReport.value?.id })
    ElMessage.error(e.message || '自动暂存失败')
  } finally {
    autoSaving.value = false
    if (autoSavePending.value) {
      autoSavePending.value = false
      await autoSaveAfterInteraction()
    }
  }
}

const editCard = async (card) => {
  const hasAccess = await ensureEditAccess('修改标注')
  if (!hasAccess) return
  card.process_method = normalizeProcessMethodByErrorType(card.error_type, card.process_method || actionToProcessMethod(card.action))
  card.manual_override = !!card.manual_override
  card._targetValidationError = ''
  applyProcessMethodInputState(card)
  card._backup = { ...card }
  card.state = 'editing'
  selectedCardId.value = card.id
  setLocalCollaborationActivity(buildCollaborationActivityFromCard(card))
  await publishLocalCollaborationActivity()
}

const hasValidCardRange = (card) => {
  const start = Number.parseInt(card?.source_in_start, 10)
  const end = Number.parseInt(card?.source_in_end, 10)
  return Number.isInteger(start) && Number.isInteger(end) && start >= 0 && end > start
}

const prepareCardForSave = async (card, options = {}) => {
  card.target = normalizeInputText(card.target)
  card.process_method = normalizeProcessMethodByErrorType(card.error_type, card.process_method)
  card.manual_override = !!card.manual_override
  card._targetValidationError = ''
  applyDefaultSeverity(card)

  if (card.kind === 'manual' && !hasValidCardRange(card)) {
    ElMessage.warning('当前标注未获取到稳定文本索引，请重新选择文本后再标注')
    return false
  }

  if (card.process_method === PROCESS_METHOD.replace && !normalizeInputText(card.target)) {
    card._targetValidationError = '请填写替换内容'
    return false
  }

  syncCardSuggestion(card, { replacementText: card.target })
  syncActionToAlertType(card)

  return true
}

const saveCard = async (card) => {
  const hasAccess = await ensureEditAccess('保存标注')
  if (!hasAccess) return
  const canSave = await prepareCardForSave(card)
  if (!canSave) return
  if (card.kind === 'pre') {
    card.kind = 'manual'
    card.origin_kind = 'pre'
    unmarkPreCardDismissed(currentReport.value?.id, card)
  }
  card.state = 'saved'
  card._backup = null
  clearLocalCollaborationActivity()
  await publishLocalCollaborationActivity()
  await autoSaveAfterInteraction()
}

const cancelEdit = async (card) => {
  if (card._backup) {
    Object.assign(card, card._backup)
  }
  card._backup = null
  clearLocalCollaborationActivity()
  await publishLocalCollaborationActivity()
}

const deleteCard = async (card) => {
  if (!currentReport.value) return
  const hasAccess = await ensureEditAccess('删除标注')
  if (!hasAccess) return
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
  clearLocalCollaborationActivity()
  await publishLocalCollaborationActivity()
  await autoSaveAfterInteraction()
}

const confirmPreCard = async (card) => {
  const hasAccess = await ensureEditAccess('确认预标注')
  if (!hasAccess) return
  const canSave = await prepareCardForSave(card, {
    allowAutoSuggestionWhenEmpty: true
  })
  if (!canSave) return
  card.kind = 'manual'
  card.origin_kind = 'pre'
  unmarkPreCardDismissed(currentReport.value?.id, card)
  card.state = 'saved'
  card._backup = null
  clearLocalCollaborationActivity()
  await publishLocalCollaborationActivity()
  await autoSaveAfterInteraction()
}

const readCurrentSelectionContext = () => {
  const selection = window.getSelection()
  const selectedTextRaw = selection?.toString() || ''
  if (!selectedTextRaw.trim()) {
    return null
  }

  const selectedText = selectedTextRaw
  const range = selection.rangeCount > 0 ? selection.getRangeAt(0) : null
  if (!range) return null
  const anchorEl = selection.anchorNode?.nodeType === Node.ELEMENT_NODE
    ? selection.anchorNode
    : selection.anchorNode?.parentElement
  const commonAncestorEl = range
    ? (range.commonAncestorContainer?.nodeType === Node.ELEMENT_NODE
      ? range.commonAncestorContainer
      : range.commonAncestorContainer?.parentElement)
    : null
  const fieldBlock = commonAncestorEl?.closest('[data-field]') || anchorEl?.closest('[data-field]')
  if (!fieldBlock || !reportSheetRef.value?.contains(fieldBlock)) {
    return null
  }
  const field = fieldBlock.dataset?.field || 'description'
  const contentEl = fieldBlock?.querySelector('.section-content') || null
  if (
    !contentEl ||
    !contentEl.contains(range.startContainer) ||
    !contentEl.contains(range.endContainer)
  ) {
    return null
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
      container.querySelectorAll(
        '.hl-badge-stack, .hl-mark, .hl-prompt-icon, .hl-prompt-triangle, .hl-collab-status, .hl-replace-target, .hl-chip.missing'
      ).forEach((el) => el.remove())
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

  return {
    selection,
    selectedText,
    field,
    sourceInStart,
    sourceInEnd
  }
}

const commitSelectionContext = async (selectionContext) => {
  if (!currentReport.value || requiresDistributionBeforeAnnotation.value || isViewOnlyAccessibleReport.value) return
  setLocalCollaborationActivity(buildCollaborationActivityFromSelection(selectionContext))
  localSelectionActivityHoldUntil = Date.now() + LOCAL_SELECTION_ACTIVITY_HOLD_MS
  await publishLocalCollaborationActivity()
}

const syncSelectionClearToCollaboration = async () => {
  if (!currentReport.value || requiresDistributionBeforeAnnotation.value || isViewOnlyAccessibleReport.value) return
  if (localCollaborationActivity.value?.status !== 'selecting') return
  const remainingHoldMs = localSelectionActivityHoldUntil - Date.now()
  if (remainingHoldMs > 0) {
    clearCollaborationSelectionSyncTimer()
    collaborationSelectionSyncTimer = window.setTimeout(() => {
      void syncSelectionClearToCollaboration()
    }, remainingHoldMs)
    return
  }
  clearLocalCollaborationActivity()
  await publishLocalCollaborationActivity()
}

const handleSectionSelectionMouseUp = async () => {
  const selectionContext = readCurrentSelectionContext()
  if (!selectionContext) return
  await commitSelectionContext(selectionContext)
}

const handleDocumentMouseUp = async (event) => {
  const eventTarget = event?.target
  if (eventTarget?.closest?.('.section-content')) return
  const selectionContext = readCurrentSelectionContext()
  if (!selectionContext) return
  await commitSelectionContext(selectionContext)
}

const handleDocumentSelectionChange = () => {
  clearCollaborationSelectionSyncTimer()
  collaborationSelectionSyncTimer = window.setTimeout(() => {
    void (async () => {
      const selectionContext = readCurrentSelectionContext()
      if (!selectionContext) {
        await syncSelectionClearToCollaboration()
        return
      }
      const nextActivity = buildCollaborationActivityFromSelection(selectionContext)
      const nextSignature = buildActivityRenderSignature(nextActivity)
      const currentSignature = buildActivityRenderSignature(localCollaborationActivity.value)
      if (nextSignature === currentSignature) return
      setLocalCollaborationActivity(nextActivity)
      await publishLocalCollaborationActivity()
    })()
  }, COLLABORATION_SELECTION_SYNC_DEBOUNCE_MS)
}

const createManualCardFromSelection = async () => {
  if (!currentReport.value) {
    ElMessage.warning('请先选择一条报告')
    return
  }
  const selectionContext = readCurrentSelectionContext()
  if (!selectionContext) {
    ElMessage.warning('请先在中间报告中选中要标注的文本')
    return
  }
  if (
    !Number.isInteger(selectionContext.sourceInStart) ||
    !Number.isInteger(selectionContext.sourceInEnd) ||
    selectionContext.sourceInStart < 0 ||
    selectionContext.sourceInEnd <= selectionContext.sourceInStart
  ) {
    ElMessage.warning('当前选区未能计算出文本索引，请重新选择纯文本区域后再标注')
    return
  }
  setLocalCollaborationActivity(buildCollaborationActivityFromSelection(selectionContext))
  const hasAccess = await ensureEditAccess('开始标注')
  if (!hasAccess) {
    clearLocalCollaborationActivity()
    return
  }

  const now = Date.now()
  const newCard = {
    id: `manual-${currentReport.value.id}-${now}`,
    kind: 'manual',
    origin_kind: 'manual',
    state: 'editing',
    content_type: selectionContext.field,
    source: selectionContext.selectedText,
    target: '',
    alert_type: '2',
    alert_message: '',
    error_type: 'typos',
    severity: riskByErrorType('typos'),
    source_in_start: selectionContext.sourceInStart,
    source_in_end: selectionContext.sourceInEnd,
    process_method: getDefaultProcessMethodByErrorType('typos'),
    manual_override: false,
    action: 'replace'
  }
  applyProcessMethodInputState(newCard)

  cards.value.push(newCard)
  selectedCardId.value = newCard.id
  setLocalCollaborationActivity(buildCollaborationActivityFromCard(newCard))
  await publishLocalCollaborationActivity()
  scrollToCard(newCard.id)
}

const isShortcutInputTarget = (target) => {
  if (!(target instanceof HTMLElement)) return false
  const tagName = String(target.tagName || '').toLowerCase()
  const inWorkbenchDialog = !!target.closest('.workbench-dialog')
  if (target.isContentEditable) return true
  if (['input', 'textarea', 'select'].includes(tagName)) return true
  if (target.closest('[contenteditable="true"]')) return true
  if (target.closest('.el-message-box')) return true
  if (!inWorkbenchDialog && target.closest('.el-dialog, .el-drawer')) return true
  return false
}

const handleDocumentKeydown = (event) => {
  if (event.defaultPrevented || event.isComposing || event.repeat) return
  if (event.ctrlKey || event.metaKey || event.altKey) return
  const activeElement = document.activeElement instanceof HTMLElement ? document.activeElement : null
  const eventTarget = event.target instanceof HTMLElement ? event.target : null
  if (isShortcutInputTarget(activeElement || eventTarget)) return

  const key = String(event.key || '').trim().toLowerCase()
  const code = String(event.code || '').trim()
  if (key === 'q' || code === 'KeyQ') {
    if (isEditingLocked.value) return
    event.preventDefault()
    void createManualCardFromSelection()
    return
  }
  if (key === 's' || code === 'KeyS') {
    if (!canSubmitCurrentReport.value || submitting.value) return
    event.preventDefault()
    void submitReport()
    return
  }
  if (key === 'd' || code === 'KeyD') {
    if (!showCancelAnnotationButton.value || isCancelAnnotationActionDisabled.value) return
    event.preventDefault()
    void handleCancelAnnotationAction()
  }
}

const remindUnsubmitted = async (offset = 1) => {
  if (!currentReport.value || !isDraftWorkflowStatus(currentDisplayStatus.value)) return 'pass'
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

  if (intent === 'submit' && currentReport.value && canSubmitCurrentReport.value) {
    const hasAccess = await ensureEditAccess(submitButtonText.value)
    if (!hasAccess) return
    const cardsReady = await ensureCardsReadyBeforeSubmit()
    if (!cardsReady) return
    const canSubmit = await ensurePreCardsReadyBeforeSubmit()
    if (!canSubmit) return
    try {
      clearLocalCollaborationActivity()
      await publishLocalCollaborationActivity()
      const response = await api.submitAnnotation(currentReport.value.id, buildPayload())
      setCurrentAnnotationUpdatedAt(response?.submitted_at || new Date().toISOString())
      markCurrentReportSubmittedLocally()
      await loadReports()
    } catch (e) {
      await syncCollaboration('view', { silent: true, reportId: currentReport.value?.id })
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
  const reportId = currentReport.value?.id
  if (reportId) {
    releaseCollaboration(reportId, { silent: true })
  } else {
    stopCollaborationSocket()
  }
  hideHighlightTooltip()
  currentReport.value = null
  collaborationState.value = null
  collaborationUnavailable.value = false
  collaborationUnavailableNotified.value = false
  localCollaborationActivity.value = null
  localSelectionActivityHoldUntil = 0
  lastPublishedActivitySignature = ''
  currentAnnotationUpdatedAt.value = null
  remoteAnnotationRefreshing.value = false
  clearHighlightHtmlCache()
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
  if (currentDisplayStatus.value === 'REVIEW_ASSIGNED') return true
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
  const hasAccess = await ensureEditAccess(submitButtonText.value)
  if (!hasAccess) return
  const cardsReady = await ensureCardsReadyBeforeSubmit()
  if (!cardsReady) return
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
    clearLocalCollaborationActivity()
    await publishLocalCollaborationActivity()
    const response = await api.submitAnnotation(currentReport.value.id, buildPayload())
    setCurrentAnnotationUpdatedAt(response?.submitted_at || new Date().toISOString())
    markCurrentReportSubmittedLocally()
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
    await syncCollaboration('view', { silent: true, reportId: currentReport.value?.id })
    ElMessage.error(e.message || '完成标注失败')
  } finally {
    submitting.value = false
  }
}

const cancelSubmittedAnnotation = async () => {
  if (!currentReport.value || !showCancelAnnotationButton.value) return
  const reportIsReviewTask = isReviewTask(currentReport.value)
  const actionText = reportIsReviewTask ? '取消复核' : '取消标注'
  const hasAccess = await ensureEditAccess(actionText)
  if (!hasAccess) return
  const reportId = currentReport.value.id
  const previousFilter = activeFilter.value
  const confirmText = reportIsReviewTask
    ? '取消后，当前报告将回到待复核状态，是否继续？'
    : '取消后，当前报告将回到待标注状态，是否继续？'
  const titleText = reportIsReviewTask ? '取消复核确认' : '取消标注确认'
  const successText = reportIsReviewTask
    ? '已取消复核，当前报告已回到待复核状态'
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
    clearLocalCollaborationActivity()
    await publishLocalCollaborationActivity()
    await api.cancelAnnotation(reportId)
    setCurrentAnnotationUpdatedAt(new Date().toISOString())
    ElMessage.success(successText)
    await loadReports()
    if (previousFilter === 'annotated' && reportList.value.length === 0) {
      activeFilter.value = 'unannotated'
      await loadReports()
    } else if (previousFilter === 'reviewed' && reportList.value.length === 0) {
      activeFilter.value = 'review'
      await loadReports()
    }
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

const handleCancelAnnotationAction = async () => {
  if (isCancelAnnotationBlockedByReview.value) {
    ElMessage.warning('该报告已被二次分发复核，无法取消标注')
    return
  }
  await cancelSubmittedAnnotation()
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
  clearCardFocus()
  hideHighlightTooltip()
  clearCollaborationSelectionSyncTimer()
  stopReportUpdatesSocket()
  if (typeof window !== 'undefined') {
    window.removeEventListener('resize', handleWindowResize)
    window.removeEventListener('keydown', handleDocumentKeydown, true)
  }
  if (typeof document !== 'undefined') {
    document.removeEventListener('visibilitychange', handleDocumentVisibilityChange)
    document.removeEventListener('mouseup', handleDocumentMouseUp)
    document.removeEventListener('selectionchange', handleDocumentSelectionChange)
  }
  releaseCollaboration(currentReport.value?.id, { silent: true })
})

onMounted(async () => {
  try {
    currentUser.value = api.getCurrentUser() || await api.getMe()
    restoreVisibleColumnKeys()
    restoreDismissedPreCardKeys()
    if (typeof window !== 'undefined') {
      window.addEventListener('resize', handleWindowResize)
      window.addEventListener('keydown', handleDocumentKeydown, true)
    }
    if (typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', handleDocumentVisibilityChange)
      document.addEventListener('mouseup', handleDocumentMouseUp)
      document.addEventListener('selectionchange', handleDocumentSelectionChange)
    }
    if (props.isAdminMode) {
      onlyMine.value = false
    }
    await loadReports()
    startReportUpdatesSocket()
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
  color: #374151;
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

.action-shortcut-hint {
  width: 100%;
  text-align: right;
  font-size: 12px;
  color: #6b7280;
}

.auto-next-toggle {
  margin-right: 2px;
}

.report-sheet-shell {
  position: relative;
  flex: 1;
  min-height: 0;
}

.report-sheet {
  position: relative;
  height: 100%;
  flex: 1;
  overflow: auto;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
  color: #374151;
  font-size: 16px;
}

.report-sheet-tooltip-layer {
  position: absolute;
  inset: 0;
  overflow: hidden;
  pointer-events: none;
  border-radius: 8px;
  z-index: 8;
}

.sheet-head {
  border-bottom: 1px solid #e5e7eb;
  padding: 12px;
  color: #374151;
  font-size: 16px;
  line-height: 1.75;
}

.sheet-head h2 {
  margin: 0 0 4px 0;
  color: #374151;
  font-size: 24px;
  line-height: 1.35;
  font-weight: 700;
}

.sheet-meta-line {
  margin-top: 2px;
}

.distribution-warning-strip {
  margin-top: 10px;
  padding: 10px 12px;
  border: 1px solid #fcd34d;
  border-radius: 10px;
  background: #fffbeb;
  color: #b45309;
  font-size: 13px;
  line-height: 1.6;
}

.collaboration-strip {
  margin-top: 10px;
  padding: 10px 12px;
  border: 1px solid #dbe7f5;
  border-radius: 10px;
  background: linear-gradient(135deg, #f8fbff 0%, #eef6ff 100%);
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}

.collaboration-users {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.collaboration-label {
  font-size: 12px;
  color: #475569;
}

.collaboration-user {
  display: inline-flex;
  align-items: center;
  padding: 4px 10px;
  border-radius: 999px;
  background: #ffffff;
  border: 1px solid #dbe7f5;
  color: #1e3a5f;
  font-size: 12px;
  line-height: 1.2;
}

.collaboration-user.me {
  border-color: #93c5fd;
  color: #1d4ed8;
}

.collaboration-user.editor {
  background: #dbeafe;
  border-color: #60a5fa;
  color: #1d4ed8;
  font-weight: 600;
}

.collaboration-empty {
  color: #64748b;
  font-size: 12px;
}

.collaboration-state {
  font-size: 12px;
  color: #475569;
}

.collaboration-state.locked {
  color: #b45309;
  font-weight: 600;
}

.sheet-body {
  padding: 12px;
  color: #374151;
  font-size: 17px;
  line-height: 2;
}

.section-block {
  margin-bottom: 16px;
}

.section-block h3 {
  margin: 0 0 8px 0;
  color: #111827;
  font-size: 19px;
  line-height: 1.5;
  font-weight: 700;
}

.section-content {
  color: #374151;
  font-size: 17px;
  line-height: 2;
  font-weight: 500;
  white-space: pre-wrap;
}

.section-content :deep(.hl-chip) {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 1px 6px 1px 4px;
  border-radius: 4px;
  border: 2px solid transparent;
  cursor: pointer;
}

.floating-highlight-tooltip {
  position: absolute;
  max-width: 320px;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid #f59e0b;
  background: #fff4bf;
  color: #7c2d12;
  font-size: 14px;
  line-height: 1.6;
  font-weight: 600;
  box-shadow: 0 14px 32px rgba(245, 158, 11, 0.22);
  pointer-events: none;
  z-index: 1200;
}

.floating-highlight-tooltip-title {
  margin-bottom: 6px;
  color: #991b1b;
  font-size: 15px;
  line-height: 1.4;
  font-weight: 900;
  letter-spacing: 0.01em;
}

.floating-highlight-tooltip-body {
  white-space: pre-wrap;
}

.section-content :deep(.hl-chip.pre) {
  background: #fef3c7;
  color: #92400e;
  border-color: #f59e0b;
}

.section-content :deep(.hl-chip.manual) {
  background: #dbeafe;
  color: #1e40af;
  border-color: #60a5fa;
}

.section-content :deep(.hl-chip.hl-collaboration-live) {
  background: rgba(254, 226, 226, 0.9);
  color: #991b1b;
  border: 2px dashed #ef4444;
  box-shadow: 0 0 0 2px rgba(239, 68, 68, 0.12);
}

.section-content :deep(.hl-chip.hl-delete) {
  text-decoration: line-through;
  text-decoration-thickness: 2px;
  background: #fee2e2;
  color: #991b1b;
  border-color: #ef4444;
}

.section-content :deep(.hl-chip.hl-replace) {
  background: #fee2e2;
  color: #991b1b;
  border-color: #ef4444;
  font-weight: 600;
}

.section-content :deep(.hl-chip.hl-prompt) {
  background: #dbeafe;
  color: #1e40af;
  border-color: #60a5fa;
  font-weight: 600;
}

.section-content :deep(.hl-source-strike) {
  text-decoration: line-through;
  text-decoration-thickness: 2px;
}

.section-content :deep(.hl-replace-target) {
  color: #dc2626;
  font-weight: 700;
}

.section-content :deep(.hl-chip.missing) {
  background: #fff7ed;
  color: #b45309;
  border: 2px dashed #f59e0b;
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
  background: #2563eb;
  clip-path: polygon(50% 0%, 0% 100%, 100% 100%);
}

.section-content :deep(.hl-badge-stack) {
  display: inline-flex;
  align-items: flex-start;
  gap: 4px;
}

.section-content :deep(.hl-mark) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 14px;
  height: 14px;
  line-height: 1;
  border-radius: 999px;
  font-size: 10px;
  color: #fff;
  background: #ef4444;
  transform: translateY(-35%);
  flex: 0 0 auto;
}

.section-content :deep(.hl-collab-status) {
  display: inline-flex;
  align-items: center;
  margin-left: 6px;
  padding: 1px 7px;
  border-radius: 999px;
  border: 1px solid rgba(239, 68, 68, 0.32);
  background: rgba(254, 226, 226, 0.96);
  color: #b91c1c;
  font-size: 11px;
  line-height: 1.4;
  font-weight: 700;
}

@keyframes chip-focus-pulse {
  0% { transform: scale(1); }
  50% { transform: scale(1.05); }
  100% { transform: scale(1); }
}

@keyframes card-focus-pulse {
  0% { box-shadow: inset 0 0 0 1px rgba(220, 38, 38, 0.2), 0 0 0 0 rgba(220, 38, 38, 0.08); }
  50% { box-shadow: inset 0 0 0 3px rgba(220, 38, 38, 0.72), 0 0 0 2px rgba(220, 38, 38, 0.14); }
  100% { box-shadow: inset 0 0 0 1px rgba(220, 38, 38, 0.2), 0 0 0 0 rgba(220, 38, 38, 0.08); }
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
  position: relative;
  cursor: pointer;
}

.error-card.selected {
  border-color: #3b82f6;
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.12);
}

.error-card.card-focus {
  border-color: #dc2626;
  box-shadow: inset 0 0 0 2px rgba(220, 38, 38, 0.58);
  animation: card-focus-pulse 0.9s ease-in-out 2;
}

.card-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-head-main {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.error-type-badge-wrap {
  position: relative;
  display: inline-flex;
  align-items: center;
  padding-right: 6px;
}

.card-index {
  position: absolute;
  top: -7px;
  right: -8px;
  display: flex;
  align-items: center;
  justify-content: center;
  min-width: 14px;
  height: 14px;
  line-height: 14px;
  border-radius: 999px;
  text-align: center;
  font-size: 10px;
  color: #fff;
  background: #ef4444;
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

.level-title {
  margin-bottom: 6px;
  font-size: 12px;
  color: #6b7280;
}

.severity-group {
  display: flex;
  width: 100%;
  margin-bottom: 8px;
}

.severity-btn {
  flex: 1;
  height: 32px;
  border: 1px solid #d1d5db;
  border-right: none;
  background: #ffffff;
  color: #374151;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.severity-btn:first-child {
  border-radius: 6px 0 0 6px;
}

.severity-btn:last-child {
  border-right: 1px solid #d1d5db;
  border-radius: 0 6px 6px 0;
}

.severity-btn-low {
  background: #f0fdf4;
  border-color: #86efac;
  color: #15803d;
}

.severity-btn-medium {
  background: #fffbeb;
  border-color: #fcd34d;
  color: #b45309;
}

.severity-btn-high {
  background: #fef2f2;
  border-color: #fca5a5;
  color: #b91c1c;
}

.severity-btn:disabled {
  cursor: not-allowed;
  opacity: 1;
}

.severity-btn.active {
  position: relative;
  z-index: 1;
  color: #ffffff;
}

.severity-btn-low.active {
  border-color: #16a34a;
  background: #22c55e;
}

.severity-btn-medium.active {
  border-color: #d97706;
  background: #f59e0b;
}

.severity-btn-high.active {
  border-color: #dc2626;
  background: #ef4444;
}

.severity-btn-low.active + .severity-btn {
  border-left-color: #16a34a;
}

.severity-btn-medium.active + .severity-btn {
  border-left-color: #d97706;
}

.severity-btn-high.active + .severity-btn {
  border-left-color: #dc2626;
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

.process-method-btn:disabled {
  cursor: not-allowed;
  opacity: 0.5;
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

.suggestion-readonly {
  min-height: 42px;
  padding: 8px 10px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  background: #f9fafb;
  color: #111827;
  line-height: 1.6;
  white-space: pre-wrap;
}

.error-type-emphasis {
  display: inline-flex;
  align-items: center;
  padding: 2px 10px;
  border-radius: 999px;
  background: #fee2e2;
  color: #b91c1c;
  font-size: 13px;
  font-weight: 700;
}

.error-type-emphasis.header {
  padding: 4px 12px;
  font-size: 14px;
}

.card-actions {
  margin-top: 8px;
  display: flex;
  gap: 8px;
}

.cancel-annotation-btn-blocked {
  color: #9ca3af !important;
  border-color: #d1d5db !important;
  background: #f3f4f6 !important;
  cursor: not-allowed;
  box-shadow: none;
  opacity: 1;
}

</style>
