# 美妆销售数据分析对话助手

一个基于Qwen3大模型和Qwen-Agent的多代理架构实现的对话式数据分析工具，专为美妆行业业务人员设计。系统通过多个专业Agent协同工作，提供智能、高效的数据分析体验。

## 功能特点

- **自然语言交互**：通过自然语言提问，无需编写代码即可分析数据
- **多类型数据上传**：支持CSV、Excel和SQLite数据库文件
- **智能数据可视化**：自动选择并生成最适合的图表展示分析结果
- **多轮对话分析**：支持连续对话和上下文理解，深入挖掘数据洞察
- **美妆行业专属知识**：整合行业知识库，提供行业专业分析与解释
- **多Agent协同**：专业Agent分工合作，提供全方位数据分析服务

## 系统架构

该项目采用先进的多Agent协作架构：

1. **主控Agent (MainAgent)**：核心控制组件，负责理解用户意图，协调其他Agent工作
2. **SQL Agent (SQLAgent)**：将自然语言转换为精确SQL查询，处理数据库操作
3. **数据处理Agent (DataAgent)**：负责数据清洗、转换和高级分析
4. **可视化Agent (VisualizationAgent)**：智能选择图表类型，生成专业可视化
5. **知识检索Agent (KnowledgeAgent)**：从美妆行业知识库检索相关信息

### 架构特点

- **模块化设计**：每个Agent专注于自己的专业领域
- **协同工作模式**：主控Agent统一调度，确保无缝协作
- **可扩展性**：易于添加新的专业Agent扩展系统能力
- **容错性**：单个Agent出错不影响整个系统

## 专业Agent能力

### 主控Agent (MainAgent)

- 理解用户意图，进行任务分解
- 协调其他专业Agent的调用顺序和参数传递
- 整合各Agent结果，生成最终回复
- 管理上下文和多轮对话状态
- 处理异常情况和回退策略

### SQL Agent

- 将自然语言精确转换为SQL查询语句
- 执行SQL查询并提供结果解释
- 自动识别数据库表结构辅助查询
- 优化SQL性能，支持复杂查询
- 记录查询历史，支持引用之前查询

### 数据处理Agent (DataAgent)

- 执行数据清洗、转换和高级分析
- 使用code_interpreter工具处理复杂分析任务
- 提供统计分析和数据挖掘能力
- 智能识别数据类型和缺失值处理
- 支持时间序列分析和趋势预测

### 可视化Agent

- 支持12种图表类型（柱状图、折线图、饼图等）
- 根据数据特点和用户需求自动选择最佳图表
- 针对美妆行业定制专业图表样式
- 自动生成图表解释，突出关键洞察
- 提供多种可视化库支持（matplotlib、seaborn、plotly等）

### 知识检索Agent

- 管理美妆行业专业知识库
- 使用RAG技术实现高效语义检索
- 提供行业背景知识和术语解释
- 支持动态扩充知识库内容

## 数据库配置

本项目使用MySQL数据库，需要在运行前配置以下环境变量：

- `DB_HOST`: MySQL主机地址(默认: localhost)
- `DB_PORT`: MySQL端口(默认: 3306)
- `DB_USER`: MySQL用户名(默认: root)
- `DB_PASSWORD`: MySQL密码
- `DB_NAME`: 数据库名称(默认: beauty_sales)

### 初始化数据库

```bash
# 初始化MySQL数据库和表结构
python -m app.scripts.init_mysql_db
```

## 安装与运行

### 方法1：使用Docker

```bash
# 克隆仓库
git clone https://github.com/yourusername/beauty-sales.git
cd beauty-sales

# 构建Docker镜像
docker build -t beauty-sales:latest .

# 运行Docker容器
docker run -p 8000:8000 \
  -e QWEN_API_KEY=your_api_key_here \
  -e DB_HOST=your_mysql_host \
  -e DB_USER=your_mysql_user \
  -e DB_PASSWORD=your_mysql_password \
  -e DB_NAME=beauty_sales \
  beauty-sales:latest
```

