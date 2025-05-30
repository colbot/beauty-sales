"""
聊天API端点
"""
import os
import uuid
import logging
import json
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Body
from fastapi.responses import StreamingResponse
import asyncio
from sqlalchemy.orm import Session
from app.agents.main_agent import MainAgent
from app.utils.data_loader import load_data_from_source
from app.database.init_db import get_db
from app.models import models
from pydantic import BaseModel
import time

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

# 新会话请求模型
class NewSessionRequest(BaseModel):
    """新会话请求"""
    data_source_id: int

# 新会话响应模型
class NewSessionResponse(BaseModel):
    """新会话响应"""
    session_id: str
    message: str

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
            # 连接数据库
            db_params = {"path": data_source.file_path}
            if not main_agent.connect_database(db_params):
                raise HTTPException(status_code=500, detail="连接数据库失败")
        else:
            # 加载数据文件
            data = load_data_from_source(data_source.file_path)
            if data is not None:
                main_agent.data_agent.load_data_from_df(data)
                main_agent.session_state["current_data_path"] = data_source.file_path
                # 同步数据到其他Agent
                main_agent._sync_data_between_agents()
        
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
            # 检查visualization是字符串还是字典对象
            vis_data = chat_result["visualization"]
            
            # 如果是base64字符串，构建合适的对象结构
            if isinstance(vis_data, str):
                chart_data = {"image": vis_data}
                chart_type = "image"
                chart_title = "数据可视化"
                chart_description = chat_result.get("description", "")
            else:
                # 如果是对象，直接使用其属性
                chart_data = vis_data.get("data", {})
                chart_type = vis_data.get("type", "bar")
                chart_title = vis_data.get("title", "数据可视化")
                chart_description = vis_data.get("description", "")
            
            # 创建可视化记录
            visualization = models.Visualization(
                chat_session_id=chat_session.id,
                chart_type=chart_type,
                chart_data=json.dumps(chart_data),
                chart_title=chart_title,
                chart_description=chart_description
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


@router.post("/new", response_model=NewSessionResponse)
async def create_new_session(
    request: NewSessionRequest = Body(...),
    db: Session = Depends(get_db)
):
    """创建新的会话，清空当前页面的历史会话"""
    try:
        # 验证数据源是否存在
        data_source = db.query(models.DataSource).filter(
            models.DataSource.id == request.data_source_id
        ).first()
        
        if not data_source:
            raise HTTPException(status_code=404, detail="数据源不存在")
        
        # 生成新的会话ID
        session_id = str(uuid.uuid4())
        
        # 创建新会话
        chat_session = models.ChatSession(
            session_id=session_id,
            data_source_id=data_source.id
        )
        db.add(chat_session)
        db.commit()
        
        # 重置主Agent的会话状态
        main_agent.reset_session()
        
        # 加载数据
        if data_source.file_type == "database":
            # 连接数据库
            db_params = {"path": data_source.file_path}
            if not main_agent.connect_database(db_params):
                raise HTTPException(status_code=500, detail="连接数据库失败")
        else:
            # 加载数据文件
            data = load_data_from_source(data_source.file_path)
            if data is not None:
                main_agent.data_agent.load_data_from_df(data)
                main_agent.session_state["current_data_path"] = data_source.file_path
        
        return NewSessionResponse(
            session_id=session_id,
            message="新会话已创建"
        )
        
    except Exception as e:
        logger.error(f"创建新会话时发生错误: {e}")
        raise HTTPException(status_code=500, detail=f"创建新会话时发生错误: {str(e)}")


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

@router.post("/stream")
async def stream_chat(
    chat_request: ChatRequest = Body(...),
    db: Session = Depends(get_db)
):
    """流式处理聊天请求，实时返回分析过程"""
    async def generate_response():
        try:
            # 设置响应超时保护
            MAX_PROCESSING_TIME = 180  # 最大处理时间为3分钟
            start_time = time.time()
            
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
                    yield json.dumps({"error": "首次对话需要指定数据源ID"}) + "\n"
                    return
                    
                # 获取数据源
                data_source = db.query(models.DataSource).filter(
                    models.DataSource.id == chat_request.data_source_id
                ).first()
                
                if not data_source:
                    yield json.dumps({"error": "数据源不存在"}) + "\n"
                    return
                    
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
            # 限制历史消息数量，避免传输过大
            max_messages = 10
            recent_messages = messages[-max_messages:] if len(messages) > max_messages else messages
            conversation_history = [{"role": msg.role, "content": msg.content} for msg in recent_messages]
            
            # 更新MainAgent的会话历史
            main_agent.session_state["conversation_history"] = conversation_history
            
            # 获取数据源
            data_source = chat_session.data_source
            
            # 加载数据并初始化必要的Agent
            if data_source.file_type == "database":
                # 连接数据库
                db_params = {"path": data_source.file_path}
                if not main_agent.connect_database(db_params):
                    yield json.dumps({"error": "连接数据库失败"}) + "\n"
                    return
            else:
                # 加载数据文件
                data = load_data_from_source(data_source.file_path)
                if data is not None:
                    main_agent.data_agent.load_data_from_df(data)
                    main_agent.session_state["current_data_path"] = data_source.file_path
                    # 同步数据到其他Agent
                    main_agent._sync_data_between_agents()
            
            # 处理聊天请求，流式返回处理过程
            final_response = None
            visualization_id = None
            
            # 发送初始的流式信息
            yield json.dumps({
                "type": "start",
                "content": {
                    "session_id": session_id
                }
            }) + "\n"
            
            # 流式处理查询
            for response_chunk in main_agent.process_query(chat_request.message):
                # 检查处理时间是否超时
                current_time = time.time()
                if current_time - start_time > MAX_PROCESSING_TIME:
                    # 超时处理
                    yield json.dumps({
                        "type": "warning",
                        "content": {
                            "message": "处理时间过长，已自动中断。请尝试简化您的问题或分多次询问。"
                        }
                    }) + "\n"
                    break
                
                # 如果是最终结果，保存它
                if response_chunk["type"] == "final":
                    final_response = response_chunk["content"]["response"]
                    # 如果有可视化结果，保存它
                    if response_chunk["content"].get("visualization"):
                        # 检查visualization是字符串还是字典对象
                        vis_data = response_chunk["content"]["visualization"]
                        
                        # 如果是base64字符串，构建合适的对象结构
                        if isinstance(vis_data, str):
                            chart_data = {"image": vis_data}
                            chart_type = "image"
                            chart_title = "数据可视化"
                            chart_description = response_chunk["content"].get("description", "")
                        else:
                            # 如果是对象，直接使用其属性
                            chart_data = vis_data.get("data", {})
                            chart_type = vis_data.get("type", "bar")
                            chart_title = vis_data.get("title", "数据可视化")
                            chart_description = vis_data.get("description", "")
                        
                        # 创建可视化记录
                        visualization = models.Visualization(
                            chat_session_id=chat_session.id,
                            chart_type=chart_type,
                            chart_data=json.dumps(chart_data),
                            chart_title=chart_title,
                            chart_description=chart_description
                        )
                        db.add(visualization)
                        db.commit()
                        db.refresh(visualization)
                        visualization_id = visualization.id
                        response_chunk["content"]["visualization_id"] = visualization_id
                
                # 优化响应大小，压缩超大的响应
                try:
                    # 对于expert_start, intermediate, final等类型的响应，检查并限制数据大小
                    if "content" in response_chunk and isinstance(response_chunk["content"], dict):
                        if "result" in response_chunk["content"] and isinstance(response_chunk["content"]["result"], dict):
                            # 如果响应文本超过50KB，截断它
                            if "response" in response_chunk["content"]["result"] and isinstance(response_chunk["content"]["result"]["response"], str):
                                response_text = response_chunk["content"]["result"]["response"]
                                if len(response_text) > 50000:  # 约50KB
                                    response_chunk["content"]["result"]["response"] = response_text[:50000] + "...(响应过长，已截断)"
                    
                    # 检查可视化数据是否太大
                    if "content" in response_chunk and isinstance(response_chunk["content"], dict) and "visualization" in response_chunk["content"]:
                        vis_data = response_chunk["content"]["visualization"]
                        if isinstance(vis_data, str) and len(vis_data) > 500000:  # 约500KB
                            # 可视化数据太大，移除它并添加警告
                            response_chunk["content"]["visualization"] = None
                            response_chunk["content"]["visualization_warning"] = "可视化数据过大，无法在聊天界面显示。请查看结果部分的可视化摘要。"
                except Exception as e:
                    logger.warning(f"优化响应大小时出错: {e}")
                
                # 发送流式结果
                try:
                    chunk_json = json.dumps(response_chunk)
                    yield chunk_json + "\n"
                    
                    # 强制刷新响应流，避免缓冲问题
                    await asyncio.sleep(0.01)
                except Exception as chunk_error:
                    logger.error(f"发送流式结果块时出错: {chunk_error}")
                    # 如果单个块发送失败，尝试发送一个简化版本
                    yield json.dumps({
                        "type": response_chunk.get("type", "unknown"),
                        "content": {"message": "处理中..."}
                    }) + "\n"
            
            # 如果没有最终响应，但处理过程中断，生成一个合理的响应
            if not final_response:
                final_response = "处理您的问题时遇到了困难，可能是因为问题过于复杂或数据量过大。请尝试简化您的问题，或者分多次询问不同的方面。"
            
            # 保存助手回复
            if final_response:
                assistant_message = models.ChatMessage(
                    chat_session_id=chat_session.id,
                    role="assistant",
                    content=final_response
                )
                db.add(assistant_message)
                db.commit()
            
            # 发送最终完成信息
            yield json.dumps({
                "type": "complete",
                "content": {
                    "session_id": session_id,
                    "visualization_id": visualization_id
                }
            }) + "\n"
            
        except Exception as e:
            logger.error(f"流式处理聊天请求时发生错误: {e}", exc_info=True)
            # 简化错误消息，避免发送过大的堆栈
            error_message = str(e)
            if len(error_message) > 1000:
                error_message = error_message[:1000] + "...(错误信息过长，已截断)"
                
            yield json.dumps({
                "error": "处理聊天请求时发生错误",
                "message": error_message
            }) + "\n"
    
    # 返回流式响应，添加响应头以优化流式传输
    return StreamingResponse(
        generate_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # 禁用Nginx的缓冲
        }
    ) 