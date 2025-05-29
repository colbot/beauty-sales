"""
数据库迁移脚本 - 为现有数据源表添加新字段
"""
import os
import logging
from sqlalchemy import create_engine, text, Column, Integer, Text
from sqlalchemy.orm import sessionmaker
from app.database.init_db import engine, SessionLocal
from app.models import models

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_database():
    """迁移数据库，添加新字段"""
    try:
        with engine.connect() as conn:
            # 检查是否需要添加新字段
            try:
                # 检查 is_predefined 字段是否存在
                result = conn.execute(text("DESCRIBE data_sources"))
                columns = [row[0] for row in result]
                
                if 'is_predefined' not in columns:
                    logger.info("添加 is_predefined 字段...")
                    conn.execute(text("ALTER TABLE data_sources ADD COLUMN is_predefined INT DEFAULT 0"))
                    conn.commit()
                    logger.info("is_predefined 字段添加成功")
                else:
                    logger.info("is_predefined 字段已存在")
                
                if 'connection_config' not in columns:
                    logger.info("添加 connection_config 字段...")
                    conn.execute(text("ALTER TABLE data_sources ADD COLUMN connection_config TEXT"))
                    conn.commit()
                    logger.info("connection_config 字段添加成功")
                else:
                    logger.info("connection_config 字段已存在")
                
                # 修改 file_path 字段为可空
                logger.info("修改 file_path 字段为可空...")
                conn.execute(text("ALTER TABLE data_sources MODIFY COLUMN file_path VARCHAR(500) NULL"))
                conn.commit()
                logger.info("file_path 字段修改成功")
                
            except Exception as e:
                logger.error(f"迁移过程中发生错误: {e}")
                conn.rollback()
                raise
                
        logger.info("数据库迁移完成")
        
    except Exception as e:
        logger.error(f"数据库迁移失败: {e}")
        raise

if __name__ == "__main__":
    migrate_database()
