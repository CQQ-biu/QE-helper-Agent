"""
启动脚本
"""
import uvicorn

if __name__ == "__main__":
    # 使用导入字符串以支持reload功能
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )


