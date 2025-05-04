"""
可视化API端点
"""
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.init_db import get_db
from app.models import models
from pydantic import BaseModel

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建路由
router = APIRouter()

# 可视化响应模型
class VisualizationResponse(BaseModel):
    """可视化响应"""
    id: int
    chat_session_id: int
    chart_type: str
    chart_data: str
    chart_title: str
    chart_description: Optional[str] = None

@router.get("/{visualization_id}", response_model=VisualizationResponse)
async def get_visualization(visualization_id: int, db: Session = Depends(get_db)):
    """获取指定的可视化"""
    visualization = db.query(models.Visualization).filter(
        models.Visualization.id == visualization_id
    ).first()
    
    if not visualization:
        raise HTTPException(status_code=404, detail="可视化不存在")
        
    return VisualizationResponse(
        id=visualization.id,
        chat_session_id=visualization.chat_session_id,
        chart_type=visualization.chart_type,
        chart_data=visualization.chart_data,
        chart_title=visualization.chart_title,
        chart_description=visualization.chart_description
    )

@router.get("/session/{session_id}", response_model=List[VisualizationResponse])
async def get_session_visualizations(session_id: str, db: Session = Depends(get_db)):
    """获取指定会话的所有可视化"""
    # 先获取会话
    session = db.query(models.ChatSession).filter(
        models.ChatSession.session_id == session_id
    ).first()
    
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    # 获取可视化
    visualizations = db.query(models.Visualization).filter(
        models.Visualization.chat_session_id == session.id
    ).all()
    
    return [
        VisualizationResponse(
            id=vis.id,
            chat_session_id=vis.chat_session_id,
            chart_type=vis.chart_type,
            chart_data=vis.chart_data,
            chart_title=vis.chart_title,
            chart_description=vis.chart_description
        )
        for vis in visualizations
    ] 