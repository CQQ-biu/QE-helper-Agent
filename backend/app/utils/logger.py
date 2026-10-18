"""
日志工具
"""
import logging
import os
from datetime import datetime
from pathlib import Path
from app.config import settings
from app.db.database import SessionLocal
from app.models import SystemLog


def setup_logger():
    """配置日志系统"""
    log_dir = Path(settings.LOG_DIR)
    log_dir.mkdir(exist_ok=True)
    
    log_file = log_dir / f"app_{datetime.now().strftime('%Y%m%d')}.log"
    
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    
    return logging.getLogger(__name__)


logger = setup_logger()


def log_to_database(task_id: str, level: str, module: str, message: str, details: str = None):
    """将日志保存到数据库"""
    db = None
    try:
        db = SessionLocal()
        log_entry = SystemLog(
            task_id=task_id,
            level=level,
            module=module,
            message=message,
            details=details
        )
        db.add(log_entry)
        db.commit()
    except Exception as e:
        logger.error(f"保存日志到数据库失败: {str(e)}")
    finally:
        if db is not None:
            db.close()

