# family-album frontend

拾光相册 · 通用网页家庭相册前端（Vue 3 + Vite + TailwindCSS v4 + Pinia + vue-router）

## 启动

```bash
npm install
npm run dev      # http://localhost:5173
npm run build
```

开发期 `/api` 由 Vite proxy 转发到 `http://localhost:8020`。

## 页面

| 路由 | 说明 |
| --- | --- |
| `/login` | 登录/注册（注册需邀请码，由部署方在服务端 `.env` 中配置，向管理员索取） |
| `/` | 时间线：按日期分组、网格缩略图、无限滚动；点击缩略图打开看图模式（详情/编辑/评论/删除） |
| `/upload` | 上传：拖拽/相册多选、进度条、成功失败计数 |
| `/settings` | 系统设置：档案信息、账号管理、访问记录 |

媒体详情在时间线的看图模式（LightboxViewer）中呈现，无独立 `/media/:id` 路由。

移动端自适应，底部导航（时间线/上传/设置）。JWT 存 localStorage（key: `family_album_token`），路由守卫未登录跳 `/login`。

## API 契约（与 backend 对齐）

鉴权头：`Authorization: Bearer <token>`

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/auth/register` | body `{username, password, invite_code}` → `{access_token, token_type, user}` |
| POST | `/api/auth/login` | body `{username, password}` → `{access_token, token_type, user}` |
| GET | `/api/auth/me` | → `{id, username, created_at}` |
| POST | `/api/media/upload` | multipart，字段名 `files`（可多个）→ MediaOut 数组 |
| GET | `/api/media?page=&page_size=` | → `{total, page, page_size, items: MediaOut[]}`，按 taken_at 倒序 |
| GET | `/api/media/{id}` | → MediaOut |
| PATCH | `/api/media/{id}` | body `{caption?, taken_at?}` |
| DELETE | `/api/media/{id}` | → `{ok:true}` |
| GET | `/api/comments?target_type=&target_id=` | → 评论列表（时间正序） |
| POST | `/api/comments` | body `{target_type, target_id, body}` → 评论对象 |
| DELETE | `/api/comments/{id}` | 删除评论 |

MediaOut：`{id, orig_name, media_type:"photo"\|"video"\|"audio", mime_type, size, caption, taken_at, taken_at_source, created_at, uploader_id, url, thumbnail_url}`。

- `url`/`thumbnail_url` 为相对静态路径（`/data/originals/...`、`/data/thumbnails/...`），Vite 已将 `/data` 一并代理到后端。
- 评论对象：`{id, target_type, target_id, author_id, author_name, body, created_at}`。

错误响应按 `{detail: "..."}` 处理；401 统一清 token 跳登录页。

## 目录

```
src/
  api/        # client.js (fetch/XHR 封装) + index.js (接口层)
  stores/     # pinia：auth
  router/     # 路由 + 守卫
  views/      # Login / Timeline / Upload / Settings
  components/ # BottomNav / LightboxViewer / BabyMascot / CartoonStickers / UploadIndicator
```
