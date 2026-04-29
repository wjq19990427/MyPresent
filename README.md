# MyPresent 🎁

> "只要一直在记录思考和当下的状态，以及一些生活琐碎，就是在好好生活。"

**MyPresent** 是一个专注于生活化记录、思考归档与智能辅助的个人 Agent。它不仅是一个代码仓库，更是一种生活理念的数字载体，旨在帮助我们更好地梳理自我，并传递有价值的经验。

### 💡 为什么叫 MyPresent？

"Present" 在这个项目中蕴含着三层递进的含义：

* **记录当下 (The Present):** 捕捉当下的状态与闪动的思绪。从个人角度而言，记录的意义在完成的那一刻便已基本达成——在这个过程中，我们系统地整理了大脑中的碎片，完成了一次深度的自我总结与反思。
* **珍惜馈赠 (The Gift of Today):** 告诫自己活在当下，珍惜今日，因为此时此刻的经历本身就是上天最好的馈赠。
* **赠予他人 (The Present for You):** 记录的进阶意义在于"利他"。我希望将自己在这些经历中的思考、成长与避坑经验，作为一份礼物，赠予所有需要帮助的人。

### 🚀 项目愿景

在快节奏的生活中，我们留下了无数零散的随笔、备忘录、照片和视频。MyPresent 致力于通过自动化的数据清洗和人工智能技术，将这些非结构化的生活碎片进行标签化、结构化管理，构建一个完全私有化的语义知识库。

它不仅是一个存放记忆的"数据库"，更是一个能读懂你情绪、帮你串联回忆的"第二大脑"。

---

## 目录

