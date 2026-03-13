<template>
  <div class="reviewer-page">
    <el-tabs v-model="activeTab" @tab-change="handleTabChange">
      <el-tab-pane label="待复核" name="pending" />
      <el-tab-pane label="已复核" name="reviewed" />
    </el-tabs>

    <!-- 待复核列表 -->
    <div v-if="activeTab === 'pending'" class="panel">
      <el-empty description="当前版本为 MVP，暂不启用复核流程。如需启用，请在管理端配置。" />
    </div>

    <!-- 已复核列表 -->
    <div v-if="activeTab === 'reviewed'" class="panel">
      <el-empty description="暂无复核记录" />
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const activeTab = ref('pending')

const handleTabChange = (tab) => {
  console.log('切换到:', tab)
}
</script>

<style scoped>
.reviewer-page {
  background: #fff;
  padding: 20px;
  border-radius: 8px;
}

.panel {
  padding: 40px 20px;
}
</style>
