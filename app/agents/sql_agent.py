"""
SQL Agent
负责把自然语言转换为SQL查询，并处理数据库操作
"""
import os
import logging
import pandas as pd
import json
from typing import Dict, List, Any, Optional, Union, Tuple
from sqlalchemy import create_engine, MetaData, Table, text
from qwen_agent.agents import Assistant

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SQLAgent:
    """SQL Agent，负责数据库操作和自然语言转SQL"""
    
    def __init__(self, db_params: Optional[Dict[str, Any]] = None):
        """初始化SQL Agent
        
        参数:
            db_params: 数据库连接参数，包含host, port, user, password, database等
        """
        # 获取API密钥和模型名称
        api_key = os.getenv("QWEN_API_KEY")
        model_name = os.getenv("QWEN_MODEL", "qwen-max")
        
        # 基础LLM配置
        self.llm_cfg = {
            'model': model_name,
            'model_server': 'dashscope',
            'api_key': api_key,
        }
        
        # 创建SQL Assistant实例
        self.sql_agent = Assistant(
            llm=self.llm_cfg,
            name='SQL专家',
            description='专精于将自然语言转换为SQL查询，并能解释SQL查询结果'
        )
        
        # 数据库连接
        self.engine = None
        self.conn = None
        self.db_name = None
        self.tables_info = {}
        
        # 如果提供了数据库参数，立即连接
        if db_params:
            self.connect_db(db_params)
            
        # 查询历史
        self.query_history = []
    
    def connect_db(self, db_params: Dict[str, Any]) -> bool:
        """连接到MySQL数据库
        
        参数:
            db_params: 数据库连接参数字典，包含host, port, user, password, database等
            
        返回:
            是否成功连接
        """
        try:
            # 关闭现有连接
            if self.conn:
                self.conn.close()
            
            # 构建MySQL连接URI
            host = db_params.get('host', 'localhost')
            port = db_params.get('port', 3306)
            user = db_params.get('user', 'root')
            password = db_params.get('password', '')
            database = db_params.get('database', 'beauty_sales')
            
            connection_string = f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}"
            
            # 创建引擎和连接
            self.engine = create_engine(connection_string)
            self.conn = self.engine.connect()
            self.db_name = database
            
            # 获取数据库表信息
            self._get_db_schema()
            
            logger.info(f"成功连接到MySQL数据库: {host}:{port}/{database}")
            return True
            
        except Exception as e:
            logger.error(f"连接数据库时发生错误: {e}")
            return False
    
    def _get_db_schema(self) -> None:
        """获取数据库表结构信息"""
        if not self.conn:
            logger.warning("未连接数据库，无法获取表结构")
            return
        
        try:
            # 使用SQLAlchemy获取表信息
            metadata = MetaData()
            metadata.reflect(bind=self.engine)
            
            # 清空现有表信息
            self.tables_info = {}
            
            # 获取每个表的结构
            for table_name in metadata.tables.keys():
                # 跳过系统表
                if table_name.startswith('information_schema.') or table_name.startswith('performance_schema.') or table_name.startswith('mysql.'):
                    continue
                
                table = metadata.tables[table_name]
                
                # 整理表结构信息
                columns_info = {}
                for column in table.columns:
                    columns_info[column.name] = {
                        "type": str(column.type),
                        "not_null": not column.nullable,
                        "default": str(column.default.arg) if column.default and column.default.arg else None,
                        "primary_key": column.primary_key
                    }
                
                # 获取表中的数据示例
                query = f"SELECT * FROM `{table_name}` LIMIT 5"  # 使用反引号包围表名，MySQL语法
                sample_data = pd.read_sql_query(query, self.conn)
                
                # 保存表信息
                self.tables_info[table_name] = {
                    "columns": columns_info,
                    "sample_data": sample_data.values.tolist()
                }
            
            logger.info(f"成功获取数据库表结构，共 {len(self.tables_info)} 个表")
            
        except Exception as e:
            logger.error(f"获取数据库表结构时发生错误: {e}")
            self.tables_info = {}
    
    def get_db_schema_text(self) -> str:
        """获取数据库结构的文本描述
        
        返回:
            数据库结构描述文本
        """
        if not self.tables_info:
            return "未获取到数据库表结构信息"
        
        schema_text = "数据库表结构:\n\n"
        
        for table_name, table_info in self.tables_info.items():
            schema_text += f"表: {table_name}\n"
            schema_text += "列名\t类型\t是否主键\t是否允许为空\t默认值\n"
            schema_text += "-" * 60 + "\n"
            
            for col_name, col_info in table_info["columns"].items():
                pk_str = "是" if col_info["primary_key"] else "否"
                not_null_str = "否" if col_info["not_null"] else "是"
                default_val = col_info["default"] if col_info["default"] is not None else "NULL"
                
                schema_text += f"{col_name}\t{col_info['type']}\t{pk_str}\t{not_null_str}\t{default_val}\n"
            
            schema_text += "\n数据示例:\n"
            if table_info["sample_data"]:
                # 获取列名
                col_names = list(table_info["columns"].keys())
                # 添加列名行
                schema_text += "\t".join(col_names) + "\n"
                schema_text += "-" * 60 + "\n"
                
                # 添加示例数据
                for row in table_info["sample_data"]:
                    schema_text += "\t".join([str(val) for val in row]) + "\n"
            else:
                schema_text += "无数据\n"
            
            schema_text += "\n" + "=" * 80 + "\n\n"
        
        return schema_text
    
    def execute_sql(self, sql: str) -> Dict[str, Any]:
        """执行SQL查询
        
        参数:
            sql: SQL查询语句
            
        返回:
            查询结果
        """
        if not self.conn:
            return {
                "success": False,
                "error": "未连接数据库",
                "sql": sql,
                "data": None
            }
        
        try:
            # 执行查询
            df = pd.read_sql_query(sql, self.conn)
            
            # 记录到查询历史
            self.query_history.append({
                "sql": sql,
                "rows": len(df),
                "columns": list(df.columns),
                "success": True,
                "timestamp": pd.Timestamp.now().isoformat()
            })
            
            return {
                "success": True,
                "sql": sql,
                "data": df.to_dict('records'),
                "columns": list(df.columns),
                "rows": len(df)
            }
            
        except Exception as e:
            logger.error(f"执行SQL查询时发生错误: {e}, SQL: {sql}")
            
            # 记录到查询历史
            self.query_history.append({
                "sql": sql,
                "error": str(e),
                "success": False,
                "timestamp": pd.Timestamp.now().isoformat()
            })
            
            return {
                "success": False,
                "error": str(e),
                "sql": sql,
                "data": None
            }
    
    def generate_sql(self, query: str, context: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """从自然语言生成SQL查询
        
        参数:
            query: 自然语言查询
            context: 对话上下文
            
        返回:
            生成的SQL查询
        """
        if not self.tables_info:
            return {
                "success": False,
                "error": "未获取数据库结构信息",
                "sql": "",
                "explanation": ""
            }
        
        try:
            # 构建基础系统提示
            system_prompt = """你是一位专业的SQL专家，精通将自然语言转换为SQL查询。
请根据用户的查询和提供的数据库结构信息，生成一个准确的SQL查询语句。

请遵循以下准则:
1. 仅生成标准的MySQL SQL语法
2. 生成的SQL应该尽可能高效和简洁
3. 对于模糊的查询，做出合理的假设，并在解释中说明
4. 确保SQL查询正确引用表名和列名
5. 对于美妆销售数据分析，考虑常见的分析模式(如时间趋势、分类对比等)

请返回:
1. SQL查询语句，不包含任何其他内容
2. SQL的详细解释，说明查询的目的和逻辑

请注意: 请不要返回多个SQL备选项，只返回最合适的一个SQL查询。"""

            # 添加上下文信息（如果有）
            context_info = ""
            if context:
                context_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in context])
                context_info = f"\n以下是之前的对话上下文:\n{context_str}"
            
            # 合并所有系统信息为一个完整的system prompt
            complete_system_prompt = f"{system_prompt}{context_info}"
            
            # 构建消息，确保只有一个system消息
            messages = [
                {"role": "system", "content": complete_system_prompt},
                {"role": "user", "content": f"数据库结构信息:\n{self.get_db_schema_text()}\n\n用户查询: {query}"}
            ]
            
            # 使用LLM生成SQL
            response_text = ""
            for response in self.sql_agent.run(messages=messages):
                if "content" in response:
                    response_text += response["content"]
            
            # 解析响应，提取SQL
            sql_query, explanation = self._extract_sql_and_explanation(response_text)
            
            if not sql_query:
                return {
                    "success": False,
                    "error": "无法从响应中提取SQL查询",
                    "sql": "",
                    "explanation": explanation or response_text
                }
            
            return {
                "success": True,
                "sql": sql_query,
                "explanation": explanation,
                "raw_response": response_text
            }
            
        except Exception as e:
            logger.error(f"生成SQL查询时发生错误: {e}")
            return {
                "success": False,
                "error": f"生成SQL查询失败: {e}",
                "sql": "",
                "explanation": ""
            }
    
    def _extract_sql_and_explanation(self, text: str) -> Tuple[str, str]:
        """从LLM响应中提取SQL查询和解释
        
        参数:
            text: LLM响应文本
            
        返回:
            提取的SQL查询和解释
        """
        sql_query = ""
        explanation = ""
        
        # 检查是否有SQL代码块
        if "```sql" in text or "```" in text:
            parts = text.split("```")
            for i, part in enumerate(parts):
                if i % 2 == 1:  # 奇数部分是代码块
                    # 去除语言标识
                    code = part.strip()
                    if code.startswith("sql"):
                        code = code[3:].strip()
                    
                    # 只取第一个SQL代码块
                    if not sql_query and ("SELECT" in code.upper() or "INSERT" in code.upper() or 
                                         "UPDATE" in code.upper() or "DELETE" in code.upper() or
                                         "CREATE" in code.upper() or "ALTER" in code.upper()):
                        sql_query = code
                        break
            
            # 提取解释
            # 假设解释在SQL代码块后面
            if sql_query:
                sql_index = text.find(sql_query)
                if sql_index != -1:
                    after_sql = text[sql_index + len(sql_query):].strip()
                    
                    # 如果SQL后面还有代码块，只取到下一个代码块之前
                    if "```" in after_sql:
                        explanation = after_sql.split("```")[0].strip()
                    else:
                        explanation = after_sql
                
                # 如果SQL后面没有文本，尝试从SQL前面提取
                if not explanation:
                    before_sql = text[:text.find("```" + ("sql" if "```sql" in text else ""))].strip()
                    if before_sql:
                        explanation = before_sql
        
        # 如果没有找到代码块，尝试直接查找SQL语句
        if not sql_query:
            lines = text.split("\n")
            for line in lines:
                line = line.strip()
                if line and ("SELECT" in line.upper() or "INSERT" in line.upper() or 
                           "UPDATE" in line.upper() or "DELETE" in line.upper() or
                           "CREATE" in line.upper() or "ALTER" in line.upper()):
                    sql_query = line
                    break
            
            # 如果找到SQL，剩下的文本作为解释
            if sql_query:
                sql_index = text.find(sql_query)
                if sql_index != -1:
                    before_sql = text[:sql_index].strip()
                    after_sql = text[sql_index + len(sql_query):].strip()
                    
                    if before_sql and after_sql:
                        explanation = before_sql + "\n\n" + after_sql
                    elif before_sql:
                        explanation = before_sql
                    else:
                        explanation = after_sql
        
        # 如果仍然没有找到SQL或解释，将整个文本视为解释
        if not sql_query and not explanation:
            explanation = text
        
        return sql_query, explanation
    
    def execute_nl_query(self, query: str, context: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """执行自然语言查询
        
        参数:
            query: 自然语言查询
            context: 对话上下文
            
        返回:
            查询结果
        """
        # 先将自然语言转换为SQL
        sql_result = self.generate_sql(query, context)
        
        if not sql_result["success"]:
            return {
                "success": False,
                "error": sql_result.get("error", "生成SQL查询失败"),
                "sql": sql_result.get("sql", ""),
                "explanation": sql_result.get("explanation", ""),
                "query": query
            }
        
        # 执行生成的SQL
        sql = sql_result["sql"]
        execution_result = self.execute_sql(sql)
        
        if not execution_result["success"]:
            return {
                "success": False,
                "error": execution_result.get("error", "执行SQL查询失败"),
                "sql": sql,
                "explanation": sql_result.get("explanation", ""),
                "query": query
            }
        
        # 生成查询结果的解释
        explanation = self._generate_result_explanation(
            query, 
            sql, 
            execution_result["data"], 
            sql_result.get("explanation", ""),
            context
        )
        
        return {
            "success": True,
            "query": query,
            "sql": sql,
            "data": execution_result["data"],
            "columns": execution_result["columns"],
            "rows": execution_result["rows"],
            "explanation": sql_result.get("explanation", ""),
            "response": explanation
        }
    
    def _generate_result_explanation(self, query: str, sql: str, data: List[Dict[str, Any]], 
                                    sql_explanation: str, context: Optional[List[Dict[str, str]]] = None) -> str:
        """生成查询结果的解释
        
        参数:
            query: 原始自然语言查询
            sql: 执行的SQL查询
            data: 查询结果数据
            sql_explanation: SQL的解释
            context: 对话上下文
            
        返回:
            结果解释
        """
        # 如果结果为空，简单返回
        if not data:
            return "查询没有返回任何结果。这可能意味着没有符合条件的数据。"
        
        try:
            # 将结果转换为DataFrame以便分析
            df = pd.DataFrame(data)
            
            # 计算一些基本统计信息
            result_info = {
                "行数": len(df),
                "列数": len(df.columns),
                "列名": list(df.columns)
            }
            
            # 对于数值列，计算统计摘要
            numeric_cols = df.select_dtypes(include=['int', 'float']).columns
            if len(numeric_cols) > 0:
                result_info["数值统计"] = {}
                for col in numeric_cols:
                    result_info["数值统计"][col] = {
                        "最小值": float(df[col].min()),
                        "最大值": float(df[col].max()),
                        "平均值": float(df[col].mean()),
                        "总和": float(df[col].sum())
                    }
            
            # 获取列的唯一值数量
            for col in df.columns:
                unique_count = df[col].nunique()
                result_info[f"{col}_唯一值数量"] = unique_count
                
                # 如果唯一值较少，列出它们
                if unique_count <= 5:
                    result_info[f"{col}_唯一值"] = list(df[col].unique())
            
            # 构建系统提示
            system_prompt = """你是一位专业的数据分析师，专注于美妆销售数据分析。
请根据提供的SQL查询、查询结果和统计信息，生成一个详细的解释，帮助用户理解查询结果的含义和见解。

解释应该包含:
1. 对结果的概述
2. 关键数字和趋势
3. 潜在的业务洞察
4. 对原始问题的直接回答

请确保解释清晰、专业，并且直接回答用户的问题。"""

            # 添加上下文信息（如果有）
            context_info = ""
            if context:
                context_str = "\n".join([f"{msg['role']}: {msg['content']}" for msg in context])
                context_info = f"\n以下是之前的对话上下文:\n{context_str}"
            
            # 合并所有系统信息为一个完整的system prompt
            complete_system_prompt = f"{system_prompt}{context_info}"

            # 构建消息
            messages = [
                {"role": "system", "content": complete_system_prompt},
                {"role": "user", "content": f"""用户的原始问题: {query}

执行的SQL查询:
{sql}

SQL解释:
{sql_explanation}

查询结果统计信息:
{json.dumps(result_info, ensure_ascii=False, indent=2)}

结果包含 {len(df)} 行数据。

请生成一个详细的解释，帮助用户理解这些结果的含义和业务洞察。"""}
            ]
            
            # 使用LLM生成解释
            explanation = ""
            for response in self.sql_agent.run(messages=messages):
                if "content" in response:
                    explanation += response["content"]
            
            return explanation
            
        except Exception as e:
            logger.error(f"生成结果解释时发生错误: {e}")
            return f"查询返回了 {len(data)} 行结果。"
    
    def get_query_history(self) -> List[Dict[str, Any]]:
        """获取查询历史
        
        返回:
            查询历史列表
        """
        return self.query_history 