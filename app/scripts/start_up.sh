#!/bin/bash

# 因为PAI-DSW只会持久化/mnt/workspace目录，所以该脚本用于配置重新分配DSW实例后的环境

# 配置好Git环境(可选)
mkdir ~/.ssh
cp ../ssh/id_rsa ~/.ssh/id_rsa
cp ../ssh/id_rsa.pub ~/.ssh/id_rsa.pub

# 安装依赖
pip install -r requirements.txt

# 配置环境变量(记得提前修改env.example中的QWEN_API_KEY)
cp env.example .env
source .env  # 加载 .env 文件中的变量

# 安装和启动mysql

# 设置 MySQL 的 root 密码（从环境变量DB_PASSWORD中获取）
MYSQL_ROOT_PASSWORD=$DB_PASSWORD

# 更新系统包
sudo apt update -y

# 安装 MySQL 服务器和客户端
sudo apt install -y mysql-server mysql-client

# 创建 /var/lib/mysql 目录（如果不存在）
sudo mkdir -p /var/lib/mysql
sudo chown -R mysql:mysql /var/lib/mysql
sudo chmod -R 755 /var/lib/mysql

# 初始化 MySQL 数据目录（首次安装时执行）
sudo mysqld --initialize-insecure --user=mysql

# 启动 MySQL 服务（不依赖 systemd）
echo "启动 MySQL 服务..."
sudo nohup mysqld --user=mysql --skip-grant-tables > /var/log/mysql-start.log 2>&1 &
sleep 5

# 登录 MySQL 更新授权方式 并设置 root 密码
mysql -u root <<EOF
UPDATE mysql.user SET plugin='mysql_native_password' WHERE user='root' AND host='localhost';
ALTER USER 'root'@'localhost' IDENTIFIED BY '$MYSQL_ROOT_PASSWORD';
FLUSH PRIVILEGES;
EOF

MYSQL_PID=$(pgrep mysqld)
if [ -z "$MYSQL_PID" ]; then
    echo "MySQL 启动失败！请检查日志：/var/log/mysql-start.log"
    exit 1
else
    echo "MySQL 进程已启动，PID: $MYSQL_PID"
fi

# 输出完成提示
echo "MySQL 安装与启动已完成！"

# 初始化数据库
python -m app.scripts.init_mysql_db

# 运行应用
python main.py
