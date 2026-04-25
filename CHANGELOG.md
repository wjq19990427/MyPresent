# Changelog

所有版本的功能修改和更新记录。版本号格式：`主版本.次版本.补丁`。

---

## [v2.4.0] - 2026-04-25

### 新增

- **文件分类存储**：上传文件按类型自动路由到 `images/` / `videos/` / `text/` 子目录
  - `_file_subdir(filename)` 辅助函数：根据扩展名返回对应子目录名
  - `ensure_dirs()` 同步创建 Final 和 Pending 下的 6 个子目录
  - `_write_files()` 新文件写入时自动路由到对应子目录
  - `move_to_final()` 从 Pending 移入 Final 时同样按类型路由
  - 历史已归档文件一次性迁移至对应子目录，`pending_db.json` 路径同步更新
  - 向量库重新索引，确保 ChromaDB metadata 与最新路径一致

---

## [v2.3.0] - 2026-04-25

### 新增

- **Phase 2.1 — Embedding 基础层**
  - 引入 ChromaDB（本地持久化，cosine 相似度）+ `BAAI/bge-small-zh-v1.5` 模型
  - `embed_session()` / `delete_embedding()`：向量库写入与删除
  - `index_existing_finals()`：启动时自动补全历史归档记录的索引
  - `_parse_date_iso()`：将 content_time 解析为 YYYY-MM-DD，双轨存储（raw + iso）
  - Embedding 自动 hook：归档（`save_session_final` / `move_to_final`）和字段更新（`update_session_fields`）时同步写入向量库
  - `st.cache_resource` 缓存 embedder 和 collection，避免重复加载

- **Phase 2.2 — 日期过滤搜索**
  - 新增「🔍 搜索」Tab（第四个 Tab）
  - 日期范围选择 → ChromaDB metadata filter（`has_exact_date=True` + 日期区间）
  - 模糊时间描述的记录单独折叠展示，并注明无法按日期过滤

- **Phase 2.3 — 语义检索**
  - 自然语言输入 → BGE 非对称检索（query 加前缀）→ Top-K 结果
  - 结果卡片附「🎯 相似度 XX%」标签
  - 点击卡片可展开完整详情和评论区

- `_render_card()` 新增可选 `score` 参数（向后兼容）
- `search_selected` 加入 session state 管理搜索结果的选中状态
- `vector_db/` 加入 `.gitignore`

---

## [v2.2.0] - 2026-04-25

### 新增

- **视频格式全面支持**：新增 mov / avi / mkv / wmv / webm / flv / m4v / 3gp / ts / mts / mpg / mpeg
- **任意大小视频上传**：`server.maxUploadSize` 提升至 4096 MB（4 GB）
- **流式文件写入**：上传文件直接以流写入磁盘，不再先整体读入内存，大视频不再占用双倍内存
- **智能视频预览**：浏览器可播放格式（mp4 / webm / mov / m4v）直接内嵌播放；avi / mkv / wmv 等不兼容格式显示文件信息并提供下载按钮

### 变更

- `VIDEO_EXTS` / `VIDEO_EXTS_PLAYABLE` 常量统一管理所有视频格式判断逻辑
- `_write_files()` 同时支持 bytes 和 file-like 对象

---

## [v2.1.0] - 2026-04-24

### 新增

- **评论区独立为列表结构**（参考微信 / Facebook 社区逻辑）
  - 每条评论包含 `id`、`text`、`created_at` 三个字段
  - 支持随时追加新评论，自动记录时间戳
  - 支持逐条删除，点击删除后立即生效
  - 新增 `add_comment(session_id, text)` 数据层函数
  - 新增 `delete_comment(session_id, comment_id)` 数据层函数
  - 新增 `_render_comments(session)` UI 渲染函数（在 form 外部，支持实时交互）
  - 卡片新增评论数徽章（`💬 N 条评论`）
  - `.md` 导出文件新增「评论区」章节

- **纯文字记录自动填充描述**
  - 粘贴文字模式：文字内容直接作为描述，表单中隐藏描述输入框
  - 上传纯文本文件（全为 `.txt` / `.md`）：第一个文件的内容作为描述，同样隐藏描述输入框
  - 新增 `_is_text_session(session)` 辅助函数
  - `render_field_inputs()` 新增 `skip_keys: set` 参数，支持跳过指定字段

- **新增本文件（CHANGELOG.md）**，维护版本记录

### 变更

- `FIELD_SCHEMA` 移除 `comments` 字段（评论区改为独立数据结构，不再属于可配置字段）
- `update_session_fields()` 对纯文字记录跳过描述字段的变更追踪（描述由内容自动填充，不应产生编辑历史）
- 编辑详情区对纯文字记录显示提示信息，隐藏描述输入框

---

## [v2.0.0] - 2026-04-24

### 新增

- **Session 粒度数据模型**：一次上传 = 一条记录，不限文件数量（类似朋友圈逻辑）
- **`FIELD_SCHEMA` 开放接口**：增删字段只改此处，UI 渲染、校验逻辑、`.md` 生成自动跟随
- **粘贴文字上传模式**：文字内容保存为 `.txt` 文件，文件名取首行前 20 字符
- **必填 / 选填字段系统**：归档前校验必填项，不通过则强制暂存
- **Final 记录编辑历史**：`edit_history` 字段记录每次修改的字段差异（`from` → `to`）
- **「已归档」Tab（Tab 3）**：展示所有 Final 记录，支持编辑并查看历史
- **Markdown 导出**：每条 Final 记录在 `Assets/Final/{session_id}.md` 生成对应文档
- **灵感墙按上传时间降序排列**

### 变更

- 数据库从「文件粒度」升级为「Session 粒度」，新增 `status` / `files[]` / `edit_history[]` 字段
- `FIELD_SCHEMA` 默认字段：`content_time`（必填）、`description`（必填）、`feeling`（必填）、`reason`（选填）、`comments`（选填）

---

## [v1.0.0] - 2026-04-24

### 新增

- 初始版本：文件上传支持 jpg / png / mp4 / md / txt，可多选
- 两种保存模式：「立即归档」写入 `Assets/Final/`，「稍后处理」写入 `Assets/Pending/`
- 视频第一帧缩略图提取（`cv2.VideoCapture`），叠加「▶ [视频]」标签
- 灵感墙画廊 Tab：卡片展示，点击查看/补充信息后归档
- Windows 兼容路径处理（`pathlib.Path`）
- `pending_db.json` 作为本地 JSON 数据库
