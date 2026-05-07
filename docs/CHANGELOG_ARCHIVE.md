# Changelog Archive

历史版本归档（v3.0.0 及更早）。当前版本记录见根目录 [`CHANGELOG.md`](../CHANGELOG.md)。

---

## [v3.0.0] - 2026-05-01

### 重构

- **模块化拆分**：将 ~1750 行的 `app.py` 拆分为职责明确的 Python 包 `mypresent/`
- `app.py` 精简为 < 35 行的启动入口，仅含 `main()`
- 包结构如下（无循环依赖）：
  - `mypresent/constants.py` — 全部常量 + FIELD_SCHEMA（零内部依赖）
  - `mypresent/config.py` — 标签 / 分组 CRUD
  - `mypresent/db.py` — pending_db.json I/O + session 数据模型
  - `mypresent/media.py` — 视频缩略图、图像格式转换
  - `mypresent/file_io.py` — 文件写入 / 移动 / Markdown 导出
  - `mypresent/vector_db.py` — ChromaDB + BGE embedding
  - `mypresent/session_ops.py` — 字段更新、评论、auto_tag
  - `mypresent/state.py` — Streamlit session state 初始化
  - `mypresent/ui/forms.py` — 表单字段渲染
  - `mypresent/ui/components.py` — 共用卡片、详情、评论区、管理面板
  - `mypresent/ui/tab_upload.py` — 记录舱 Tab
  - `mypresent/ui/tab_gallery.py` — 灵感墙 Tab
  - `mypresent/ui/tab_archived.py` — 已归档 Tab
  - `mypresent/ui/tab_search.py` — 搜索 Tab
- `README.md` 重写为开发者文档（架构说明 / 扩展指南 / API 参考）
- 新增 `requirements.txt` 显式锁定依赖

### 兼容性

- 数据文件（`pending_db.json`、`Assets/`、`vector_db/`、`mypresent_config.json`）格式不变，无需迁移
- 运行命令不变：`streamlit run app.py`

---

## [v2.6.0] - 2026-04-30

### 新增

- **文本内容可编辑**
  - 纯文字记录（粘贴文字 / txt/md 上传）的详情编辑表单中，描述区域改为可直接编辑的大文本框
  - 保存时同步将修改写回对应 `.txt` 文件，description 字段同步更新
  - 归档操作同样支持在归档前编辑文本内容

- **文件夹批量导入**
  - 记录舱新增「📂 导入文件夹」模式
  - 输入本地文件夹绝对路径 → 点击「扫描」→ 展示所有支持格式文件
  - 用 multiselect 批量勾选（默认全选），展示总大小和将创建的 session 数量
  - 两种导入方式：「每个文件独立记录」（各文件各自成一条待处理）/ 「所有文件合并一条记录」
  - 文件以流式方式写入磁盘，大视频不占双倍内存
  - 导入后自动清空扫描结果，显示导入成功提示

### 变更

- `import_folder_to_pending(file_paths, as_one_session)` 新增函数
- `_render_folder_import()` 新增 UI 渲染函数
- `SUPPORTED_IMPORT_EXTS` 常量：所有支持导入的扩展名集合
- `init_state()` 新增 `folder_scan_results`、`folder_import_done` 状态键

---

## [v2.5.0] - 2026-04-29

### 新增

- **标签系统**
  - 系统默认 5 个标签：个人规划、生活感悟、重要记忆、工作总结、随笔
  - 用户可在「已归档」Tab 的「⚙️ 管理标签」面板中增删自定义标签
  - 默认标签不可删除，自定义标签随时可删
  - 归档时（上传直接归档 / 灵感墙归档 / 已归档编辑）均可多选标签
  - 标签变更不计入编辑历史
  - 标签内容写入 embedding 文本，提升语义检索准确度

- **AI 自动标签接口（预留）**
  - `auto_tag_session(session) -> list[str]` 预留接口
  - 配置 `MYPRESENT_API_KEY` 环境变量后将接入大模型推荐标签（Phase 3 实现）
  - 上传 Tab 显示「✨ AI」按钮，API 未配置时禁用

- **分组功能**
  - 用户可创建命名分组（精选合集），记录可属于多个分组
  - 在「⚙️ 管理分组」面板中增删分组；删除分组自动清理所有记录的 `group_ids`
  - 详情编辑表单中可勾选所属分组
  - 「已归档」Tab 顶部显示分组导航按钮，点击切换

- **已归档 Tab 过滤栏**
  - 文件类型过滤：全部 / 📷 图片 / 🎬 视频 / 📝 文本
  - 标签过滤：多选，OR 逻辑（含任一标签即显示）
  - 分组过滤：顶部按钮导航
  - 多条件叠加：分组 AND（文件类型 AND（标签 OR））

- **卡片增强**：标签以 `🏷️ 标签1  标签2` 形式显示在卡片底部

### 变更

- `_make_session()` 新增 `tags` 参数，session 结构增加 `tags: []`、`group_ids: []`
- `save_session_pending/final()` 新增 `tags` 参数
- `update_session_fields()` 兼容处理 `tags` 和 `group_ids`（不记 edit_history）
- `_build_embed_text()` 将标签拼入 embedding 文本
- `mypresent_config.json`：新数据文件，存储标签注册表和分组，加入 `.gitignore`

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
