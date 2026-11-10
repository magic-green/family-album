.DEFAULT_GOAL := help

.PHONY: help build up down logs dev seed clean

help:
	@echo "拾光相册（family-album）常用命令："
	@echo ""
	@echo "  make build   构建前端产物 frontend/dist（首次启动前必须执行）"
	@echo "  make up      启动 Docker Compose（后台，自动构建镜像）"
	@echo "  make down    停止并移除容器（数据卷保留）"
	@echo "  make logs    跟踪后端日志"
	@echo "  make dev     打印本地开发模式的启动步骤"
	@echo "  make seed    灌入虚构示例数据（python scripts/seed_demo.py）"
	@echo "  make clean   打印清空示例数据的提示（不会自动删除）"

build:
	cd frontend && npm ci && npm run build

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

dev:
	@echo "本地开发模式（两个终端分别执行）："
	@echo "  1) 后端：cd backend && uvicorn app.main:app --port 8020"
	@echo "  2) 前端：cd frontend && npm run dev"
	@echo "  3) 浏览器打开 http://localhost:5173 （Vite 已配置 /api 与 /data 代理）"

seed:
	python scripts/seed_demo.py

clean:
	@echo "清空数据请手动执行，make 不会替你删除任何文件："
	@echo "  删除 data/originals 与 data/thumbnails 中的内容、以及 db/app.db，"
	@echo "  再重新建立空目录即可。操作前请先做好备份。"
