"""
聊天API端点
"""
import os
import uuid
import logging
import json
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from app.agents.main_agent import MainAgent
from app.utils.data_loader import load_data_from_source
from app.database.init_db import get_db
from app.models import models
from pydantic import BaseModel

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建路由
router = APIRouter()

# 请求模型
class ChatRequest(BaseModel):
    """聊天请求"""
    session_id: Optional[str] = None
    message: str
    data_source_id: Optional[int] = None

# 响应模型
class ChatResponse(BaseModel):
    """聊天响应"""
    session_id: str
    response: str
    visualization_id: Optional[int] = None

# 创建主控Agent
main_agent = MainAgent()

@router.post("/", response_model=ChatResponse)
async def chat(
    chat_request: ChatRequest = Body(...),
    db: Session = Depends(get_db)
):
    """处理聊天请求"""
    try:
        # 获取或创建会话ID
        session_id = chat_request.session_id or str(uuid.uuid4())
        
        # 获取会话
        chat_session = db.query(models.ChatSession).filter(
            models.ChatSession.session_id == session_id
        ).first()
        
        # 如果没有会话，创建一个新的
        if not chat_session:
            # 检查数据源
            if not chat_request.data_source_id:
                raise HTTPException(status_code=400, detail="首次对话需要指定数据源ID")
                
            # 获取数据源
            data_source = db.query(models.DataSource).filter(
                models.DataSource.id == chat_request.data_source_id
            ).first()
            
            if not data_source:
                raise HTTPException(status_code=404, detail="数据源不存在")
                
            # 创建新会话
            chat_session = models.ChatSession(
                session_id=session_id,
                data_source_id=data_source.id
            )
            db.add(chat_session)
            db.commit()
            db.refresh(chat_session)
            
        # 创建用户消息
        user_message = models.ChatMessage(
            chat_session_id=chat_session.id,
            role="user",
            content=chat_request.message
        )
        db.add(user_message)
        db.commit()
        
        # 获取历史消息
        messages = db.query(models.ChatMessage).filter(
            models.ChatMessage.chat_session_id == chat_session.id
        ).order_by(models.ChatMessage.created_at).all()
        
        # 将历史消息转换为Agent可用的格式，并更新会话状态
        conversation_history = [{"role": msg.role, "content": msg.content} for msg in messages]
        # 更新MainAgent的会话历史
        main_agent.session_state["conversation_history"] = conversation_history
        
        # 获取数据源
        data_source = chat_session.data_source
        
        # 加载数据并初始化必要的Agent
        if data_source.file_type == "database":
            # 初始化SQL Agent
            if not main_agent.initialize_sql_agent(data_source.file_path):
                raise HTTPException(status_code=500, detail="初始化SQL Agent失败")
        else:
            # 加载数据文件
            data = load_data_from_source(data_source.file_path)
            if data is not None:
                main_agent.data_agent.load_data_from_df(data)
                main_agent.session_state["current_data_path"] = data_source.file_path
        
        # 处理聊天请求
        chat_result = main_agent.process_query(chat_request.message)
        
        # 保存助手回复
        assistant_message = models.ChatMessage(
            chat_session_id=chat_session.id,
            role="assistant",
            content=chat_result["response"]
        )
        db.add(assistant_message)
        db.commit()
        
        # 处理可视化
        visualization_id = None
        if chat_result.get("visualization"):
            visualization = models.Visualization(
                chat_session_id=chat_session.id,
                chart_type=chat_result["visualization"].get("type", "bar"),
                chart_data=json.dumps(chat_result["visualization"].get("data", {})),
                chart_title=chat_result["visualization"].get("title", "数据可视化"),
                chart_description=chat_result["visualization"].get("description", "")
            )
            db.add(visualization)
            db.commit()
            db.refresh(visualization)
            visualization_id = visualization.id
        
        # 返回响应
        return ChatResponse(
            session_id=session_id,
            response=chat_result["response"],
            visualization_id=visualization_id
        )
        
    except Exception as e:
        logger.error(f"处理聊天请求时发生错误: {e}")
        raise HTTPException(status_code=500, detail=f"处理聊天请求时发生错误: {str(e)}")


@router.get("/sessions")
async def get_sessions(db: Session = Depends(get_db)):
    """获取所有聊天会话"""
    sessions = db.query(models.ChatSession).all()
    return sessions


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, db: Session = Depends(get_db)):
    """获取指定会话的消息"""
    session = db.query(models.ChatSession).filter(
        models.ChatSession.session_id == session_id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
        
    messages = db.query(models.ChatMessage).filter(
        models.ChatMessage.chat_session_id == session.id
    ).order_by(models.ChatMessage.created_at).all()
    
    return messages 