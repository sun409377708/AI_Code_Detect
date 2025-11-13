#!/bin/bash
# PR-Agent Dashboard 启动脚本

echo "🚀 启动 PR-Agent 可视化管理平台..."
echo ""

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "❌ 错误: 未找到 Python 3"
    echo "请先安装 Python 3: brew install python3"
    exit 1
fi

# 检查 .env 文件
ENV_FILE=~/pr-agent-test/.env
if [ ! -f "$ENV_FILE" ]; then
    echo "❌ 错误: 未找到配置文件 $ENV_FILE"
    echo "请确保已配置 PR-Agent 的环境变量"
    exit 1
fi

# 检查并安装依赖
if [ ! -d "venv" ]; then
    echo "📦 创建虚拟环境..."
    python3 -m venv venv
fi

echo "📦 激活虚拟环境..."
source venv/bin/activate

echo "📦 安装依赖..."
pip install -q -r requirements.txt

echo ""
echo "✅ 准备完成！"
echo ""

# 启动应用
python3 app.py
