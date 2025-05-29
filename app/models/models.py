"""
数据库模型
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database import Base

class DataSource(Base):
    """数据源模型"""
    __tablename__ = "data_sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), index=True)
    description = Column(Text, nullable=True)
    file_path = Column(String(500), nullable=True)  # 文件路径，对于预配置数据源可为空
    file_type = Column(String(50))  # csv, excel, db, postgres
    is_predefined = Column(Integer, default=0)  # 0: 用户上传, 1: 预配置数据源
    connection_config = Column(Text, nullable=True)  # 数据库连接配置的JSON字符串
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # 关联
    chat_sessions = relationship("ChatSession", back_populates="data_source")

class ChatSession(Base):
    """聊天会话模型"""
    __tablename__ = "chat_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(50), unique=True, index=True)
    data_source_id = Column(Integer, ForeignKey("data_sources.id"))
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 关联
    data_source = relationship("DataSource", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="chat_session")
    visualizations = relationship("Visualization", back_populates="chat_session")

class ChatMessage(Base):
    """聊天消息模型"""
    __tablename__ = "chat_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    chat_session_id = Column(Integer, ForeignKey("chat_sessions.id"))
    role = Column(String(20))  # user, assistant
    content = Column(LONGTEXT)  # 使用MySQL的LONGTEXT类型，适合存储大量文本内容
    created_at = Column(DateTime, default=datetime.now)
    
    # 关联
    chat_session = relationship("ChatSession", back_populates="messages")

class Visualization(Base):
    """可视化模型"""
    __tablename__ = "visualizations"
    
    id = Column(Integer, primary_key=True, index=True)
    chat_session_id = Column(Integer, ForeignKey("chat_sessions.id"))
    chart_type = Column(String(50))  # line, bar, pie
    chart_data = Column(LONGTEXT)  # JSON格式的图表数据，使用LONGTEXT类型
    chart_title = Column(String(255))
    chart_description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    
    # 关联
    chat_session = relationship("ChatSession", back_populates="visualizations") 