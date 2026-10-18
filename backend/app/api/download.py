"""
下载相关API
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models import TaskRecord, ExcelFile
from app.utils.logger import logger, log_to_database
from pathlib import Path

router = APIRouter()


@router.get("/download/{task_id}")
async def download_excel(
    task_id: str,
    db: Session = Depends(get_db)
):
    """
    下载处理后的Excel文件
    """
    try:
        # 获取任务记录
        task_record = db.query(TaskRecord).filter(TaskRecord.task_id == task_id).first()
        if not task_record:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        if task_record.status != "completed":
            raise HTTPException(status_code=400, detail="任务尚未完成")
        
        # 获取处理后的文件
        excel_file = db.query(ExcelFile).filter(
            ExcelFile.task_id == task_record.id,
            ExcelFile.file_type == "original"
        ).first()
        
        if not excel_file or not excel_file.processed_file_path:
            raise HTTPException(status_code=404, detail="文件不存在")
        
        file_path = Path(excel_file.processed_file_path)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="文件不存在")
        
        log_to_database(task_id, "INFO", "DownloadAPI", "文件下载", f"文件名: {file_path.name}")
        
        return FileResponse(
            path=str(file_path),
            filename=excel_file.file_name,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"下载文件失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"下载失败: {str(e)}")

