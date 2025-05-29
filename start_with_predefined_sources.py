#!/usr/bin/env python3
"""
启动脚本 - 包含预配置数据源初始化
"""
import os
import sys
import logging
from dotenv import load_dotenv

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_environment():
    """检查环境变量配置"""
    required_vars = [
        'QWEN_API_KEY',
        'DB_PASSWORD',
        'POSTGRES_PASSWORD'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"缺少必要的环境变量: {', '.join(missing_vars)}")
        logger.error("请检查 .env 文件配置")
        return False
    
    return True

def migrate_database():
    """运行数据库迁移"""
    try:
        logger.info("运行数据库迁移...")
        from app.scripts.migrate_database import migrate_database
        migrate_database()
        logger.info("数据库迁移完成")
    except Exception as e:
        logger.warning(f"数据库迁移失败: {e}")
        logger.info("如果是首次运行，这是正常的")

def init_predefined_sources():
    """初始化预配置数据源"""
    try:
        logger.info("初始化预配置数据源...")
        from app.scripts.init_predefined_datasources import init_predefined_datasources
        init_predefined_datasources()
        logger.info("预配置数据源初始化完成")
    except Exception as e:
        logger.error(f"预配置数据源初始化失败: {e}")

def start_application():
    """启动应用"""
    try:
        logger.info("启动美妆销售数据分析助手...")
        import uvicorn
        from main import app
        
        # 获取配置
        debug = os.getenv("DEBUG", "True").lower() == "true"
        port = int(os.getenv("PORT", "8000"))
        
        # 启动应用
        uvicorn.run(app, host="0.0.0.0", port=port, reload=debug)
        
    except Exception as e:
        logger.error(f"启动应用失败: {e}")
        sys.exit(1)

def main():
    """主函数"""
    print("=" * 60)
    print("美妆销售数据分析助手 - 启动程序")
    print("支持预配置数据源功能")
    print("=" * 60)
    
    # 加载环境变量
    load_dotenv()
    
    # 检查环境变量
    if not check_environment():
        sys.exit(1)
    
    # 运行数据库迁移
    migrate_database()
    
    # 初始化预配置数据源
    init_predefined_sources()
    
    # 启动应用
    start_application()

if __name__ == "__main__":
    main()
