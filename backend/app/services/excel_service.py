"""
Excel处理服务
"""
import os
from pathlib import Path
from openpyxl import load_workbook
from openpyxl.styles import PatternFill
from openpyxl.utils import get_column_letter, column_index_from_string
from typing import List, Dict, Optional, Tuple
from app.config import settings
from app.utils.logger import logger, log_to_database


class ExcelService:
    """Excel处理服务类"""
    
    def __init__(self):
        # 使用绝对路径，确保在不同工作目录下都能找到文件
        base_dir = Path(__file__).parent.parent.parent  # 从 app/services/excel_service.py 回到 backend/
        self.upload_dir = (base_dir / settings.UPLOAD_DIR).resolve()
        self.output_dir = (base_dir / settings.OUTPUT_DIR).resolve()
        self.upload_dir.mkdir(exist_ok=True, parents=True)
        self.output_dir.mkdir(exist_ok=True, parents=True)
        
        # 高亮颜色（浅黄色）
        self.highlight_fill = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")
    
    def parse_excel(self, file_path: str) -> Dict:
        """
        解析Excel文件，返回sheet和列信息
        """
        try:
            wb = load_workbook(file_path, data_only=False)
            
            sheets_info = []
            for sheet_name in wb.sheetnames:
                sheet = wb[sheet_name]
                
                # 获取有效数据范围
                if sheet.max_row == 0 or sheet.max_column == 0:
                    continue
                
                # 获取列列表
                column_list = []
                for col_idx in range(1, sheet.max_column + 1):
                    col_letter = get_column_letter(col_idx)
                    column_list.append(col_letter)
                
                sheets_info.append({
                    "sheet_name": sheet_name,
                    "total_rows": sheet.max_row,
                    "total_columns": sheet.max_column,
                    "column_mapping": column_list
                })
            
            wb.close()
            
            return {
                "success": True,
                "sheets": sheets_info
            }
        except Exception as e:
            logger.error(f"解析Excel失败: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def process_excel(
        self,
        file_path: str,
        sheet_configs: List[Dict],
        answer_service,
        task_id: str
    ) -> Optional[str]:
        """
        处理Excel：填入答案和分数
        """
        try:
            # 确保文件路径是绝对路径
            file_path = Path(file_path).resolve()
            if not file_path.exists():
                raise FileNotFoundError(f"Excel文件不存在: {file_path}")
            
            log_to_database(task_id, "INFO", "ExcelService", "开始处理Excel文件", f"文件路径: {file_path}")
            
            # 加载工作簿，保留所有格式
            wb = load_workbook(str(file_path))
            
            for sheet_config in sheet_configs:
                sheet_name = sheet_config["sheet_name"]
                if sheet_name not in wb.sheetnames:
                    logger.warning(f"Sheet {sheet_name} 不存在")
                    continue
                
                sheet = wb[sheet_name]
                score_column = sheet_config["score_column"]
                answer_column = sheet_config["answer_column"]
                source_column = sheet_config.get("source_column")
                question_columns = sheet_config["question_columns"]
                
                log_to_database(
                    task_id, "INFO", "ExcelService",
                    f"处理Sheet: {sheet_name}",
                    f"Score列: {score_column}, 答案列: {answer_column}, 来源列: {source_column or '未配置'}"
                )
                
                # 遍历每一行（从第2行开始，假设第1行是标题）
                for row_idx in range(2, sheet.max_row + 1):
                    try:
                        # 提取问题文本（合并多个问题列）
                        question_text = self._extract_question_text(sheet, row_idx, question_columns)
                        
                        if not question_text or question_text.strip() == "":
                            continue
                        
                        # 从知识库检索，并基于命中的资料生成答案和相关度分数
                        answer, score, source = answer_service.generate_answer(question_text, task_id)
                        
                        # 填入分数
                        score_cell = f"{score_column}{row_idx}"
                        if score is not None:
                            sheet[score_cell].value = score
                        sheet[score_cell].fill = self.highlight_fill
                        
                        # 填入答案
                        answer_cell = f"{answer_column}{row_idx}"
                        sheet[answer_cell].value = answer if answer else "未检索到"
                        sheet[answer_cell].fill = self.highlight_fill

                        # 来源列是可选配置；命中业务映射规则时优先写规则指定文件名。
                        if source_column:
                            source_cell = f"{source_column}{row_idx}"
                            sheet[source_cell].value = source if source else "未检索到"
                            sheet[source_cell].fill = self.highlight_fill
                        
                        logger.debug(
                            f"行 {row_idx}: 问题={question_text[:50]}..., "
                            f"答案={answer[:50] if answer else '未检索到'}, 分数={score}, 来源={source}"
                        )
                    
                    except Exception as e:
                        logger.error(f"处理第 {row_idx} 行时出错: {str(e)}")
                        log_to_database(
                            task_id, "ERROR", "ExcelService",
                            f"处理第 {row_idx} 行时出错",
                            str(e)
                        )
                        continue
            
            # 保存处理后的文件
            output_file_path = self.output_dir / f"processed_{task_id}_{Path(file_path).name}"
            output_file_path = output_file_path.resolve()
            wb.save(str(output_file_path))
            wb.close()
            
            log_to_database(task_id, "INFO", "ExcelService", "Excel处理完成", f"输出文件: {output_file_path}")
            
            return str(output_file_path)
        
        except Exception as e:
            logger.error(f"处理Excel失败: {str(e)}")
            log_to_database(task_id, "ERROR", "ExcelService", "处理Excel失败", str(e))
            return None
    
    def _extract_question_text(self, sheet, row_idx: int, question_columns: List[str]) -> str:
        """
        从指定列提取问题文本
        支持单列（如'B'）和列范围（如'B:F'）
        """
        question_parts = []
        
        for col_spec in question_columns:
            if ':' in col_spec:
                # 列范围，如 'B:F'
                start_col, end_col = col_spec.split(':')
                start_idx = column_index_from_string(start_col)
                end_idx = column_index_from_string(end_col)
                
                for col_idx in range(start_idx, end_idx + 1):
                    cell = sheet.cell(row=row_idx, column=col_idx)
                    if cell.value:
                        question_parts.append(str(cell.value))
            else:
                # 单列
                col_idx = column_index_from_string(col_spec)
                cell = sheet.cell(row=row_idx, column=col_idx)
                if cell.value:
                    question_parts.append(str(cell.value))
        
        return " ".join(question_parts).strip()
