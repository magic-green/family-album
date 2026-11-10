# 拾光相册（family-album）

> 一个**自托管的网页版家庭相册**：把照片、视频、音频存放在自己的服务器上，按时间线浏览，家人可以评论、点赞、打标签，支持 PWA 安装与系统分享，并可按需接入视觉模型自动打标签。

本项目是开源脱敏副本，仓库内**不包含任何真实照片、真实姓名、真实个人数据或真实密钥**。所有示例素材均由代码绘制，示例账号与日期均为虚构。

---

## 功能一览

- **时间线首页**：按拍摄日期分组的响应式瀑布流，手机 / 平板 / 桌面自适应列数，无限滚动加载；顶部展示相册概况与成长天数。
- **上传**：多选文件、整个文件夹拖入或选择（含子目录递归）、**剪贴板粘贴上传**（`Ctrl+V` 直接贴入截图或复制的图片）。
- **分片并行 + 秒传**：小分片并行上传、单片失败自动重试；上传前先算内容哈希，相册里已有的文件直接秒传跳过，不重复消耗流量。
- **照片 / 视频 / 音频**：常见图片格式（含 HEIC/HEIF、WebP）、常见视频与音频格式均可上传。
- **媒体自动处理**：视频上传后服务端自动转码为 720p H.264；音频自动归一化为 m4a；自动生成缩略图。
- **自定义拍摄日期**：在看图模式里可手动修改日期，时间线按新日期自动重排。
- **拍摄时间恢复**：依次尝试 EXIF 拍摄时间 → 文件名时间戳 → 批次日期提示 → 文件修改时间 → 上传时间，尽量还原真实拍摄时刻。
- **评论 / 点赞 / 标签**：一人一赞可取消，标签筛选，AI 给出的标题与标签采用「建议制」，可人工采纳或删除。
- **看图模式**：左右切换、键盘方向键、双击点赞、编辑图注、查看原图、查看拍摄时间 / 设备 / 坐标等元数据、删除入口。
- **PWA 与系统分享**：可「添加到主屏幕」独立启动；支持从系统分享菜单直接把图片发送到相册。
- **可选 AI 标签**：接入兼容的视觉模型服务后，可为照片生成内容标签与标题建议；未配置或模型不可用时按设计自动降级，不影响上传与浏览。
- **多用户与邀请码**：注册需邀请码，提供账号列表、删除账号与登录记录查看。
- **系统设置**：出生日期、自定义头像、相册概况（照片数 / 存储占用 / 模型状态等）。

---

## 界面与示例素材

本文档**不附任何真实界面截图**。仓库中的界面与文档素材全部是程序化绘制的矢量剪贴画：

- `demo/` 下提供 8 张统一 `640×480` 的纯 SVG 剪贴画（阳光与云、云朵、小花、小鸭、气球、星星与月亮、彩虹、相机），奶油 / 蜜桃 / 蜂蜜配色，见 `demo/README.md`。
- 前端界面用到的卡通横幅与背景贴纸同样是纯 SVG（位于 `frontend/public/cartoon/`），不含位图、外链或脚本。
- `scripts/seed_demo.py` 生成的示例相册图片是用 Pillow 直接绘制的抽象卡通图，与上述剪贴画一样不含任何文字、真实照片、EXIF、GPS 或设备信息，可自由替换。

---

## 快速开始 A：Docker Compose（推荐）

### 前置条件

- Docker Engine 与 Docker Compose 插件。
- Node.js 20.19+ 或 22.12+ 与 npm（**仅用于构建前端**，运行时不需要 Node）。
- 一份填好的 `.env` 配置。

> **关键前提**：必须先构建出 `frontend/dist`，后端才能同源托管前端页面；缺少该目录时访问会是一片空白。

### 步骤

```bash
# 1. 进入克隆下来的仓库根目录（以下均为相对路径）
cd family-album

# 2. 复制配置模板并修改
cp .env.example .env
#   INVITE_CODE 为强必填：务必把占位值改成你自己的随机字符串，未设置会拒绝启动
#   JWT_SECRET 留空即可：程序自动生成随机密钥并持久化，重启复用；
#   也可用 `openssl rand -hex 32` 自行生成固定值
openssl rand -hex 32

# 3. 构建前端产物（首次启动前必须执行）
cd frontend && npm ci && npm run build && cd ..
#   也可用仓库根目录的 Makefile：make build

# 4. 启动服务
docker compose up -d --build
#   等价于：make up

# 5. 浏览器访问
#   http://localhost:8020
```

