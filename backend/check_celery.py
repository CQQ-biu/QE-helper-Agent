"""
检查Celery和Redis连接
"""
import sys
from app.config import settings
from app.services.task_service import celery_app

def check_redis():
    """检查Redis连接"""
    try:
        import redis
        r = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True
        )
        r.ping()
        print(f"✓ Redis连接成功: {settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}")
        return True
    except Exception as e:
        print(f"✗ Redis连接失败: {str(e)}")
        print(f"  请确保Redis服务正在运行")
        return False

def check_celery():
    """检查Celery配置"""
    try:
        print(f"✓ Celery配置:")
        print(f"  Broker: {celery_app.conf.broker_url}")
        print(f"  Backend: {celery_app.conf.result_backend}")
        return True
    except Exception as e:
        print(f"✗ Celery配置检查失败: {str(e)}")
        return False

def check_active_workers():
    """检查活动的Worker"""
    try:
        inspect = celery_app.control.inspect()
        active_workers = inspect.active()
        if active_workers:
            print(f"✓ 发现 {len(active_workers)} 个活动的Worker:")
            for worker_name, tasks in active_workers.items():
                print(f"  - {worker_name}: {len(tasks)} 个任务")
        else:
            print("✗ 没有活动的Worker")
            print("  请运行: python run_celery.py")
        return active_workers is not None
    except Exception as e:
        print(f"✗ 无法检查Worker状态: {str(e)}")
        return False

def check_registered_tasks():
    """检查注册的任务"""
    try:
        inspect = celery_app.control.inspect()
        registered = inspect.registered()
        if registered:
            for worker_name, tasks in registered.items():
                print(f"✓ Worker '{worker_name}' 注册的任务:")
                for task_name in tasks:
                    if 'process_excel_task' in task_name:
                        print(f"  - {task_name} ✓")
                    else:
                        print(f"  - {task_name}")
        else:
            print("✗ 没有找到注册的任务")
        return registered is not None
    except Exception as e:
        print(f"✗ 无法检查注册的任务: {str(e)}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("Celery 诊断工具")
    print("=" * 50)
    print()
    
    redis_ok = check_redis()
    print()
    
    if not redis_ok:
        print("请先确保Redis服务正在运行！")
        sys.exit(1)
    
    check_celery()
    print()
    
    check_active_workers()
    print()
    
    check_registered_tasks()
    print()
    
    print("=" * 50)
    print("诊断完成")
    print("=" * 50)

