<template>
  <el-dialog
    v-model="dialogVisible"
    title="报告详情"
    width="800px"
    :close-on-click-modal="false"
    class="report-view-dialog"
  >
    <div class="report-container" v-if="report">
      <!-- 医院标题 -->
      <div class="report-header">
        <h1 class="hospital-name">XX大学附属第一医院</h1>
        <h2 class="report-title">{{ reportTitle }}</h2>
      </div>

      <!-- 患者信息 -->
      <div class="patient-info">
        <div class="info-row">
          <span class="info-item">
            <span class="label">检查号：</span>
            <span class="value">{{ report.ris_no || report.external_id || '-' }}</span>
          </span>
          <span class="info-item">
            <span class="label">检查类型：</span>
            <span class="value">{{ report.modality || '-' }}</span>
          </span>
          <span class="info-item">
            <span class="label">患者姓名：</span>
            <span class="value">{{ report.patient_name || '***' }}</span>
          </span>
          <span class="info-item">
            <span class="label">性别：</span>
            <span class="value">{{ report.patient_sex || '-' }}</span>
          </span>
        </div>
        <div class="info-row">
          <span class="info-item full-width">
            <span class="label">项目：</span>
            <span class="value">{{ report.exam_item || '-' }}</span>
          </span>
        </div>
      </div>

      <!-- 报告内容区域 -->
      <div class="report-content">
        <!-- 检查所见 -->
        <div class="content-section">
          <h3 class="section-title">【检查所见】</h3>
          <div class="section-content" v-html="getHighlightedText('description')"></div>
        </div>

        <!-- 诊断意见 -->
        <div class="content-section">
          <h3 class="section-title">【诊断意见】</h3>
          <div class="section-content diagnosis-content" v-html="getHighlightedText('impression')"></div>
        </div>
      </div>

      <!-- 底部信息 -->
      <div v-if="suggestionList.length" class="suggestion-section">
        <h3 class="section-title">【预标注修改建议】</h3>
        <div v-for="(item, idx) in suggestionList" :key="idx" class="suggestion-item">
          <div>字段：{{ item.contentType }}</div>
          <div>错误类型：{{ item.errType }}</div>
          <div>错误内容：{{ item.source || "-" }}</div>
          <div>建议说明：{{ item.alertMessage || "-" }}</div>
        </div>
      </div>

      <div class="report-footer">
        <div class="footer-info">
          <span>报告医生：{{ report.doctor_username || '***' }}</span>
          <span v-if="report.assigned_doctor_id">工号：{{ report.doctor_employee_id || '***' }}</span>
        </div>
        <div class="footer-date">
          报告日期：{{ formatDate(report.imported_at) }}
        </div>
      </div>
    </div>
    <template #footer>
      <el-button @click="dialogVisible = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  report: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['update:modelValue'])

const dialogVisible = ref(false)

const reportTitle = computed(() => {
  const modality = props.report?.modality?.trim()
  const examItem = props.report?.exam_item?.trim()
  const titleCore = modality || examItem || '影像'
  return `${titleCore}检查报告单`
})

watch(() => props.modelValue, (val) => {
  dialogVisible.value = val
})

watch(dialogVisible, (val) => {
  emit('update:modelValue', val)
})

const formatDate = (dateStr) => {
  if (!dateStr) return '****-**-** **:**:**'
  const date = new Date(dateStr)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hour = String(date.getHours()).padStart(2, '0')
  const minute = String(date.getMinutes()).padStart(2, '0')
  const second = String(date.getSeconds()).padStart(2, '0')
  return `${year}-${month}-${day} ${hour}:${minute}:${second}`
}

// 错误类型映射
const ERR_TYPE_MAP = {
  'bodyParts': '部位错误',
  'examitems': '检查项目错误',
  'organectomys': '器官切除/缺如信息错误',
  'positions': '体位/位置错误',
  'sexs': '性别错误',
  'typo_modality': '检查类型错写',
  'typo_unit': '单位错写/错误',
  'typos': '错别字/拼写错误',
  'typoTerms': '术语错写/术语错误'
}

const CONTENT_TYPE_MAP = {
  description: 'description',
  desc: 'description',
  '检查所见': 'description',
  impression: 'impression',
  impress: 'impression',
  '诊断意见': 'impression'
}

const normalizeContentType = (contentType) => {
  if (!contentType) return ''
  const raw = String(contentType).trim()
  const lower = raw.toLowerCase()
  return CONTENT_TYPE_MAP[lower] || CONTENT_TYPE_MAP[raw] || ''
}

const resolveHighlightRange = (text, anno) => {
  const source = String(anno.source || '')
  const parsedStart = Number.parseInt(anno.source_in_start, 10)
  const parsedEnd = Number.parseInt(anno.source_in_end, 10)
  const candidates = []

  if (Number.isInteger(parsedStart)) {
    if (Number.isInteger(parsedEnd)) {
      candidates.push([parsedStart, parsedEnd], [parsedStart - 1, parsedEnd - 1])
    }
    if (source) {
      candidates.push(
        [parsedStart, parsedStart + source.length],
        [parsedStart - 1, parsedStart - 1 + source.length]
      )
    }
  }

  for (const [rawStart, rawEnd] of candidates) {
    const start = Math.max(0, rawStart)
    const end = Math.max(start, Math.min(text.length, rawEnd))
    if (!source) {
      return { start, end }
    }
    if (text.slice(start, end) === source) {
      return { start, end }
    }
  }

  if (source) {
    const fallbackIndex = text.indexOf(source)
    if (fallbackIndex !== -1) {
      return { start: fallbackIndex, end: fallbackIndex + source.length }
    }
  }
  return null
}

