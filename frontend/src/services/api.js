import axios from 'axios'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 300000, // 5分钟超时
  headers: {
    'Content-Type': 'application/json'
  }
})

// 上传Excel文件
export const uploadExcel = (formData) => {
  return api.post('/upload', formData, {
    headers: {
      'Content-Type': 'multipart/form-data'
    }
  })
}

// 处理Excel
export const processExcel = (config) => {
  console.log('processExcel API调用，URL: /api/v1/process, 数据:', config)
  return api.post('/process', config, {
    headers: {
      'Content-Type': 'application/json'
    }
  })
}

// 查询任务状态
export const getTaskStatus = (taskId) => {
  return api.get(`/status/${taskId}`)
}

// 下载Excel
export const downloadExcel = (taskId) => {
  return api.get(`/download/${taskId}`, {
    responseType: 'blob'
  })
}

export default api

