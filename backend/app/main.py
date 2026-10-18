"""
FastAPI主应用
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.api import upload, download
from app.db.database import initialize_database
from app import models  # noqa: F401，确保所有ORM模型在建表前完成注册
from app.utils.logger import logger

# 启用pgvector并创建数据库表
initialize_database()

# 创建FastAPI应用
app = FastAPI(
    title="QE Helper API",
    description="Excel问答处理系统",
    version="1.0.0"
)

# 配置CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(upload.router, prefix=settings.API_V1_PREFIX, tags=["上传"])
app.include_router(download.router, prefix=settings.API_V1_PREFIX, tags=["下载"])


@app.get("/")
async def root():
    """根路径"""
    return {"message": "QE Helper API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

