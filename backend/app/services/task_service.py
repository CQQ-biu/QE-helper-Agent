"""
异步任务服务
"""
from pathlib import Path
from celery import Celery
from celery.signals import worker_process_init
from app.config import settings
from app.db.database import SessionLocal, engine, initialize_database
from app.models import TaskRecord, ExcelFile
from app.services.excel_service import ExcelService
from app.services.answer_service import AnswerService
from app.utils.logger import logger, log_to_database

logger.info("Celery Worker数据库: %s", engine.url.render_as_string(hide_password=True))

# 初始化Celery
celery_app = Celery(
    "qe_helper",
    broker=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
    backend=f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}"
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Shanghai',
    enable_utc=True,
)


@worker_process_init.connect
def initialize_worker_database(**kwargs):
    """确保Celery单独启动时也已启用pgvector并创建表。"""
    # prefork子进程不能复用父进程建立的数据库连接。
    engine.dispose(close=False)
    initialize_database()


@celery_app.task(name="process_excel_task")
def process_excel_task(
    task_id: str,
    file_path: str,
    customer_name: str,
    customer_type: str,
    work_number: str,
    fill_date: str,
    answer_language: str,
    max_score: float,
    sheet_configs: list
):
    """
    处理Excel的异步任务
    """
    db = SessionLocal()
    try:
        # 更新任务状态为处理中
        # 使用新的数据库会话查询，确保能获取到数据
        task_record = db.query(TaskRecord).filter(TaskRecord.task_id == task_id).first()
        
        if not task_record:
            # 尝试刷新数据库连接
            db.close()
            db = SessionLocal()
            task_record = db.query(TaskRecord).filter(TaskRecord.task_id == task_id).first()
            
        if not task_record:
            # 记录所有任务ID用于调试
            all_tasks = db.query(TaskRecord.task_id).limit(10).all()
            logger.error(f"任务记录不存在: {task_id}")
            logger.error(f"数据库中最近的任务ID: {[t[0] for t in all_tasks]}")
            raise Exception(f"任务记录不存在: {task_id}")
        
        # 保存任务记录ID，确保后续使用
        task_record_id = task_record.id
        logger.info(f"找到任务记录，ID: {task_record_id}, 状态: {task_record.status}")
        
        task_record.status = "processing"
        db.commit()
        logger.info(f"任务状态已更新为processing")
        
        log_to_database(task_id, "INFO", "TaskService", "开始处理Excel任务")
        
        # 初始化服务
        excel_service = ExcelService()
        answer_service = AnswerService(max_score=max_score, language=answer_language)
        
        # 再次验证 task_record
        if task_record is None:
            raise Exception(f"任务记录意外变为None: {task_id}")
        
        # 处理Excel
        # 确保文件路径是绝对路径
        from pathlib import Path
        if not Path(file_path).is_absolute():
            # 如果是相对路径，转换为绝对路径
            base_dir = Path(__file__).parent.parent.parent  # 回到 backend/
            file_path = str((base_dir / file_path).resolve())
        
        logger.info(f"处理文件路径: {file_path}")
        logger.info(f"文件是否存在: {Path(file_path).exists()}")
        logger.info(f"任务记录ID: {task_record.id}")
        logger.info(f"Sheet配置数量: {len(sheet_configs) if sheet_configs else 0}")
        
        try:
            processed_file_path = excel_service.process_excel(
                file_path=file_path,
                sheet_configs=sheet_configs,
                answer_service=answer_service,
                task_id=task_id
            )
        except AttributeError as e:
            logger.error(f"属性错误: {str(e)}")
            logger.error(f"task_record类型: {type(task_record)}")
            logger.error(f"task_record值: {task_record}")
            raise
        
        if not processed_file_path:
            raise Exception("Excel处理失败")
        
        # 更新文件记录（使用之前保存的ID）
        excel_file = db.query(ExcelFile).filter(
            ExcelFile.task_id == task_record_id,
            ExcelFile.file_type == "original"
        ).first()
        
        if excel_file:
            excel_file.processed_file_path = processed_file_path
            db.commit()
        
        # 更新任务状态为完成（重新查询以确保对象有效）
        task_record = db.query(TaskRecord).filter(TaskRecord.id == task_record_id).first()
        if task_record:
            task_record.status = "completed"
            db.commit()
        
        log_to_database(task_id, "INFO", "TaskService", "Excel任务处理完成")
        
        return {
            "success": True,
            "file_path": processed_file_path
        }
    
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        logger.error(f"处理Excel任务失败: {str(e)}")
        logger.error(f"错误详情:\n{error_detail}")
        log_to_database(task_id, "ERROR", "TaskService", f"处理Excel任务失败: {str(e)}", error_detail)
        
        # 更新任务状态为失败
        task_record = db.query(TaskRecord).filter(TaskRecord.task_id == task_id).first()
        if task_record:
            task_record.status = "failed"
            db.commit()
        
        raise
    
    finally:
        db.close()