`docker compose` 会自动读取同目录的 `.env`；`INVITE_CODE` 是**强必填**项，未设置时 Compose 会直接报错拒绝启动，后端未检测到该环境变量也会报错退出。数据卷 `./data`、`./db` 与只读挂载的 `./frontend/dist` 让容器重建后数据不丢失。

### 注册第一个账号

打开 `http://localhost:8020` → 「注册」→ 填写你在 `.env` 中设置的 `INVITE_CODE`、用户名和密码（至少 6 位）。第一个账号即管理员视角的普通家庭成员账号；之后其他家人用同一个邀请码自行注册即可。

---

## 快速开始 B：本地直跑

适合开发调试，或不想使用容器的场景。

### 1. 后端（Python 3.12+）

```bash
cd backend
python -m venv .venv
source .venv/bin/activate          # Windows 使用：.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. 前端构建（Node.js 20.19+ / 22.12+）

```bash
cd frontend
npm ci
npm run build
```

### 3. 设置环境变量

后端从 `backend/` 目录启动，因此下面的相对路径都以 `backend/` 为基准：

```bash
export INVITE_CODE=你的邀请码
export JWT_SECRET=                # 留空即可：自动生成随机密钥，持久化到数据库文件同目录的 .jwt_secret，重启复用
export DATA_DIR=../data
export DB_PATH=../db/app.db
export STATIC_DIR=../frontend/dist
```

Windows（PowerShell）可用 `$env:INVITE_CODE="你的邀请码"` 等形式设置。

### 4. 启动后端

```bash
cd backend
uvicorn app.main:app --port 8020
```

打开 `http://localhost:8020` 即可（后端同源托管 `frontend/dist`）。首次启动会自动建表并创建所需目录。

### 5. 开发模式（前端热更新）

两个终端分别执行：

```bash
# 终端 1：后端（在 backend/ 目录）
uvicorn app.main:app --port 8020 --reload

# 终端 2：前端（在 frontend/ 目录）
npm run dev
```

Vite 开发服务器运行在 `http://localhost:5173`，`frontend/vite.config.js` 已配置把 `/api` 与 `/data` 代理到 `8020`，开发时直接访问 `5173` 即可。

---

## 配置表

所有配置均通过环境变量提供，Docker Compose 会从 `.env` 读取。

| 变量 | 必填 | 默认值 | 用途 |
|---|---|---|---|
| `INVITE_CODE` | **是（强必填）** | 无；未设置时后端与 Compose 都会拒绝启动 | 注册邀请码；`.env.example` 中是占位值 `change-me-please`，务必改成你自己的随机字符串 |
| `JWT_SECRET` | 否 | 留空即自动生成安全随机密钥，持久化到**数据库文件（`DB_PATH`）同目录**的 `.jwt_secret`，重启复用 | JWT 签名密钥；也可用 `openssl rand -hex 32` 自行生成固定值 |
| `JWT_EXPIRE_DAYS` | 否 | `30` | 登录令牌有效期（天），每次打开应用会静默续期 |
| `DATA_DIR` | 否 | `data` | 媒体根目录，原图 / 缩略图 / 头像 / 分片暂存都在其下 |
| `DB_PATH` | 否 | `db/app.db` | SQLite 数据库文件路径 |
| `STATIC_DIR` | 否 | `static` | 前端构建产物目录（本地直跑设为 `../frontend/dist`；Compose 内为挂载目录） |
| `CORS_ORIGINS` | 否 | `http://localhost:5173,http://localhost:8020` | 可选：允许访问后端的前端来源，英文逗号分隔；经反向代理访问时请加上你的访问地址 |
| `OLLAMA_URL` | 否 | `http://localhost:11434` | 可选：兼容的视觉模型服务地址；容器内访问宿主机模型时覆盖为 `http://host.docker.internal:11434` 并启用 compose 中的 `extra_hosts`；未配置或不可用时 AI 功能自动降级 |
| `AI_TAG_MODEL` | 否 | 留空（使用程序默认） | 可选：视觉模型名称 |
| `AMAP_KEY` | 否 | 留空 | 可选：逆地理编码服务密钥，用于把 GPS 坐标转成中文地名；留空只显示原始坐标 |

完整示例见 `.env.example`。**不要把填好真实值的 `.env` 提交到版本库**（已被 `.gitignore` 忽略）。

---

## 示例数据

刚克隆下来的仓库是空的。想快速看到界面效果，可以灌入一份**完全虚构**的示例数据：

```bash
python scripts/seed_demo.py       # 或：make seed
```

脚本会：

