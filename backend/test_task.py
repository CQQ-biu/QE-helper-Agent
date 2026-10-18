"""
测试Celery任务执行
"""
import sys
from app.services.task_service import process_excel_task

# 测试一个简单的任务
if __name__ == "__main__":
    print("测试Celery任务执行...")
    print("=" * 50)
    
    try:
        # 这里需要提供一个实际存在的任务ID和文件路径
        # 你可以在数据库中查看一个任务记录
        test_task_id = input("请输入任务ID (task_id): ").strip()
        
        if not test_task_id:
            print("错误：需要提供任务ID")
            sys.exit(1)
        
        print(f"\n准备执行任务: {test_task_id}")
        print("注意：这会在Celery Worker中执行")
        print("请查看Worker终端的输出\n")
        
        # 注意：直接调用会同步执行，用于测试
        # 实际应该使用 .delay() 异步调用
        
    except KeyboardInterrupt:
        print("\n取消测试")
    except Exception as e:
        print(f"\n错误: {str(e)}")
        import traceback
        traceback.print_exc()

