<template>
  <div class="home-container">
    <el-card class="form-card">
      <template #header>
        <div class="card-header">
          <span>基本信息</span>
        </div>
      </template>
      
      <el-form :model="form" label-width="140px" ref="formRef">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="客户名称" required>
              <el-input v-model="form.customer_name" placeholder="请输入客户名称" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="客户类型" required>
              <el-select v-model="form.customer_type" placeholder="请选择客户类型" style="width: 100%">
                <el-option label="设计公司" value="设计公司" />
                <el-option label="直接客户" value="直接客户" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>
        
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="工号" required>
              <el-input v-model="form.work_number" placeholder="请输入工号" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="填表日期" required>
              <el-date-picker
                v-model="form.fill_date"
                type="datetime"
                placeholder="请选择日期"
                style="width: 100%"
                format="YYYY-MM-DD HH:mm:ss"
                value-format="YYYY-MM-DDTHH:mm:ss"
              />
            </el-form-item>
          </el-col>
        </el-row>
        
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="答案语言" required>
              <el-select v-model="form.answer_language" placeholder="请选择语言" style="width: 100%">
                <el-option label="简体中文" value="简体中文" />
                <el-option label="英语" value="英语" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="最高分数" required>
              <el-input-number
                v-model="form.max_score"
                :min="0"
                :max="100"
                :precision="2"
                style="width: 100%"
                placeholder="请输入最高分数"
              />
            </el-form-item>
          </el-col>
        </el-row>
        
        <el-form-item label="上传Excel">
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :limit="1"
            :on-change="handleFileChange"
            :on-remove="handleFileRemove"
            accept=".xlsx,.xls"
          >
            <el-button type="primary">选择文件</el-button>
            <template #tip>
              <div class="el-upload__tip">
                只能上传Excel文件（.xlsx, .xls），且不超过50MB
              </div>
            </template>
          </el-upload>
        </el-form-item>
        
        <el-form-item>
          <el-button
            type="primary"
            @click="handleUpload"
            :loading="uploading"
            :disabled="!file"
          >
            上传并解析
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>
    
    <!-- Excel配置卡片 -->
    <el-card v-if="excelInfo" class="config-card" style="margin-top: 20px">
      <template #header>
        <div class="card-header">
          <span>Excel配置</span>
        </div>
      </template>
      
      <div v-for="(sheet, index) in excelInfo.sheets" :key="index" class="sheet-config">
        <el-divider>
          <span style="font-weight: bold">Sheet: {{ sheet.sheet_name }}</span>
        </el-divider>
        
        <el-form :model="sheetConfigs[index]" label-width="140px">
          <el-form-item label="启用此Sheet">
            <el-switch v-model="sheetConfigs[index].enabled" />
          </el-form-item>
          
          <template v-if="sheetConfigs[index].enabled">
            <el-form-item label="Score列">
              <el-select v-model="sheetConfigs[index].score_column" placeholder="请选择Score列">
                <el-option
                  v-for="col in sheet.column_mapping"
                  :key="col"
                  :label="col"
                  :value="col"
                />
              </el-select>
            </el-form-item>
            
            <el-form-item label="答案列">
              <el-select v-model="sheetConfigs[index].answer_column" placeholder="请选择答案列">
                <el-option
                  v-for="col in sheet.column_mapping"
                  :key="col"
                  :label="col"
                  :value="col"
                />
              </el-select>
            </el-form-item>

            <el-form-item label="来源文件列">
              <el-select
                v-model="sheetConfigs[index].source_column"
                clearable
                placeholder="请选择来源文件列（可选）"
              >
                <el-option
                  v-for="col in sheet.column_mapping"
                  :key="col"
                  :label="col"
                  :value="col"
                />
              </el-select>
            </el-form-item>
            
            <el-form-item label="问题列">
              <el-select
                v-model="sheetConfigs[index].question_columns"
                multiple
                placeholder="请选择问题列（可多选）"
                style="width: 100%"
              >
                <el-option
                  v-for="col in sheet.column_mapping"
                  :key="col"
                  :label="col"
                  :value="col"
                />
              </el-select>
              <div class="tip-text">
                提示：如果问题跨多列（如A到F），请分别选择A、B、C、D、E、F
              </div>
            </el-form-item>
          </template>
        </el-form>
      </div>
      
      <el-form-item style="margin-top: 20px">
        <el-button
          type="success"
          @click="handleProcess"
          :loading="processing"
          :disabled="!hasEnabledSheet"
        >
          开始处理
        </el-button>
      </el-form-item>
    </el-card>
    
    <!-- 处理进度卡片 -->
    <el-card v-if="currentTaskId" class="progress-card" style="margin-top: 20px">
      <template #header>
        <div class="card-header">
          <span>处理进度</span>
        </div>
      </template>
      
      <div class="progress-content">
        <el-steps :active="stepActive" align-center>
          <el-step title="上传中" :description="stepStatus.upload" />
          <el-step title="处理中" :description="stepStatus.process" />
          <el-step title="完成" :description="stepStatus.complete" />
        </el-steps>
        
        <div style="margin-top: 30px; text-align: center">
          <el-button
            v-if="taskStatus === 'completed'"
            type="primary"
            @click="handleDownload"
            :loading="downloading"
          >
            下载处理后的Excel
          </el-button>
          <el-text v-else type="info">
            任务状态: {{ getStatusText(taskStatus) }}
          </el-text>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script>