- 用 Pillow 直接绘制若干张 640×480 的抽象卡通示例图（渐变背景 + 圆、云、花、星等几何形状，**不写任何文字**以避开字体依赖），保存到 `data/originals/` 与 `data/thumbnails/`；
- 建表并写入 1 个虚构示例账号、1 条虚构出生日期设置 `2024-01-01`、若干条照片记录、几个中性标签与中性评论；
- 所有 `gps_lat` / `gps_lon` / `location_name` / `camera_make` / `camera_model` 一律置空，**不含 EXIF、GPS、设备信息或任何真实个人信息**；
- 提供示例账号 `demo` / `demo1234`（**仅本地演示用，请勿在公网使用**）。

脚本**幂等**，重复运行不会重复插入；跑完重启或刷新页面即可看到示例相册。

### 清空重来

```bash
# 不可恢复，请先备份；这会清空全部媒体与账号
rm -rf data db
mkdir -p data/originals data/thumbnails data/avatars data/tmp db
```

之后重新运行 `python scripts/seed_demo.py` 即可再次灌入示例数据。

---

## 部署到公网

- **反向代理**：用 Nginx 或 Caddy 把外部流量转发到本机运行的服务端口（`8020`），并把你的访问地址加入 `CORS_ORIGINS`。Caddy 配置简单，Nginx 可参考 `proxy_pass` 常规写法。
- **建议开启 HTTPS**：PWA 的 Service Worker 与「添加到主屏幕」「系统分享」都依赖安全上下文（HTTPS 或 localhost）。Caddy 可自动签发证书；用 Nginx 时请自行配置证书。
- **上传体积限制**：反向代理需放宽请求体大小限制（例如 Nginx 的 `client_max_body_size`）。应用本身对头像有 10MB 限制，照片 / 视频无硬性上限；分片上传把单次请求拆成小片，可降低代理压力，但仍建议为代理设置足够大的上限。
- **安全建议**：
  - `INVITE_CODE` 是强必填项，务必改成随机值，不要保留示例占位值；
  - `JWT_SECRET` 留空即可自动生成（重启复用），或用 `openssl rand -hex 32` 手动设置固定值，切勿使用弱口令或把真实密钥写进会被提交的文件；
  - 不要把服务端口无保护地直接暴露到公网，至少置于反向代理之后并配合访问控制；
  - 定期更新依赖与容器镜像，定期备份 `db/` 与 `data/`。

---

## 数据与备份

所有运行期数据都落在仓库根目录下，**均不进入版本库**：

| 路径 | 内容 |
|---|---|
| `db/app.db` | SQLite 单文件库：账号、媒体元数据、评论、标签、点赞、设置、登录记录 |
| 数据库文件同目录的 `.jwt_secret` | `JWT_SECRET` 留空时自动生成的安全随机密钥，重启复用（默认即 `db/.jwt_secret`） |
| `data/originals/` | 原图 / 视频 / 音频（UUID 文件名） |
| `data/thumbnails/` | 缩略图 |
| `data/avatars/` | 自定义头像 |
| `data/tmp/` | 分片上传暂存目录 |
| `frontend/dist/` | 前端构建产物（可随时重新构建） |

**备份**：直接拷贝 `db/` 与 `data/` 两个目录即可（自动生成的 `.jwt_secret` 默认也位于 `db/`，一并备份）；恢复时放回原位置。**清空**：参见「示例数据」一节的命令，操作前务必先备份。

---

## 隐私说明

- **本仓库不含任何真实个人数据**：示例图片由代码绘制，示例账号、姓名、日期均为虚构，示例媒体不含 EXIF、GPS 或设备信息。
- **你自己上传的照片可能含 EXIF / GPS / 设备信息**：应用会读取其中的拍摄时间、坐标与设备型号用于展示；如介意，请在上传前自行清理元数据，或避免上传含敏感信息的原图。
- **AI 打标签是可选功能**：启用后会把图片发送给你自己配置的模型服务（`OLLAMA_URL`，默认 `http://localhost:11434`）；未配置或模型不可用时按设计自动降级，不会向外部服务发送图片。启用 `AMAP_KEY` 时，逆地理编码会把 GPS 坐标发送给对应的地图服务。
- 在公网部署前，请自行评估访问控制与数据合规风险。

---

## 技术栈

- **后端**：Python 3.12+、FastAPI、SQLAlchemy 2、SQLite（首次启动自动建表）。
- **前端**：Vue 3、Vite 8、Tailwind CSS 4、Pinia、vue-router；字体使用系统字体栈，无外部字体依赖。
- **媒体处理**：Pillow、pillow-heif、imageio-ffmpeg（缩略图、HEIC 支持、视频转码与音频归一）。
- **PWA**：Service Worker、Web App Manifest、系统分享（Web Share Target）。
- **可选外部服务**：兼容的视觉模型服务（AI 标签）、地图逆地理编码服务。

