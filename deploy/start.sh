#!/usr/bin/env bash
# 项目启动脚本（配合 systemd 使用）
# 放到项目根目录，systemd 的 ExecStart 直接调用它即可。
set -e

# 切换到项目根目录（脚本所在目录的上一级）
cd "$(dirname "$0")/.."

# 如使用虚拟环境，解开下面一行
# source venv/bin/activate

# 数据库连接串：默认连本机 MySQL；可用环境变量覆盖（部署时由 systemd 注入）
export DATABASE_URL="${DATABASE_URL:-mysql+aiomysql://root:123456@127.0.0.1:3306/my_image_list?charset=utf8}"

exec uvicorn main:app --host 127.0.0.1 --port 8000 --workers 2
