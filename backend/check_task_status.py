"""
查看数据库中的任务状态
"""
from app.db.database import SessionLocal
from app.models import TaskRecord, ExcelFile, SystemLog
from sqlalchemy import desc

def list_tasks():
    """列出所有任务"""
    db = SessionLocal()
    try:
        tasks = db.query(TaskRecord).order_by(desc(TaskRecord.created_at)).limit(10).all()
        
        if not tasks:
            print("数据库中没有任务记录")
            return
        
        print("=" * 80)
        print("最近10个任务记录:")
        print("=" * 80)
        
        for task in tasks:
            print(f"\n任务ID: {task.task_id}")
            print(f"  状态: {task.status}")
            print(f"  客户名称: {task.customer_name}")
            print(f"  客户类型: {task.customer_type}")
            print(f"  工号: {task.work_number}")
            print(f"  创建时间: {task.created_at}")
            print(f"  更新时间: {task.updated_at}")
            
            # 查找关联的文件
            files = db.query(ExcelFile).filter(ExcelFile.task_id == task.id).all()
            if files:
                print(f"  关联文件数: {len(files)}")
                for f in files:
                    print(f"    - {f.file_name} ({f.file_type})")
                    if f.processed_file_path:
                        print(f"      处理后文件: {f.processed_file_path}")
        
        print("\n" + "=" * 80)
        
        # 查看最新的任务详情
        if tasks:
            latest_task = tasks[0]
            print(f"\n最新任务详情 (task_id: {latest_task.task_id}):")
            print(f"  状态: {latest_task.status}")
            
            # 查看相关日志
            logs = db.query(SystemLog).filter(
                SystemLog.task_id == latest_task.task_id
            ).order_by(desc(SystemLog.created_at)).limit(5).all()
            
            if logs:
                print(f"\n  最近5条日志:")
                for log in logs:
                    print(f"    [{log.level}] {log.module}: {log.message}")
                    if log.details:
                        print(f"      详情: {log.details[:100]}...")
            
    except Exception as e:
        print(f"查询失败: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

def show_task_detail(task_id: str):
    """显示指定任务的详细信息"""
    db = SessionLocal()
    try:
        task = db.query(TaskRecord).filter(TaskRecord.task_id == task_id).first()
        
        if not task:
            print(f"任务不存在: {task_id}")
            return
        
        print("=" * 80)
        print(f"任务详情: {task_id}")
        print("=" * 80)
        print(f"状态: {task.status}")
        print(f"客户名称: {task.customer_name}")
        print(f"客户类型: {task.customer_type}")
        print(f"工号: {task.work_number}")
        print(f"填表日期: {task.fill_date}")
        print(f"答案语言: {task.answer_language}")
        print(f"最高分数: {task.max_score}")
        print(f"创建时间: {task.created_at}")
        print(f"更新时间: {task.updated_at}")
        
        # 文件信息
        files = db.query(ExcelFile).filter(ExcelFile.task_id == task.id).all()
        if files:
            print(f"\n关联文件:")
            for f in files:
                print(f"  - {f.file_name}")
                print(f"    类型: {f.file_type}")
                print(f"    路径: {f.file_path}")
                if f.processed_file_path:
                    print(f"    处理后: {f.processed_file_path}")
                if f.excel_config:
                    print(f"    配置: {f.excel_config[:200]}...")
        
        # 日志信息
        logs = db.query(SystemLog).filter(
            SystemLog.task_id == task_id
        ).order_by(desc(SystemLog.created_at)).all()
        
        if logs:
            print(f"\n日志记录 (共{len(logs)}条):")
            for log in logs:
                print(f"  [{log.created_at.strftime('%Y-%m-%d %H:%M:%S')}] [{log.level}] {log.module}: {log.message}")
                if log.details:
                    print(f"    详情: {log.details}")
        else:
            print("\n无日志记录")
        
        print("=" * 80)
        
    except Exception as e:
        print(f"查询失败: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # 显示指定任务的详情
        task_id = sys.argv[1]
        show_task_detail(task_id)
    else:
        # 列出所有任务
        list_tasks()
        print("\n提示: 使用 'python check_task_status.py <task_id>' 查看指定任务的详细信息")