import { ref, reactive, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { uploadExcel, processExcel, getTaskStatus, downloadExcel } from '../services/api'

export default {
  name: 'Home',
  setup() {
    const formRef = ref(null)
    const uploadRef = ref(null)
    const uploading = ref(false)
    const processing = ref(false)
    const downloading = ref(false)
    const file = ref(null)
    const excelInfo = ref(null)
    const currentTaskId = ref(null)
    const taskStatus = ref('')
    const statusCheckInterval = ref(null)
    
    const form = reactive({
      customer_name: '',
      customer_type: '',
      work_number: '',
      fill_date: '',
      answer_language: '简体中文',
      max_score: 10.0
    })
    
    const sheetConfigs = ref([])
    
    const stepActive = computed(() => {
      if (taskStatus.value === 'completed') return 2
      if (taskStatus.value === 'processing') return 1
      return 0
    })
    
    const stepStatus = reactive({
      upload: '等待上传',
      process: '等待处理',
      complete: '等待完成'
    })
    
    const hasEnabledSheet = computed(() => {
      return sheetConfigs.value.some(config => config.enabled)
    })
    
    const handleFileChange = (uploadFile) => {
      file.value = uploadFile.raw
    }
    
    const handleFileRemove = () => {
      file.value = null
      excelInfo.value = null
      sheetConfigs.value = []
    }
    
    const handleUpload = async () => {
      console.log('handleUpload 被调用')
      console.log('表单数据:', form)
      console.log('文件:', file.value)
      
      // 验证表单
      if (!form.customer_name || !form.customer_type || !form.work_number || 
          !form.fill_date || !form.answer_language || !form.max_score) {
        console.warn('表单验证失败，缺少字段')
        ElMessage.warning('请填写完整的基本信息')
        return
      }
      
      if (!file.value) {
        ElMessage.warning('请先选择Excel文件')
        return
      }
      
      uploading.value = true
      try {
        const formData = new FormData()
        formData.append('file', file.value)
        formData.append('customer_name', form.customer_name)
        formData.append('customer_type', form.customer_type)
        formData.append('work_number', form.work_number)
        formData.append('fill_date', form.fill_date)
        formData.append('answer_language', form.answer_language)
        formData.append('max_score', form.max_score.toString())
        
        console.log('开始上传，表单数据:', {
          customer_name: form.customer_name,
          customer_type: form.customer_type,
          work_number: form.work_number,
          fill_date: form.fill_date,
          answer_language: form.answer_language,
          max_score: form.max_score,
          file: file.value?.name
        })
        
        const response = await uploadExcel(formData)
        console.log('上传响应:', response.data)
        
        if (response.data && response.data.success) {
          excelInfo.value = response.data.data
          currentTaskId.value = excelInfo.value.task_id
          
          // 初始化Sheet配置
          sheetConfigs.value = excelInfo.value.sheets.map(sheet => ({
            sheet_name: sheet.sheet_name,
            enabled: false,
            score_column: '',
            answer_column: '',
            source_column: '',
            question_columns: []
          }))
          
          ElMessage.success('上传成功！请配置Sheet信息')
          stepStatus.upload = '上传成功'
        } else {
          ElMessage.error(response.data?.message || '上传失败')
        }
      } catch (error) {
        console.error('上传失败:', error)
        console.error('错误详情:', error.response)
        const errorMessage = error.response?.data?.detail || error.response?.data?.message || error.message || '上传失败，请稍后重试'
        ElMessage.error(errorMessage)
      } finally {
        uploading.value = false
      }
    }
    
    const handleProcess = async () => {
      console.log('handleProcess 被调用')
      
      // 验证配置
      const enabledConfigs = sheetConfigs.value.filter(config => config.enabled)
      console.log('启用的配置:', enabledConfigs)
      
      for (const config of enabledConfigs) {
        if (!config.score_column || !config.answer_column || config.question_columns.length === 0) {
          console.warn('配置不完整:', config)
          ElMessage.warning('请完整配置所有启用的Sheet')
          return
        }
        const outputColumns = [config.score_column, config.answer_column, config.source_column].filter(Boolean)
        if (new Set(outputColumns).size !== outputColumns.length) {
          ElMessage.warning('Score列、答案列和来源文件列不能重复')
          return
        }
      }
      
      if (enabledConfigs.length === 0) {
        ElMessage.warning('请至少启用一个Sheet')
        return
      }
      
      processing.value = true
      stepStatus.process = '处理中...'
      
      try {
        const config = {
          task_id: currentTaskId.value,
          sheet_configs: enabledConfigs.map(config => ({
            sheet_name: config.sheet_name,
            score_column: config.score_column,
            answer_column: config.answer_column,
            source_column: config.source_column || null,
            question_columns: config.question_columns
          }))
        }
        
        console.log('发送处理请求，配置:', JSON.stringify(config, null, 2))
        
        const response = await processExcel(config)
        console.log('处理响应:', response.data)
        
        if (response.data && response.data.success) {
          ElMessage.success('处理任务已启动，请等待完成')
          // 立即查询一次状态
          taskStatus.value = 'pending'
          stepStatus.process = '已提交，等待处理...'
          // 启动状态轮询
          startStatusCheck()
        } else {
          ElMessage.error(response.data?.message || '启动处理失败')
        }
      } catch (error) {
        console.error('处理失败:', error)
        console.error('错误详情:', error.response)
        const errorMessage = error.response?.data?.detail || error.response?.data?.message || error.message || '启动处理失败，请稍后重试'
        ElMessage.error(errorMessage)
        stepStatus.process = '处理失败'
      } finally {
        processing.value = false
      }
    }
    
    const startStatusCheck = () => {
      if (statusCheckInterval.value) {
        clearInterval(statusCheckInterval.value)
      }
      
      statusCheckInterval.value = setInterval(async () => {
        try {
          const response = await getTaskStatus(currentTaskId.value)
          console.log('状态查询响应:', response.data)
          if (response.data && response.data.success) {
            const newStatus = response.data.data.status
            console.log(`任务状态更新: ${taskStatus.value} -> ${newStatus}`)
            taskStatus.value = newStatus
            
            // 更新步骤状态显示
            if (newStatus === 'processing') {
              stepStatus.process = '处理中...'
            }
            
            if (newStatus === 'completed') {
              clearInterval(statusCheckInterval.value)
              stepStatus.complete = '处理完成'
              ElMessage.success('处理完成！可以下载文件了')
            } else if (newStatus === 'failed') {
              clearInterval(statusCheckInterval.value)
              stepStatus.complete = '处理失败'
              ElMessage.error('处理失败，请查看日志')
            }
          }
        } catch (error) {
          console.error('查询状态失败:', error)
        }
      }, 2000) // 每2秒查询一次
    }
    
    const handleDownload = async () => {
      downloading.value = true
      try {
        const response = await downloadExcel(currentTaskId.value)
        
        // 创建下载链接
        const blob = new Blob([response.data], {
          type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        })
        const url = window.URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = `processed_${currentTaskId.value}.xlsx`
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        window.URL.revokeObjectURL(url)
        
        ElMessage.success('下载成功')
      } catch (error) {
        console.error('下载失败:', error)
        ElMessage.error(error.response?.data?.detail || '下载失败，请稍后重试')
      } finally {
        downloading.value = false
      }
    }
    
    const getStatusText = (status) => {
      const statusMap = {
        'pending': '等待中',
        'processing': '处理中',
        'completed': '已完成',
        'failed': '失败'
      }
      return statusMap[status] || status
    }
    
    return {
      formRef,
      uploadRef,
      form,
      uploading,
      processing,
      downloading,
      file,
      excelInfo,
      sheetConfigs,
      hasEnabledSheet,
      currentTaskId,
      taskStatus,
      stepActive,
      stepStatus,
      handleFileChange,
      handleFileRemove,
      handleUpload,
      handleProcess,
      handleDownload,
      getStatusText
    }
  }
}
</script>

<style scoped>
.home-container {
  max-width: 1200px;
  margin: 0 auto;
}

.form-card,
.config-card,
.progress-card {
  background: white;
  border-radius: 8px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: bold;
  font-size: 16px;
}

.sheet-config {
  margin-bottom: 20px;
}

.tip-text {
  font-size: 12px;
  color: #909399;
  margin-top: 5px;
}

.progress-content {
  padding: 20px;
}
</style>
