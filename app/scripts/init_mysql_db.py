"""
MySQL数据库初始化脚本
用于创建数据库和初始表结构
"""
import os
import sys
import time
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from pathlib import Path

# 将项目根目录添加到路径
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(ROOT_DIR))

# 加载环境变量
load_dotenv()

# 获取数据库连接信息
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "beauty_sales")


def init_database():
    """初始化MySQL数据库"""
    print("开始初始化MySQL数据库...")
    
    # 不指定数据库名创建连接，用于创建数据库
    connection_string = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/"
    
    try:
        # 创建没有指定数据库的引擎
        engine = create_engine(connection_string)
        
        # 创建数据库
        with engine.connect() as conn:
            conn.execute(text(f"CREATE DATABASE IF NOT EXISTS {DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
            print(f"数据库 {DB_NAME} 创建成功")
            
    except Exception as e:
        print(f"创建数据库时出错: {e}")
        sys.exit(1)
    
    # 等待数据库创建完成
    time.sleep(1)
    
    # 导入模型并创建表
    try:
        # 现在导入 app 模块，这样可以确保环境变量已经设置好
        from app.database import Base, engine
        from app.models import DataSource, ChatSession, ChatMessage, Visualization
        
        # 创建所有表
        Base.metadata.create_all(bind=engine)
        print("数据库表创建成功")
        
    except Exception as e:
        print(f"创建数据库表时出错: {e}")
        sys.exit(1)
    
    print("数据库初始化完成！")


if __name__ == "__main__":
    init_database() 