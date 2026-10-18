"""
上传相关API
"""
import os
import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.models import TaskRecord, ExcelFile
from app.schemas import UploadRequest, ExcelParseResponse, ProcessConfigRequest, ResponseModel
from app.services.excel_service import ExcelService
from app.services.task_service import process_excel_task
from app.utils.logger import logger, log_to_database
from app.config import settings

router = APIRouter()

excel_service = ExcelService()


@router.post("/upload", response_model=ResponseModel)
async def upload_excel(
    customer_name: str = Form(...),
    customer_type: str = Form(...),
    work_number: str = Form(...),
    fill_date: str = Form(...),
    answer_language: str = Form(...),
    max_score: float = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    上传Excel文件并解析
    """
    try:
        # 生成任务ID
        task_id = str(uuid.uuid4())
        
        # 保存上传的文件
        upload_dir = Path(settings.UPLOAD_DIR)
        upload_dir.mkdir(exist_ok=True, parents=True)
        
        file_path = upload_dir / f"{task_id}_{file.filename}"
        # 转换为绝对路径，确保Celery Worker能找到文件
        file_path = file_path.resolve()
        with open(file_path, "wb") as f:
            content = await file.read()
            if len(content) > settings.MAX_FILE_SIZE:
                raise HTTPException(status_code=413, detail="文件大小超过限制")
            f.write(content)
        
        # 解析Excel
        parse_result = excel_service.parse_excel(str(file_path))
        
        if not parse_result["success"]:
            raise HTTPException(status_code=400, detail=f"Excel解析失败: {parse_result.get('error')}")
        
        # 保存任务记录到数据库
        from datetime import datetime
        try:
            # 尝试ISO格式
            fill_date_obj = datetime.fromisoformat(fill_date.replace("Z", "+00:00"))
        except:
            try:
                # 兼容格式：YYYY-MM-DDTHH:mm:ss
                fill_date_obj = datetime.fromisoformat(fill_date)
            except:
                try:
                    # 兼容格式：YYYY-MM-DD HH:mm:ss
                    fill_date_obj = datetime.strptime(fill_date, "%Y-%m-%d %H:%M:%S")
                except:
                    # 默认当前时间
                    fill_date_obj = datetime.now()
        
        task_record = TaskRecord(
            task_id=task_id,
            customer_name=customer_name,
            customer_type=customer_type,
            work_number=work_number,
            fill_date=fill_date_obj,
            answer_language=answer_language,
            max_score=max_score,
            status="pending"
        )
        db.add(task_record)
        db.commit()
        db.refresh(task_record)
        
        # 保存文件记录（使用绝对路径）
        excel_file = ExcelFile(
            task_id=task_record.id,
            file_name=file.filename,
            file_path=str(file_path.resolve()),  # 保存绝对路径
            file_size=len(content),
            file_type="original"
        )
        db.add(excel_file)
        db.commit()
        
        # 确保数据已提交到数据库（重要：Celery Worker需要能查询到）
        db.refresh(excel_file)
        
        log_to_database(task_id, "INFO", "UploadAPI", "文件上传成功", f"文件名: {file.filename}")
        
        logger.info(f"任务记录已保存到数据库: task_id={task_id}, record_id={task_record.id}")
        
        return ResponseModel(
            success=True,
            message="上传成功",
            data={
                "task_id": task_id,
                "file_name": file.filename,
                "sheets": parse_result["sheets"]
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"上传文件失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"上传失败: {str(e)}")


@router.post("/process", response_model=ResponseModel)
async def process_excel(
    request: ProcessConfigRequest,
    db: Session = Depends(get_db)
):
    """
    处理Excel：根据配置填入答案
    """
    try:
        # 获取任务记录
        task_record = db.query(TaskRecord).filter(TaskRecord.task_id == request.task_id).first()
        if not task_record:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        # 获取原始文件
        excel_file = db.query(ExcelFile).filter(
            ExcelFile.task_id == task_record.id,
            ExcelFile.file_type == "original"
        ).first()
        
        if not excel_file:
            raise HTTPException(status_code=404, detail="文件不存在")
        
        # 保存配置信息
        import json
        excel_file.excel_config = json.dumps(
            [config.dict() for config in request.sheet_configs],
            ensure_ascii=False
        )
        db.commit()
        
        # 刷新数据库对象，确保数据已提交
        db.refresh(task_record)
        db.refresh(excel_file)
        
        # 验证task_id是否正确
        logger.info(f"准备启动任务，task_id={request.task_id}, 数据库task_id={task_record.task_id}")
        
        # 使用数据库中的实际task_id
        actual_task_id = task_record.task_id
        
        # 启动异步任务
        try:
            result = process_excel_task.delay(
                task_id=actual_task_id,  # 使用数据库中的实际task_id
                file_path=excel_file.file_path,
                customer_name=task_record.customer_name,
                customer_type=task_record.customer_type,
                work_number=task_record.work_number,
                fill_date=task_record.fill_date.isoformat(),
                answer_language=task_record.answer_language,
                max_score=task_record.max_score,
                sheet_configs=[config.dict() for config in request.sheet_configs]
            )
            logger.info(f"任务已提交到Celery，Celery任务ID: {result.id}, 业务task_id: {actual_task_id}")
            log_to_database(actual_task_id, "INFO", "ProcessAPI", f"启动处理任务，Celery任务ID: {result.id}")
        except Exception as e:
            logger.error(f"提交Celery任务失败: {str(e)}")
            log_to_database(request.task_id, "ERROR", "ProcessAPI", "提交Celery任务失败", str(e))
            raise HTTPException(status_code=500, detail=f"启动任务失败: {str(e)}")
        
        return ResponseModel(
            success=True,
            message="任务已启动",
            data={"task_id": request.task_id}
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"启动处理任务失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"启动任务失败: {str(e)}")


@router.get("/status/{task_id}", response_model=ResponseModel)
async def get_task_status(
    task_id: str,
    db: Session = Depends(get_db)
):
    """
    查询任务状态
    """
    try:
        task_record = db.query(TaskRecord).filter(TaskRecord.task_id == task_id).first()
        if not task_record:
            raise HTTPException(status_code=404, detail="任务不存在")
        
        file_url = None
        if task_record.status == "completed":
            excel_file = db.query(ExcelFile).filter(
                ExcelFile.task_id == task_record.id,
                ExcelFile.file_type == "original"
            ).first()
            if excel_file and excel_file.processed_file_path:
                file_url = f"/api/v1/download/{task_id}"
        
        return ResponseModel(
            success=True,
            message="查询成功",
            data={
                "task_id": task_id,
                "status": task_record.status,
                "file_url": file_url
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"查询任务状态失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"查询失败: {str(e)}")