也可以使用Docker Compose:

```yaml
# docker-compose.yml
version: '3'

services:
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: your_password
      MYSQL_DATABASE: beauty_sales
    ports:
      - "3306:3306"
    volumes:
      - mysql_data:/var/lib/mysql
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost"]
      interval: 10s
      timeout: 5s
      retries: 5

  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - QWEN_API_KEY=your_api_key_here
      - DB_HOST=mysql
      - DB_USER=root
      - DB_PASSWORD=your_password
      - DB_NAME=beauty_sales
    depends_on:
      mysql:
        condition: service_healthy

volumes:
  mysql_data:
```

### 方法2：本地安装

```bash
# 克隆仓库
git clone https://github.com/yourusername/beauty-sales.git
cd beauty-sales

# 创建并激活虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑.env文件，填入你的Qwen API密钥和MySQL数据库信息

# 初始化数据库
python -m app.scripts.init_mysql_db

# 运行应用
python main.py
```

运行后访问 http://localhost:8000 即可使用应用。

## 使用方法

1. 上传数据文件（CSV、Excel或SQLite数据库）
2. 选择要分析的数据源
3. 在聊天框中输入自然语言问题，例如：
   - "过去三个月的销售趋势图是什么样的？"
   - "哪些地区的产品表现最佳？"
   - "用户年龄分布是怎样的？"
   - "不同价格区间的产品销售情况对比"
   - "推荐一个分析护肤品类别销售的可视化方式"
4. 系统将自动分析数据并给出回答，必要时生成可视化图表

## 技术栈

- **核心框架**：Qwen-Agent, FastAPI
- **AI模型**：Qwen3系列大语言模型
- **数据处理**：Pandas, NumPy, SQLAlchemy
- **可视化库**：Matplotlib, Seaborn, Plotly, Bokeh, Altair, PyGWalker
- **数据库**：MySQL, FAISS(向量数据库)
- **工具集成**：LangChain
- **前端技术**：HTML5, CSS3, JavaScript, Plotly.js
- **部署工具**：Docker, Uvicorn

## 项目结构

```
beauty-sales/
├── app/
│   ├── agents/             # 智能代理实现
│   │   ├── main_agent.py   # 主控Agent
│   │   ├── sql_agent.py    # SQL Agent
│   │   ├── data_agent.py   # 数据处理Agent
│   │   ├── visualization_agent.py # 可视化Agent
│   │   └── knowledge_agent.py # 知识检索Agent
│   ├── api/                # API端点
│   ├── components/         # 组件
│   ├── database/           # 数据库相关
│   ├── knowledge_base/     # 美妆行业知识库
│   ├── models/             # 数据模型
│   ├── scripts/            # 脚本文件
│   │   └── init_mysql_db.py # MySQL初始化脚本
│   ├── static/             # 静态资源
│   ├── templates/          # HTML模板
│   └── utils/              # 工具函数
├── docs/                   # 文档
│   ├── 架构实现文档.md      # 详细架构文档
│   ├── 项目介绍.md          # 项目业务背景介绍
├── main.py                 # 应用入口
├── requirements.txt        # 依赖列表
├── Dockerfile              # Docker配置
├── docker-compose.yml      # Docker Compose配置
└── README.md               # 项目说明
```

## 性能与安全

- 查询优化：SQL查询性能优化和缓存机制
- 数据保护：本地处理数据，不传输敏感信息
- 输入验证：SQL注入防护和输入安全检查
- 资源管理：定期清理临时文件和图表缓存

## 未来计划

- 行业知识库扩展：添加更多美妆行业专业资料
- 分析模板系统：常用分析模板的保存和复用
- 用户权限管理：多级用户权限控制
- 高级数据库支持：连接其他数据库系统
- 个性化推荐：基于历史分析行为提供分析建议