// 获取高亮文本
const getHighlightedText = (field) => {
  if (!props.report) return ''

  const preAnnos = props.report.pre_annotations || []
  if (preAnnos.length === 0) {
    // 没有预标注，直接返回原文
    return escapeHtml(props.report[field] || props.report.report_text || '无')
  }

  // 获取对应字段的文本
  let text = props.report[field] || ''

  if (!text) return '无'

  const matchedAnnos = preAnnos
    .filter((anno) => normalizeContentType(anno.content_type) === field.toLowerCase())
    .map((anno) => {
      const range = resolveHighlightRange(text, anno)
      return range ? { anno, ...range } : null
    })
    .filter(Boolean)
    .sort((a, b) => b.start - a.start)

  for (const item of matchedAnnos) {
    const anno = item.anno
    const source = anno.source || ''
    const alertType = anno.alert_type || ''
    const alertMsg = anno.alert_message || anno.alert_msg || ''
    const errType = ERR_TYPE_MAP[anno.err_type] || anno.err_type || '错误'

    if (!source) continue

    const start = item.start
    const end = item.end

    // 构建替换文本
    const highlightClass = alertType === '1' ? 'error-highlight delete' : 'error-highlight'
    const replaceHtml = `<span class="${highlightClass}" title="错误类型: ${errType}\n建议说明: ${escapeHtml(alertMsg)}">${escapeHtml(source)}</span>`

    // 替换文本
    if (start >= 0 && start < text.length) {
      text = text.substring(0, start) + replaceHtml + text.substring(end)
    }
  }

  return text
}

const suggestionList = computed(() => {
  const preAnnos = props.report?.pre_annotations || []
  return preAnnos.map((anno) => ({
    contentType: normalizeContentType(anno.content_type) === 'description'
      ? '检查所见'
      : normalizeContentType(anno.content_type) === 'impression'
        ? '诊断意见'
        : (anno.content_type || '未知字段'),
    errType: ERR_TYPE_MAP[anno.err_type] || anno.err_type || "错误",
    source: anno.source || "",
    alertMessage: anno.alert_message || anno.alert_msg || "",
  }))
})

// HTML转义
const escapeHtml = (text) => {
  if (!text) return ''
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
}
</script>

<style scoped>
.report-container {
  font-family: 'Noto Sans SC', 'Microsoft YaHei', sans-serif;
  color: #1e293b;
}

.report-header {
  text-align: center;
  border-bottom: 2px solid #334155;
  padding-bottom: 16px;
  margin-bottom: 24px;
}

.hospital-name {
  font-size: 24px;
  font-weight: bold;
  margin: 0 0 8px 0;
  color: #0f172a;
}

.report-title {
  font-size: 20px;
  font-weight: 500;
  margin: 0;
  color: #475569;
}

.patient-info {
  border-bottom: 1px dashed #cbd5e1;
  padding-bottom: 20px;
  margin-bottom: 24px;
}

.info-row {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 12px;
}

.info-row:last-child {
  margin-bottom: 0;
}

.info-item {
  display: flex;
  align-items: center;
  font-size: 14px;
}

.info-item.full-width {
  width: 100%;
}

.label {
  font-weight: 600;
  color: #0f172a;
}

.value {
  color: #334155;
}

.report-content {
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  overflow: hidden;
}

.content-section {
  padding: 20px;
}

.content-section:first-child {
  border-bottom: 1px solid #e2e8f0;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: #0f172a;
  margin: 0 0 12px 0;
  padding-left: 12px;
  border-left: 4px solid #2563eb;
}

.section-content {
  font-size: 15px;
  line-height: 1.8;
  color: #334155;
  white-space: pre-wrap;
  text-align: justify;
}

.diagnosis-content {
  background-color: #f8fafc;
  padding: 16px;
  border-radius: 6px;
  border: 1px solid #f1f5f9;
}

.report-footer {
  display: flex;
  justify-content: space-between;
  margin-top: 32px;
  padding-top: 16px;
  border-top: 1px solid #f1f5f9;
  font-size: 12px;
  color: #64748b;
}

.suggestion-section {
  margin-top: 20px;
}

.suggestion-item {
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 10px 12px;
  margin-top: 10px;
  font-size: 13px;
  line-height: 1.7;
}

.footer-info {
  display: flex;
  gap: 24px;
}

/* 预标注错误高亮样式 */
:deep(.error-highlight) {
  background-color: #ffcccc;
  color: #cc0000;
  padding: 2px 4px;
  border-radius: 3px;
  font-weight: 500;
  cursor: help;
}

:deep(.error-highlight.delete) {
  background-color: #ff9999;
  text-decoration: line-through;
}
</style>
