"""
启动Celery Worker
"""
from app.services.task_service import celery_app

if __name__ == "__main__":
    celery_app.worker_main(['worker', '--loglevel=info', '--pool=solo'])

