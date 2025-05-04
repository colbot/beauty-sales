"""
数据上传API端点
"""
import os
import shutil
import uuid
import logging
from typing import Optional
from fastapi import (
    APIRouter, Depends, HTTPException, 
    File, UploadFile, Form, status
)
from sqlalchemy.orm import Session
from app.database.init_db import get_db
from app.models import models
from pydantic import BaseModel

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 创建路由
router = APIRouter()

# 数据源响应模型
class DataSourceResponse(BaseModel):
    """数据源响应"""
    id: int
    name: str
    description: Optional[str] = None
    file_type: str

# 创建数据存储目录
DATA_DIR = os.path.join("app", "database", "data")
os.makedirs(DATA_DIR, exist_ok=True)

@router.post("/upload", response_model=DataSourceResponse, status_code=status.HTTP_201_CREATED)
async def upload_data(
    file: UploadFile = File(...),
    name: str = Form(...),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    """上传数据文件"""
    try:
        # 检查文件类型
        file_extension = os.path.splitext(file.filename)[1].lower()
        
        if file_extension not in [".csv", ".xlsx", ".xls", ".db", ".sqlite"]:
            raise HTTPException(
                status_code=400,
                detail="不支持的文件类型，仅支持CSV、Excel和SQLite数据库文件"
            )
        
        # 生成唯一文件名
        unique_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = os.path.join(DATA_DIR, unique_filename)
        
        # 保存文件
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 确定文件类型
        if file_extension in [".csv"]:
            file_type = "csv"
        elif file_extension in [".xlsx", ".xls"]:
            file_type = "excel"
        else:
            file_type = "database"
        
        # 创建数据源记录
        data_source = models.DataSource(
            name=name,
            description=description,
            file_path=file_path,
            file_type=file_type
        )
        db.add(data_source)
        db.commit()
        db.refresh(data_source)
        
        return DataSourceResponse(
            id=data_source.id,
            name=data_source.name,
            description=data_source.description,
            file_type=data_source.file_type
        )
        
    except Exception as e:
        logger.error(f"上传数据文件时发生错误: {e}")
        raise HTTPException(status_code=500, detail=f"上传数据文件时发生错误: {str(e)}")


@router.get("/sources", response_model=list[DataSourceResponse])
async def get_data_sources(db: Session = Depends(get_db)):
    """获取所有数据源"""
    data_sources = db.query(models.DataSource).all()
    return [
        DataSourceResponse(
            id=source.id,
            name=source.name,
            description=source.description,
            file_type=source.file_type
        )
        for source in data_sources
    ]


@router.get("/sources/{source_id}", response_model=DataSourceResponse)
async def get_data_source(source_id: int, db: Session = Depends(get_db)):
    """获取指定数据源"""
    data_source = db.query(models.DataSource).filter(models.DataSource.id == source_id).first()
    
    if not data_source:
        raise HTTPException(status_code=404, detail="数据源不存在")
        
    return DataSourceResponse(
        id=data_source.id,
        name=data_source.name,
        description=data_source.description,
        file_type=data_source.file_type
    ) 