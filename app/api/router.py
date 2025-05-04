"""
API路由配置
"""
from fastapi import APIRouter
from app.api.endpoints import chat, data_upload, visualization

# 创建API路由器
api_router = APIRouter()

# 添加各个端点路由
api_router.include_router(chat.router, prefix="/chat", tags=["聊天"])
api_router.include_router(data_upload.router, prefix="/data", tags=["数据上传"])
api_router.include_router(visualization.router, prefix="/visualization", tags=["数据可视化"]) 