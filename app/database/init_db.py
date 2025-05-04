"""
数据库初始化
"""
import os
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv()

# 获取数据库URL
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///app/database/beauty_sales.db")

# 创建数据库引擎
engine = create_engine(DATABASE_URL)

# 创建会话
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建基类
Base = declarative_base()

def get_db():
    """获取数据库连接"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_database():
    """初始化数据库"""
    try:
        # 检查数据库连接
        with engine.connect() as conn:
            logger.info("数据库连接成功")
            
            # 检查表是否存在
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = [row[0] for row in result]
            logger.info(f"发现数据库表: {tables}")
            
        # 创建所有表
        from app.models import models
        Base.metadata.create_all(bind=engine)
        logger.info("数据库表创建成功")
        
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        raise 