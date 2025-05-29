"""
美妆销售数据分析对话助手
基于Qwen3和Qwen-Agent实现
"""
import os
import uvicorn
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from app.api.router import api_router
from app.database.init_db import init_database
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 创建FastAPI应用
app = FastAPI(
    title="美妆销售数据分析对话助手",
    description="让业务人员通过自然语言与数据交互，快速获取数据洞察",
    version="1.0.0"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该指定具体的域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# 设置模板
templates = Jinja2Templates(directory="app/templates")

# 添加超时设置
app.add_middleware(
    middleware_class=lambda app: app,  # 这里可以添加自定义中间件
)

# 添加API路由
app.include_router(api_router, prefix="/api")

# 全局异常处理
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """全局异常处理器"""
    import traceback
    import logging
    
    logger = logging.getLogger(__name__)
    logger.error(f"全局异常: {exc}", exc_info=True)
    
    return {
        "error": "服务器内部错误",
        "detail": str(exc) if os.getenv("DEBUG", "False").lower() == "true" else "请联系管理员",
        "type": "internal_server_error"
    }

# 主页
@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# 健康检查端点
@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "service": "美妆销售数据分析助手",
        "version": "1.0.0"
    }

# 初始化数据库
@app.on_event("startup")
async def startup_event():
    init_database()

if __name__ == "__main__":
    # 获取配置
    debug = os.getenv("DEBUG", "True").lower() == "true"
    port = int(os.getenv("PORT", "8000"))
    
    # 启动应用
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=debug) 