---

## API 概览

除注册、登录、健康检查外，接口均需 `Authorization: Bearer <token>`。完整交互式文档由 FastAPI 在 `/docs` 提供。

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/auth/register` | 注册（用户名 / 密码 / 邀请码） |
| POST | `/api/auth/login` | 登录 |
| POST | `/api/auth/refresh` | 静默续期 |
| GET | `/api/auth/me` | 当前用户 |
| GET | `/api/auth/users` | 账号列表（含上传数） |
| DELETE | `/api/auth/users/{id}` | 删除账号 |
| GET | `/api/auth/logs` | 最近登录记录 |
| GET | `/api/media` | 媒体列表（分页 / 类型 / 标签筛选） |
| GET | `/api/media/{id}` | 媒体详情 |
| PATCH | `/api/media/{id}` | 修改图注 / 拍摄时间 |
| DELETE | `/api/media/{id}` | 删除媒体（含文件） |
| POST | `/api/media/{id}/like` | 点赞 / 取消 |
| POST | `/api/media/upload` | 整包上传 |
| POST | `/api/media/upload/init`、`/{id}/chunk`、`/{id}/status`、`/{id}/finalize` | 分片上传四步 |
| POST | `/api/media/check` | 秒传哈希检查 |
| POST | `/api/media/{id}/ai/run` | 单张即时 AI 标记 |
| POST | `/api/media/ai/backfill` | 存量批量 AI 标记 |
| POST | `/api/media/{id}/adopt-caption` | 采用 AI 标题为图注 |
| DELETE | `/api/media/{id}/tags/{tag_id}` | 删除标签 |
| GET | `/api/media/tags/all` | 标签聚合（含计数） |
| GET / POST | `/api/comments` | 评论列表 / 发表评论 |
| GET / PUT | `/api/settings` | 读取 / 保存设置（出生日期） |
| POST | `/api/system/avatar` | 上传自定义头像 |
| GET | `/api/system/info` | 相册概况 |
| GET | `/api/health` | 健康检查 |

---

## 目录结构

```
family-album/
├─ backend/
│  ├─ app/
│  │  ├─ main.py            # FastAPI 入口、静态托管、SPA fallback
│  │  ├─ config.py          # 环境变量与路径配置
│  │  ├─ database.py        # engine / SessionLocal / Base
│  │  ├─ models.py          # 数据表模型
│  │  ├─ auth.py            # 密码哈希与 JWT
│  │  ├─ routers/           # 各业务路由
│  │  └─ services/          # 缩略图 / EXIF / 视频 / 音频 / AI / 逆地理
│  ├─ requirements.txt
│  └─ Dockerfile
├─ frontend/
│  ├─ src/                  # Vue 组件、视图、状态、路由、样式
│  ├─ public/               # 静态资源（含纯 SVG 卡通素材、PWA 图标与清单）
│  ├─ vite.config.js        # 开发服务器与代理
│  └─ package.json
├─ demo/                    # 纯 SVG 示例剪贴画
├─ scripts/
│  └─ seed_demo.py          # 虚构示例数据灌入脚本
├─ data/                    # 运行时媒体（不入库）
├─ db/                      # SQLite 与自动生成的密钥（不入库）
├─ docker-compose.yml
├─ Makefile
├─ .env.example
├─ .gitignore
├─ CONTRIBUTING.md
├─ LICENSE
└─ README.md
```

---

## 已知限制

- 使用 SQLite 单文件库，适合家庭小规模自托管；多实例并发写同一库需自行改造数据库层。
- 上传过程中刷新或关闭页面会丢失进度（浏览器文件句柄不跨刷新，界面已有确认拦截），大批量上传时请勿刷新。
- 部分聊天软件另存的图片会丢失 EXIF，拍摄时间只能靠文件名时间戳恢复，改名后可能不准，可在看图模式手动修正。
- AI 打标签依赖外部模型服务（默认 `http://localhost:11434`，容器内访问宿主机需覆盖为 `http://host.docker.internal:11434`）；未配置或离线时按设计自动降级，相关功能不可用，不影响上传与浏览。
- 个别私有音频格式不受支持。
- 专辑（albums）数据表已建立，配套功能仍在完善。
- 更新前端后如页面显示异常，强制刷新一次即可（入口文件已设置不缓存）。

---

## 许可证

本项目采用 **MIT License**，详见 `LICENSE`。

## 贡献方式

欢迎提交 Issue 与 Pull Request，简要指南见 `CONTRIBUTING.md`。请勿在仓库中提交真实照片、真实姓名、真实密钥、数据库文件或 `.env`。
