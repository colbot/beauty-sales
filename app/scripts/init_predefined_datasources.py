"""
初始化预配置数据源
"""
import os
import json
import logging
from sqlalchemy.orm import Session
from app.database.init_db import get_db
from app.models import models

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_predefined_datasources():
    """初始化预配置数据源"""
    try:
        # 获取数据库会话
        db = next(get_db())
        
        # 检查是否已存在预配置数据源
        existing_predefined = db.query(models.DataSource).filter(
            models.DataSource.is_predefined == 1
        ).first()
        
        if existing_predefined:
            logger.info("预配置数据源已存在，跳过初始化")
            return
        
        # 从环境变量获取PostgreSQL连接配置
        postgres_config = {
            "host": os.getenv("POSTGRES_HOST", "localhost"),
            "port": int(os.getenv("POSTGRES_PORT", "5432")),
            "user": os.getenv("POSTGRES_USER", "postgres"),
            "password": os.getenv("POSTGRES_PASSWORD", ""),
            "database": os.getenv("POSTGRES_DATABASE", "beauty_sales")
        }
        
        # 创建欧莱雅官方销售数据源
        loreal_datasource = models.DataSource(
            name="欧莱雅官方销售数据",
            description="连接到欧莱雅官方PostgreSQL数据库，包含完整的销售数据、产品信息和客户数据",
            file_path=None,  # 预配置数据源不需要文件路径
            file_type="postgres",
            is_predefined=1,
            connection_config=json.dumps(postgres_config)
        )
        
        db.add(loreal_datasource)
        db.commit()
        db.refresh(loreal_datasource)
        
        logger.info(f"成功创建预配置数据源: {loreal_datasource.name} (ID: {loreal_datasource.id})")
        
        # 可以添加更多预配置数据源
        # 例如：其他品牌的数据源
        
    except Exception as e:
        logger.error(f"初始化预配置数据源时发生错误: {e}")
        if 'db' in locals():
            db.rollback()
    finally:
        if 'db' in locals():
            db.close()

if __name__ == "__main__":
    init_predefined_datasources()
