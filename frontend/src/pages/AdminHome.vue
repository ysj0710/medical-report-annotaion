<template>
  <div class="admin-page">
    <!-- 报告池 -->
    <div v-if="activeTab === 'reports'" class="panel">
      <div class="toolbar">
        <el-input
          v-model="reportQuery"
          placeholder="搜索报告编号/内容"
          clearable
          @keyup.enter="loadReports"
          style="width: 240px"
        />
        <el-select
          v-model="reportStatus"
          placeholder="全部状态"
          @change="handleStatusChange"
          style="width: 140px"
        >
          <el-option value="" label="全部状态" />
          <el-option value="IMPORTED" label="待分发" />
          <el-option value="ASSIGNED" label="已分发" />
          <el-option value="SUBMITTED" label="已提交" />
          <el-option value="DONE" label="已完成" />
        </el-select>
        <el-button @click="loadReports">查询</el-button>
        <el-button
          type="primary"
          @click="openAssignModal"
        >
          一键分发报告
        </el-button>
        <el-button
          type="danger"
          @click="batchDelete"
          :disabled="selectedReports.length === 0"
        >
          批量删除 ({{ selectedReports.length }})
        </el-button>
      </div>

      <el-table
        ref="tableRef"
        :data="reports"
        row-key="id"
        border
        stripe
        @selection-change="handleSelectionChange"
      >
        <el-table-column
          type="selection"
          :selectable="checkSelectable"
          width="50"
        />
        <el-table-column
          label="序号"
          width="70"
          :index="tableIndex"
          type="index"
        />
        <el-table-column label="检查号(RIS_NO)" prop="ris_no" width="140" />
        <el-table-column label="检查类型" prop="modality" width="100" />
        <el-table-column label="性别" prop="patient_sex" width="60" />
        <el-table-column label="年龄" prop="patient_age" width="70" />
        <el-table-column
          label="检查项目"
          prop="exam_item"
          show-overflow-tooltip
        />
        <el-table-column label="标注员" prop="doctor_username" width="100" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.status)">{{
              getStatusText(row.status)
            }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column
          label="导入时间"
          prop="imported_at"
          :formatter="formatTime"
          width="180"
        />
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="viewReport(row)"
              >查看</el-button
            >
            <el-button
              v-if="row.status === 'IMPORTED'"
              link
              type="danger"
              @click="deleteReport(row)"
              >删除</el-button
            >
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="reportPage"
          v-model:page-size="reportPageSize"
          :page-sizes="[10, 20, 50, 100]"
          :total="reportTotal"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="loadReports"
          @current-change="loadReports"
        />
      </div>
    </div>

    <!-- 导入 -->
    <div v-if="activeTab === 'import'" class="panel">
      <el-card>
        <template #header>
          <span>导入报告</span>
        </template>
        <el-alert
          title="支持格式说明"
          type="info"
          :closable="false"
          style="margin-bottom: 16px"
        >
          支持 .xlsx 和 .csv
          文件，必填列：RIS_NO(检查号)、检查类型(MODALITY)、性别(PATIENT_SEX)、年龄(PATIENT_AGE)、检查项目(EXAM_ITEM)、检查所见(DESCRIPTION)、诊断意见(IMPRESSION)
        </el-alert>
        <el-upload
          ref="uploadRef"
          :auto-upload="false"
          :limit="1"
          accept=".xlsx,.csv"
          :on-change="handleFileSelect"
        >
          <el-button type="primary">选择报告文件</el-button>
          <template #tip>
            <div class="el-upload__tip">原始报告文件（必填）</div>
          </template>
        </el-upload>
        <el-upload
          ref="preUploadRef"
          :auto-upload="false"
          :limit="1"
          accept=".xlsx,.csv"
          :on-change="handlePreFileSelect"
          style="margin-top: 16px"
        >
          <el-button type="warning">选择预标注文件</el-button>
          <template #tip>
            <div class="el-upload__tip">预标注文件（可选），包含错误标注信息</div>
          </template>
        </el-upload>
        <el-button
          type="success"
          @click="handleImport"
          :disabled="!importFile || importing"
          style="margin-top: 16px"
        >
          {{ importing ? "导入中..." : "开始导入" }}
        </el-button>
        <div v-if="importTask" class="import-result">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="任务状态">{{
              importTask.status
            }}</el-descriptions-item>
            <el-descriptions-item label="总行数">{{
              importTask.total_rows
            }}</el-descriptions-item>
            <el-descriptions-item label="成功">{{
              importTask.success_rows
            }}</el-descriptions-item>
            <el-descriptions-item label="失败">{{
              importTask.failed_rows
            }}</el-descriptions-item>
          </el-descriptions>
          <el-link
            v-if="importTask.error_report_path"
            type="danger"
            :href="'/api/reports/import-tasks/' + importTask.id + '/errors'"
            target="_blank"
            style="margin-top: 12px"
          >
            下载错误明细
          </el-link>
        </div>
      </el-card>
    </div>

    <!-- 用户管理 -->
    <div v-if="activeTab === 'users'" class="panel">
      <div class="toolbar">
        <el-button type="primary" @click="openUserModal()">新建用户</el-button>
      </div>
      <el-table :data="users" row-key="id" border stripe>
        <el-table-column label="序号" width="70" type="index" />
        <el-table-column label="工号" prop="employee_id" width="120" />
        <el-table-column label="用户名" prop="username" />
        <el-table-column label="角色" width="100">
          <template #default="{ row }">
            {{ getRoleText(row.role) }}
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'danger'">
              {{ row.enabled ? "启用" : "禁用" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="查看全部" width="120">
          <template #default="{ row }">
            <el-tag :type="row.can_view_all ? 'success' : 'info'">
              {{ row.can_view_all ? "是" : "否" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="300" fixed="right">
          <template #default="{ row }">
            <el-button link type="primary" @click="openUserModal(row)"
              >编辑</el-button
            >
            <el-button
              link
              :type="row.enabled ? 'danger' : 'success'"
              @click="toggleUser(row)"
            >
              {{ row.enabled ? "禁用" : "启用" }}
            </el-button>
            <el-button
              link
              :type="row.can_view_all ? 'warning' : 'success'"
              @click="toggleViewAll(row)"
            >
              {{ row.can_view_all ? "取消权限" : "授权查看" }}
            </el-button>
            <el-tag
              v-if="row.view_all_requested && !row.can_view_all"
              type="warning"
              size="small"
            >
              已申请
            </el-tag>
            <el-button link type="danger" @click="deleteUser(row)"
              >删除</el-button
            >
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 分发弹窗 -->
    <el-dialog v-model="showAssignModal" title="分发报告给医生" width="760px">
      <p>将自动分发全部待分发报告（IMPORTED）</p>
      <el-transfer
        v-model="assignDoctorIds"
        :data="doctorTransferData"
        :titles="['可选医生', '已选医生']"
        filterable
      />
      <template #footer>
        <el-button @click="showAssignModal = false">取消</el-button>
        <el-button
          type="primary"
          @click="handleAssign"
          :disabled="assignDoctorIds.length === 0"
          >确认分发</el-button
        >
      </template>
    </el-dialog>

    <!-- 用户弹窗 -->
    <el-dialog
      v-model="showUserModal"
      :title="editingUser ? '编辑用户' : '新建用户'"
      width="400px"
    >
      <el-form :model="userForm" label-width="60px">
        <el-form-item label="工号">
          <el-input v-model="userForm.employee_id" placeholder="请输入工号" />
        </el-form-item>
        <el-form-item label="用户名">
          <el-input v-model="userForm.username" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="userForm.password" type="password" show-password />
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="userForm.role" style="width: 100%">
            <el-option value="doctor" label="专家" />
            <el-option value="reviewer" label="复核人" />
            <el-option value="admin" label="管理员" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showUserModal = false">取消</el-button>
        <el-button type="primary" @click="handleSaveUser">保存</el-button>
      </template>
    </el-dialog>

    <!-- 报告查看弹窗 -->
    <ReportViewDialog v-model="showReportDialog" :report="currentReport" />
  </div>
</template>

<script setup>
import { ref, watch, nextTick, computed } from "vue";
import { useRoute } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { api } from "../api";
import ReportViewDialog from "../components/ReportViewDialog.vue";

const route = useRoute();

// 状态
const activeTab = ref("reports");

// 报告列表
const reports = ref([]);
const tableRef = ref(null);
const reportQuery = ref("");
const reportStatus = ref("");
const reportPage = ref(1);
const reportPageSize = ref(10);
const reportTotal = ref(0);
const selectedReports = ref([]);
const isRestoringSelection = ref(false); // 标记是否正在恢复选中状态

// 导入
const importFile = ref(null);
const preAnnotationFile = ref(null);
const preUploadRef = ref(null);
const importing = ref(false);
const importTask = ref(null);

// 用户
const users = ref([]);
const doctors = ref([]);
const showUserModal = ref(false);
const editingUser = ref(null);
const userForm = ref({ username: "", password: "", role: "doctor", employee_id: "" });

// 分发
const showAssignModal = ref(false);
const showReportDialog = ref(false);
const currentReport = ref(null);
const assignDoctorIds = ref([]);
const doctorTransferData = computed(() =>
  doctors.value.map((doctor) => ({
    key: doctor.id,
    label: doctor.employee_id
      ? `${doctor.username}（工号：${doctor.employee_id}）`
      : doctor.username,
  })),
);

// 方法
const handleStatusChange = () => {
  reportPage.value = 1;
  selectedReports.value = [];
  loadReports();
};

const tableIndex = (index) => {
  return (reportPage.value - 1) * reportPageSize.value + index + 1;
};

const checkSelectable = (row) => {
  return row.status === "IMPORTED";
};

const handleSelectionChange = (selection) => {
  // 如果是正在恢复选中状态，不处理
  if (isRestoringSelection.value) {
    return;
  }

  // 获取当前页的IMPORTED记录ID
  const currentPageIds = reports.value
    .filter((r) => r.status === "IMPORTED")
    .map((r) => r.id);

  // 从selectedReports中移除当前页的所有ID
  const prevSelected = selectedReports.value.filter(
    (id) => !currentPageIds.includes(id),
  );

  // 添加当前页选中的ID
  const selectedIds = selection
    .filter((r) => r.status === "IMPORTED")
    .map((r) => r.id);

  selectedReports.value = [...prevSelected, ...selectedIds];
};

const loadReports = async () => {
  const params = { page: reportPage.value, page_size: reportPageSize.value };
  if (reportQuery.value) params.q = reportQuery.value;
  if (reportStatus.value) params.status = reportStatus.value;
  const res = await api.getReports(params);
  reports.value = res.items;
  reportTotal.value = res.total;

  // 加载新数据后，恢复当前页选中状态
  isRestoringSelection.value = true;
  nextTick(() => {
    // 先清空表格的选中状态
    tableRef.value?.clearSelection();

    // 然后根据 selectedReports 恢复当前页的选中状态
    const importableRows = reports.value.filter((r) => r.status === "IMPORTED");
    importableRows.forEach((row) => {
      if (selectedReports.value.includes(row.id)) {
        tableRef.value?.toggleRowSelection(row, true);
      }
    });

    // 恢复完成后重置标记
    isRestoringSelection.value = false;
  });
};

const loadUsers = async () => {
  const allUsers = await api.getUsers();
  // 固定顺序：按创建顺序（id 升序）展示，编辑不会改变表格物理位置
  users.value = [...allUsers].sort((a, b) => a.id - b.id);
  doctors.value = await api.getUsers("doctor");
};

const handleFileSelect = (uploadFile) => {
  importFile.value = uploadFile.raw;
  importTask.value = null;
};

const handlePreFileSelect = (uploadFile) => {
  preAnnotationFile.value = uploadFile.raw;
};

const handleImport = async () => {
  if (!importFile.value) return;
  importing.value = true;
  try {
    const res = await api.importReports(importFile.value, preAnnotationFile.value);
    importTask.value = await pollTask(res.task_id);
    ElMessage.success("导入完成");
  } catch (e) {
    ElMessage.error(e.message);
  } finally {
    importing.value = false;
  }
};

const openAssignModal = async () => {
  if (doctors.value.length === 0) {
    await loadUsers();
  }
  if (doctors.value.length === 0) {
    ElMessage.warning("暂无可分发医生，请先在用户管理中创建医生账号");
    return;
  }
  assignDoctorIds.value = [];
  showAssignModal.value = true;
};

const pollTask = async (taskId) => {
  while (true) {
    const task = await api.getImportTask(taskId);
    if (task.status !== "RUNNING" && task.status !== "PENDING") {
      return task;
    }
    await new Promise((r) => setTimeout(r, 1000));
  }
};

const handleAssign = async () => {
  try {
    const doctorMap = new Map(doctors.value.map((doctor) => [doctor.id, doctor.username]));
    const res = await api.assignReports([], null, assignDoctorIds.value);
    const perDoctorText = Object.entries(res.per_doctor || {})
      .filter(([, count]) => count > 0)
      .map(([doctorId, count]) => `${doctorMap.get(Number(doctorId)) || doctorId}：${count}条`)
      .join("；");
    ElMessage.success(
      perDoctorText
        ? `分发成功，共 ${res.assigned} 条。${perDoctorText}`
        : `分发成功，共 ${res.assigned} 条`,
    );
    showAssignModal.value = false;
    selectedReports.value = [];
    assignDoctorIds.value = [];
    loadReports();
  } catch (e) {
    ElMessage.error(e.message);
  }
};

const viewReport = (r) => {
  currentReport.value = r;
  showReportDialog.value = true;
};

const openUserModal = (user = null) => {
  editingUser.value = user;
  userForm.value = user
    ? { username: user.username, password: "", role: user.role, employee_id: user.employee_id || "" }
    : { username: "", password: "", role: "doctor", employee_id: "" };
  showUserModal.value = true;
};

const handleSaveUser = async () => {
  const payload = {
    username: userForm.value.username?.trim(),
    role: userForm.value.role,
    employee_id: userForm.value.employee_id?.trim() || null,
  };

  if (userForm.value.password) {
    payload.password = userForm.value.password;
  }

  try {
    if (editingUser.value) {
      await api.updateUser(editingUser.value.id, payload);
    } else {
      if (!payload.password) {
        ElMessage.error("新建用户必须填写密码");
        return;
      }
      await api.createUser(payload);
    }
    ElMessage.success("保存成功");
    showUserModal.value = false;
    editingUser.value = null;
    loadUsers();
  } catch (e) {
    ElMessage.error(e.message);
  }
};

const toggleUser = async (user) => {
  try {
    await api.updateUser(user.id, { enabled: !user.enabled });
    loadUsers();
  } catch (e) {
    ElMessage.error(e.message);
  }
};

const toggleViewAll = async (user) => {
  try {
    await api.updateUser(user.id, { can_view_all: !user.can_view_all });
    loadUsers();
  } catch (e) {
    ElMessage.error(e.message);
  }
};

const deleteUser = async (user) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除用户 "${user.username}" 吗？`,
      "提示",
      { confirmButtonText: "确定", cancelButtonText: "取消", type: "warning" },
    );
    await api.deleteUser(user.id);
    loadUsers();
    ElMessage.success("删除成功");
  } catch (e) {
    if (e !== "cancel") ElMessage.error(e.message);
  }
};

const deleteReport = async (r) => {
  try {
    await ElMessageBox.confirm(
      `确定要删除检查号 "${r.ris_no || r.external_id || r.id}" 吗？`,
      "提示",
      { confirmButtonText: "确定", cancelButtonText: "取消", type: "warning" },
    );
    await api.deleteReport(r.id);
    const idx = reports.value.indexOf(r);
    if (idx > -1) reports.value.splice(idx, 1);
    selectedReports.value = selectedReports.value.filter((id) => id !== r.id);
    reportTotal.value--;
    ElMessage.success("删除成功");
  } catch (e) {
    if (e !== "cancel") ElMessage.error(e.message);
  }
};

const batchDelete = async () => {
  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedReports.value.length} 条记录吗？`,
      "提示",
      { confirmButtonText: "确定", cancelButtonText: "取消", type: "warning" },
    );
    const idsToDelete = [...selectedReports.value];
    for (const id of idsToDelete) {
      await api.deleteReport(id);
    }
    reports.value = reports.value.filter((r) => !idsToDelete.includes(r.id));
    selectedReports.value = [];
    reportTotal.value -= idsToDelete.length;
    ElMessage.success("删除成功");
  } catch (e) {
    if (e !== "cancel") ElMessage.error(e.message);
  }
};

const formatTime = (_row, _column, cellValue) => {
  if (!cellValue) return '-'
  const date = new Date(cellValue)
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hour = String(date.getHours()).padStart(2, '0')
  const minute = String(date.getMinutes()).padStart(2, '0')
  const second = String(date.getSeconds()).padStart(2, '0')
  return `${year}-${month}-${day} ${hour}:${minute}:${second}`
};

const getStatusText = (status) => {
  const statusMap = {
    IMPORTED: "待分发",
    ASSIGNED: "已分发",
    IN_PROGRESS: "标注中",
    SUBMITTED: "已提交",
    REVIEW_PENDING: "待复核",
    REJECTED: "已驳回",
    DONE: "已完成",
  };
  return statusMap[status] || status;
};

const getStatusType = (status) => {
  const typeMap = {
    IMPORTED: "info", // 灰色 - 待分发
    ASSIGNED: "primary", // 蓝色 - 已分发
    IN_PROGRESS: "warning", // 橙色 - 标注中
    SUBMITTED: "warning", // 黄色 - 已提交
    REVIEW_PENDING: "warning", // 黄色 - 待复核
    REJECTED: "danger", // 红色 - 已驳回
    DONE: "primary", // 蓝色 - 已完成
  };
  return typeMap[status] || "";
};

const getRoleText = (role) => {
  const roleMap = {
    admin: "管理员",
    doctor: "专家",
    reviewer: "复核人"
  };
  return roleMap[role] || role;
};

// 监听 query 变化
watch(reportQuery, () => {
  reportPage.value = 1;
  selectedReports.value = [];
});

watch(
  () => route.path,
  (path) => {
    const tab = path.startsWith("/admin/import")
      ? "import"
      : path.startsWith("/admin/users")
        ? "users"
        : "reports";
    activeTab.value = tab;

    if (tab === "reports") loadReports();
    if (tab === "users") loadUsers();
  },
  { immediate: true },
);

watch(
  () => [reportPage.value, reportPageSize.value],
  () => {
    if (activeTab.value === "reports") {
      loadReports();
    }
  },
);

watch(
  () => activeTab.value,
  (tab) => {
    if (tab === "users") {
      loadUsers();
    }
  },
);
</script>

<style scoped>
.admin-page {
  background: #fff;
  padding: 20px;
  border-radius: 8px;
}

.panel {
  margin-top: 16px;
}

.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  align-items: center;
  flex-wrap: wrap;
}

.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.import-result {
  margin-top: 20px;
}
</style>
