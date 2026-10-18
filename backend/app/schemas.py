"""
Pydantic模型（API请求/响应模型）
"""
from pydantic import BaseModel, Field, model_validator
from typing import Optional, List, Dict, Any
from datetime import datetime


# 上传请求模型
class UploadRequest(BaseModel):
    customer_name: str = Field(..., description="客户名称")
    customer_type: str = Field(..., description="客户类型：设计公司/直接客户")
    work_number: str = Field(..., description="工号")
    fill_date: str = Field(..., description="填表日期")
    answer_language: str = Field(..., description="答案语言：简体中文/英语")
    max_score: float = Field(..., description="最高分数")


# Excel Sheet信息
class SheetInfo(BaseModel):
    sheet_name: str = Field(..., description="Sheet名称")
    total_rows: int = Field(..., description="总行数")
    total_columns: int = Field(..., description="总列数")
    column_mapping: List[str] = Field(..., description="列列表，如['A', 'B', 'C']")


# Excel解析响应
class ExcelParseResponse(BaseModel):
    task_id: str = Field(..., description="任务ID")
    file_name: str = Field(..., description="文件名")
    sheets: List[SheetInfo] = Field(..., description="Sheet列表")


# Sheet配置
class SheetConfig(BaseModel):
    sheet_name: str = Field(..., description="Sheet名称")
    score_column: str = Field(..., description="Score列（如'A'）")
    question_columns: List[str] = Field(..., description="问题列列表（如['B', 'C']）")
    answer_column: str = Field(..., description="答案列（如'G'）")
    source_column: Optional[str] = Field(None, description="来源文件列（如'H'，可选）")

    @model_validator(mode="after")
    def validate_output_columns(self):
        output_columns = [self.score_column, self.answer_column]
        if self.source_column:
            output_columns.append(self.source_column)
        if len(output_columns) != len(set(output_columns)):
            raise ValueError("Score列、答案列和来源文件列不能重复")
        return self


# 处理配置请求
class ProcessConfigRequest(BaseModel):
    task_id: str = Field(..., description="任务ID")
    sheet_configs: List[SheetConfig] = Field(..., description="Sheet配置列表")


# 任务状态响应
class TaskStatusResponse(BaseModel):
    task_id: str = Field(..., description="任务ID")
    status: str = Field(..., description="任务状态")
    message: Optional[str] = Field(None, description="消息")
    progress: Optional[float] = Field(None, description="进度（0-100）")
    file_url: Optional[str] = Field(None, description="文件下载URL")


# 通用响应
class ResponseModel(BaseModel):
    success: bool = Field(..., description="是否成功")
    message: str = Field(..., description="消息")
    data: Optional[Any] = Field(None, description="数据")
