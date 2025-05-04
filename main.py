"""
美妆销售数据分析对话助手
基于Qwen3和Qwen-Agent实现
"""
import os
import uvicorn
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
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

# 挂载静态文件
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# 设置模板
templates = Jinja2Templates(directory="app/templates")

# 添加API路由
app.include_router(api_router, prefix="/api")

# 主页
@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

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