- [快速开始](#快速开始)
- [项目架构](#项目架构)
- [模块详解](#模块详解)
- [数据文件说明](#数据文件说明)
- [扩展开发指南](#扩展开发指南)
- [API 参考](#api-参考)
- [Roadmap](#roadmap)

---

## 快速开始

**安装依赖**

```bash
pip install -r requirements.txt
# 国内镜像加速：
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

**启动应用**

```bash
cd D:\MyPresent
streamlit run app.py
```

浏览器访问 `http://localhost:8501`。

**环境要求**

| 项目 | 要求 |
|------|------|
| Python | 3.9+ |
| Streamlit | 1.33+ |
| opencv-python | 4.x |
| Pillow | 10.x+ |
| chromadb | 0.5+ |
| sentence-transformers | 3.0+ |

**（可选）AI 自动标签**

配置环境变量 `MYPRESENT_API_KEY` 后，上传页面的「✨ AI」按钮将激活自动标签推荐（Phase 3 实现）。

---

## 项目架构

```
D:\MyPresent\
├── app.py                          # 入口（< 35 行），仅调用 main()
├── mypresent/                      # 核心包
│   ├── __init__.py
│   ├── constants.py                # 全部常量 + FIELD_SCHEMA（零内部依赖）
│   ├── config.py                   # 标签 / 分组 CRUD
│   ├── db.py                       # pending_db.json I/O + session 数据模型
│   ├── media.py                    # 视频缩略图、图像格式转换
│   ├── file_io.py                  # 文件写入 / 移动 / Markdown 导出
│   ├── vector_db.py                # ChromaDB + BGE embedding（Phase 2）
│   ├── session_ops.py              # 字段更新、评论、auto_tag
│   ├── state.py                    # Streamlit session state 初始化
│   └── ui/
│       ├── __init__.py
│       ├── forms.py                # 表单字段渲染
│       ├── components.py           # 共用卡片、详情、评论区、管理面板
│       ├── tab_upload.py           # 记录舱 Tab
│       ├── tab_gallery.py          # 灵感墙 Tab
│       ├── tab_archived.py         # 已归档 Tab
│       └── tab_search.py           # 搜索 Tab
├── pending_db.json                 # 所有记录数据库（自动生成，gitignored）
├── mypresent_config.json           # 标签 / 分组配置（自动生成，gitignored）
├── Assets/                         # 文件存储（gitignored）
│   ├── Pending/{images,videos,text}/
│   └── Final/{images,videos,text}/
├── vector_db/                      # ChromaDB 持久化（gitignored）
├── CHANGELOG.md
├── requirements.txt
└── .gitignore
```

**依赖关系（无循环）**

```
constants ──────────────────────────────── (底层，无内部依赖)
    ↑
config ──── constants
db ─────── constants
media ───── constants
    ↑
file_io ─── constants + db + vector_db（延迟导入避免循环）
vector_db ── constants + db
    ↑
session_ops ─ constants + db + file_io + vector_db
    ↑
state ──────── streamlit only
ui/forms ───── constants
ui/components ─ constants + config + db + media + session_ops + ui/forms
ui/tab_* ────── 各自组合上述模块
    ↑
app.py ──────── ui/tab_* + file_io + vector_db + state
```

---

## 模块详解

### `constants.py` — 扩展字段只改这里

所有常量的唯一来源。**新增字段只需修改 `FIELD_SCHEMA`**，UI 渲染、校验、`.md` 生成全部自动跟随。

```python
FIELD_SCHEMA: list[dict] = [
    {
        "key":         str,   # session dict 中的键名
        "label":       str,   # 界面显示名称
        "required":    bool,  # True = 归档前必须填写
        "type":        str,   # "textarea" | "text" | "date_or_text"
        "placeholder": str,
        "help":        str,
    },
    ...
]
```

`type` 说明：

| type | 控件 | 适用场景 |
|------|------|----------|
| `textarea` | 多行文本框 | 描述、感受等长文本 |
| `text` | 单行文本框 | 简短标签、标题 |
| `date_or_text` | 日历 + 自由输入双控件 | 时间字段（支持模糊时间如"去年夏天"） |

---

### `config.py` — 标签 / 分组数据

管理 `mypresent_config.json`，提供标签注册表和分组的 CRUD。

- `get_tags_registry()` / `add_tag()` / `remove_tag()`
- `get_groups()` / `create_group()` / `delete_group()`

默认标签（`DEFAULT_TAGS`）不可删除，自定义标签随时可删。`delete_group()` 会自动清理所有 session 的 `group_ids`。

---

### `db.py` — Session 数据模型

管理 `pending_db.json` 的读写，以及 session 的创建和校验。

- `load_db()` / `save_db()` — 全量读写，损坏时返回 `[]` 不抛异常
- `validate_session(session)` — 返回未填写的必填字段 label 列表
- `_is_text_session(session)` — 判断是否为纯文字记录
- `_make_session(...)` — 创建标准 session dict
- `_apply_fields(session, values)` — 将字段值写入 session 并重算 `is_complete`

---

### `media.py` — 视频 / 图像处理

- `video_thumbnail(path)` — 提取视频第一帧，叠加「▶ [视频]」标签，返回 PIL Image
- `pil_to_png_bytes(img)` — PIL Image → PNG bytes，供 `st.image()` 使用

---

### `file_io.py` — 文件存储规则

文件按类型自动路由到子目录：`images/` / `videos/` / `text/`，流式写入避免大视频双倍内存占用。

关键函数：

- `ensure_dirs()` — 应用启动时调用，创建所有子目录
- `_write_files(file_data_list, dest_dir, session_id)` — 写文件并返回 file_entries
- `_write_md(session)` — 生成/重写 Final 目录的 `.md` 文档
- `save_session_pending(...)` — 暂存到 Pending
- `save_session_final(...)` — 直接归档到 Final（同时写向量库）
- `move_to_final(session_id)` — Pending → Final 迁移（同时写向量库）
- `import_folder_to_pending(file_paths, as_one_session)` — 文件夹批量导入

---

### `vector_db.py` — Embedding 方案

使用 ChromaDB（本地持久化，cosine 相似度）+ `BAAI/bge-small-zh-v1.5` 模型。

- `_get_embedder()` / `_get_collection()` — `@st.cache_resource` 装饰，首次调用时初始化
- `embed_session(session)` — upsert 到向量库（归档 / 字段更新时自动调用）
- `delete_embedding(session_id)` — 从向量库删除
- `_ensure_indexed()` — 启动时补全历史 Final 记录的索引，自动检测 schema 升级

替换向量库只需修改此文件，其他模块无感知。

---

### `session_ops.py` — 如何添加新的 Session 操作

高层操作函数，组合 db + file_io + vector_db：

- `update_session_fields(session_id, new_values)` — 字段更新（Final 记录自动追加 edit_history，重写 .md，更新向量库）
- `update_session_tags(session_id, tags)` — 单独更新标签（不触发 edit_history）
- `update_session_groups(session_id, group_ids)` — 单独更新分组
- `add_comment(session_id, text)` / `delete_comment(session_id, comment_id)` — 评论操作
- `auto_tag_session(session)` — AI 标签接口（Phase 3 stub，配置 `MYPRESENT_API_KEY` 后实现）

**新增 Session 操作**：在此文件添加函数，组合 db / file_io / vector_db 即可，无需修改其他层。

---

### `ui/` — 如何添加新 Tab 或新 UI 组件

**新增 Tab**：
1. 在 `ui/` 下新建 `tab_xxx.py`，导出 `render_xxx_tab()` 函数
2. 在 `app.py` 的 `st.tabs([...])` 中注册，并在对应 `with` 块调用

**新增共用组件**：添加到 `ui/components.py`。

**`ui/forms.py`** — `render_field_inputs(prefix, defaults, skip_keys)` 是字段渲染的统一入口，必须在 `st.form()` 块内调用。

**`ui/components.py`** — 核心组件：
- `_render_card(col, session, state_key, score)` — 卡片（画廊 / 搜索结果均复用）
- `_render_detail(session, mode, state_key)` — 详情 + 编辑面板（`mode="pending"|"final"`）
- `_render_comments(session)` — 评论区（必须在 form 外调用）
- `_render_tag_manager()` / `_render_group_manager()` — 管理面板

---

## 数据文件说明

### `pending_db.json` — Session 数据库

JSON 数组，每个元素为一条记录：

```jsonc
{
  "session_id":   "20260424_192301",     // 唯一 ID：YYYYMMDD_HHMMSS
  "status":       "pending",             // "pending" | "final"
  "upload_time":  "2026-04-24 19:23:01",
  "archive_time": "",                    // 归档时填入
  "is_complete":  false,                 // 必填项是否全部完整（自动计算）
  "source_type":  "file",               // "file" | "text"
  "files": [
    {
      "filename":      "20260424_192301_000_photo.jpg",
      "original_name": "photo.jpg",
      "path":          "Assets/Pending/images/20260424_..."
    }
  ],
  "tags":         ["生活感悟"],
  "group_ids":    ["grp_20260425_100000"],
  "comments":     [{"id": "...", "text": "...", "created_at": "..."}],
  "edit_history": [{"edited_at": "...", "changes": {"feeling": {"from": "旧", "to": "新"}}}],
  // FIELD_SCHEMA 字段：
  "content_time": "2025-06-01",
  "description":  "...",
  "feeling":      "...",
  "reason":       ""
}
```

### `mypresent_config.json` — 标签 / 分组配置

```jsonc
{
  "tags_registry": ["个人规划", "生活感悟", "重要记忆", "工作总结", "随笔", "自定义标签"],
  "groups": [
    {"id": "grp_20260425_100000", "name": "2026年春", "created_at": "2026-04-25 10:00:00"}
  ]
}
```

---

## 扩展开发指南

### 新增元数据字段

只改 `mypresent/constants.py` 中的 `FIELD_SCHEMA`：

```python
{
    "key":         "mood_score",
    "label":       "心情评分",
    "required":    False,
    "type":        "text",
    "placeholder": "1-10 分",
    "help":        "选填",
},
```

新字段自动出现在所有表单、`.md` 导出中。旧记录中该字段为空字符串，不影响兼容性。

### 接入 AI 自动标签（Phase 3）

实现 `mypresent/session_ops.py` 中的 `auto_tag_session(session) -> list[str]`：

```python
def auto_tag_session(session: dict) -> list[str]:
    api_key = os.environ.get("MYPRESENT_API_KEY")
    if not api_key:
        return []
    # 调用 Claude / OpenAI API，基于 description + feeling 推荐标签
    ...
```

### 替换向量库

只修改 `mypresent/vector_db.py`，其他模块通过 `embed_session` / `delete_embedding` / `_ensure_indexed` 调用，接口不变。

### 接入外部存储

替换这些函数即可切换后端，接口签名不变：

| 函数（位于 `file_io.py` / `db.py`） | 替换方向 |
|------|----------|
| `load_db()` / `save_db()` | 数据库 / 对象存储 |
| `_write_files()` | OSS / S3 上传 |
| `move_to_final()` | 远程 copy + delete |
| `_write_md()` | 上传到对象存储 |

### 新增支持的文件类型

1. 在 `constants.py` 的对应集合中添加扩展名（`IMAGE_EXTS` / `VIDEO_EXTS` / `TEXT_EXTS`）
2. 在 `ui/tab_upload.py` 的 `file_uploader` 的 `type=` 列表中添加
3. 在 `ui/components.py` 的 `_render_detail` 文件预览区添加对应渲染分支

---

## API 参考

### db.py

```python
load_db() -> list[dict]
save_db(data: list[dict]) -> None
validate_session(session: dict) -> list[str]      # 返回未填写的必填字段 label
_is_text_session(session: dict) -> bool
_make_session(session_id, file_entries, source_type, field_values, tags) -> dict
```

### file_io.py

```python
ensure_dirs() -> None
save_session_pending(file_data_list, source_type, field_values, tags=None) -> None
save_session_final(file_data_list, source_type, field_values, tags=None) -> None
move_to_final(session_id: str) -> None
import_folder_to_pending(file_paths: list[Path], as_one_session: bool) -> int
```

`file_data_list` 的每个元素为 `(bytes | file-like, original_name: str)`。

### session_ops.py

```python
update_session_fields(session_id: str, new_values: dict) -> None
update_session_tags(session_id: str, tags: list[str]) -> None
update_session_groups(session_id: str, group_ids: list[str]) -> None
add_comment(session_id: str, text: str) -> None
delete_comment(session_id: str, comment_id: str) -> None
auto_tag_session(session: dict) -> list[str]    # Phase 3 stub
```

### config.py

```python
get_tags_registry() -> list[str]
add_tag(tag: str) -> None
remove_tag(tag: str) -> None            # 默认标签在 UI 层保护，此函数不做检查
get_groups() -> list[dict]
create_group(name: str) -> str          # 返回 group_id
delete_group(group_id: str) -> None     # 同时清理所有 session 的 group_ids
```

### vector_db.py

```python
embed_session(session: dict) -> None        # upsert（失败静默）
delete_embedding(session_id: str) -> None   # 失败静默
_ensure_indexed() -> None                   # 启动时补全历史索引
```

### ui/components.py

```python
_render_card(col, session, state_key, score=None) -> None
_render_detail(session, mode, state_key=None) -> None   # mode="pending"|"final"
_render_comments(session) -> None           # 必须在 st.form() 外调用
_render_tag_manager() -> None
_render_group_manager() -> None
```

### ui/forms.py

```python
render_field_inputs(prefix, defaults=None, skip_keys=None) -> dict
# 必须在 st.form() 块内调用
# prefix：同一页面多处调用时保证唯一（如 "upload"、"edit_20260424_192301"）
# skip_keys：跳过渲染但保留 defaults 中对应值
```

---

## Roadmap

| Phase | 状态 | 内容 |
|-------|------|------|
| Phase 1 | ✅ 完成 | 基础上传、归档、灵感墙、评论区、编辑历史 |
| Phase 2 | ✅ 完成 | ChromaDB embedding、日期过滤搜索、语义检索、标签/分组、文件夹导入 |
| Phase 3 | 🔜 计划中 | AI 标签推荐（`auto_tag_session`）、智能问答（`render_search_tab` 问答模式） |
| Phase 4 | 🔜 计划中 | OurPresent — 多用户版本，社区化分享，记录开放与隐私控制 |
