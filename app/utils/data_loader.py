"""
数据加载工具
支持从各种源加载数据
"""
import os
import logging
import pandas as pd
from typing import Optional
import sqlite3

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_data_from_source(file_path: str) -> Optional[pd.DataFrame]:
    """
    从不同类型的数据源加载数据
    
    参数:
        file_path: 数据文件路径
        
    返回:
        加载的数据框或None
    """
    try:
        # 检查文件是否存在
        if not os.path.exists(file_path):
            logger.error(f"文件不存在: {file_path}")
            return None
        
        # 根据文件扩展名加载不同类型的文件
        file_extension = os.path.splitext(file_path)[1].lower()
        
        if file_extension == '.csv':
            # 加载CSV文件
            logger.info(f"从CSV文件加载数据: {file_path}")
            return pd.read_csv(file_path)
            
        elif file_extension in ['.xlsx', '.xls']:
            # 加载Excel文件
            logger.info(f"从Excel文件加载数据: {file_path}")
            return pd.read_excel(file_path)
            
        elif file_extension in ['.db', '.sqlite']:
            # 加载SQLite数据库
            logger.info(f"从SQLite数据库加载数据: {file_path}")
            # 连接到数据库
            conn = sqlite3.connect(file_path)
            
            # 获取所有表
            table_query = "SELECT name FROM sqlite_master WHERE type='table';"
            tables = pd.read_sql_query(table_query, conn)
            
            if tables.empty:
                logger.error(f"数据库没有表: {file_path}")
                conn.close()
                return None
            
            # 默认加载第一个表
            table_name = tables.iloc[0, 0]
            logger.info(f"加载表: {table_name}")
            
            # 加载表数据
            df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
            conn.close()
            
            return df
        
        else:
            logger.error(f"不支持的文件类型: {file_extension}")
            return None
            
    except Exception as e:
        logger.error(f"加载数据时发生错误: {e}")
        return None

def get_table_names_from_db(db_path: str) -> list:
    """
    获取数据库中的所有表名
    
    参数:
        db_path: 数据库文件路径
        
    返回:
        表名列表
    """
    try:
        # 连接到数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 获取所有表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        # 关闭连接
        conn.close()
        
        return [table[0] for table in tables]
        
    except Exception as e:
        logger.error(f"获取表名时发生错误: {e}")
        return []

def load_table_from_db(db_path: str, table_name: str) -> Optional[pd.DataFrame]:
    """
    从数据库加载特定表
    
    参数:
        db_path: 数据库文件路径
        table_name: 表名
        
    返回:
        加载的数据框或None
    """
    try:
        # 连接到数据库
        conn = sqlite3.connect(db_path)
        
        # 加载表数据
        df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
        conn.close()
        
        return df
        
    except Exception as e:
        logger.error(f"加载表时发生错误: {e}")
        return None 