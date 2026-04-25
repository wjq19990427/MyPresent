# 灵感记录工具

本地运行的个人记忆归档工具，基于 **Streamlit** 构建。支持图片、视频、文本的上传与管理，通过结构化信息字段对每条记录进行描述，并提供待处理暂存、信息补全、归档、编辑历史、社区式评论等完整生命周期管理。

---

## 目录

- [快速开始](#快速开始)
- [项目结构](#项目结构)
- [数据模型](#数据模型)
- [核心接口（函数 API）](#核心接口函数-api)
  - [字段定义接口](#字段定义接口--field_schema)
  - [数据库操作](#数据库操作)
  - [Session 生命周期](#session-生命周期)
  - [评论操作](#评论操作)
  - [字段校验](#字段校验)
  - [视频处理](#视频处理)
  - [UI 渲染层](#ui-渲染层)
  - [Streamlit 会话状态](#streamlit-会话状态)
- [UI 页面说明](#ui-页面说明)
- [扩展开发指南](#扩展开发指南)
  - [新增元数据字段](#1-新增元数据字段)
  - [新增支持的文件类型](#2-新增支持的文件类型)
  - [接入外部存储](#3-接入外部存储)
  - [新增 Tab 页面](#4-新增-tab-页面)
  - [改造为多用户版本](#5-改造为多用户版本)

---

## 快速开始

**安装依赖**（国内镜像）

```bash
pip install streamlit opencv-python Pillow -i https://pypi.tuna.tsinghua.edu.cn/simple
```

**启动应用**

```bash
cd D:\MyPresent
python -m streamlit run app.py
```

浏览器访问 `http://localhost:8501`。

**运行环境**

| 项目 | 要求 |
|------|------|
| Python | 3.9+ |
| Streamlit | 1.28+（需支持 `use_container_width`） |
| opencv-python | 4.x |
| Pillow | 9.x+ |

---

## 项目结构

```
D:\MyPresent\
├── app.py                  # 全部源码（单文件应用）
├── pending_db.json         # 所有记录的数据库（自动生成）
├── CHANGELOG.md            # 版本更新记录
└── Assets\
    ├── Pending\            # 待处理文件存储目录
    │   └── {session_id}_{index:03d}_{original_name}
    └── Final\              # 已归档文件存储目录
        ├── {session_id}_{index:03d}_{original_name}
        └── {session_id}.md # 每条归档记录对应的 Markdown 文档
```

**文件命名规则**

保存时以 `session_id` 为前缀，`session_id` 格式为 `YYYYMMDD_HHMMSS`（精确到秒）。同一次上传的多个文件通过三位数字索引区分：

```
20260424_192301_000_photo.jpg
20260424_192301_001_video.mp4
20260424_192301_002_note.txt
```

---

## 数据模型

所有记录统一存储在 `pending_db.json`，格式为 JSON 数组，每个元素为一个 **Session**（一次上传）。

### Session 结构

```jsonc
{
  // ── 系统字段（自动生成，不可手动修改）──────────────────────────
  "session_id":   "20260424_192301",         // 唯一 ID，格式 YYYYMMDD_HHMMSS
  "status":       "pending",                 // "pending" | "final"
  "upload_time":  "2026-04-24 19:23:01",     // 上传时间，自动记录
  "archive_time": "2026-04-24 20:00:00",     // 归档时间，归档时填入，否则为 ""
  "is_complete":  false,                     // 所有必填项是否已填，自动计算
  "edit_history": [],                        // 编辑历史，仅 Final 记录追加

  // ── 文件列表 ──────────────────────────────────────────────────
  "files": [
    {
      "filename":      "20260424_192301_000_photo.jpg",  // 存储文件名
      "original_name": "photo.jpg",                      // 原始文件名
      "path":          "Assets/Pending/20260424_..."     // 绝对或相对路径
    }
  ],
  "source_type": "file",                     // "file" | "text"（粘贴文字）

  // ── 元数据字段（由 FIELD_SCHEMA 驱动，见下节）──────────────────
  "content_time": "2025-06-01",
  "description":  "关于这段内容的描述",       // 纯文字记录由内容自动填充
  "feeling":      "当时的感受",
  "reason":       "",

  // ── 评论区（独立列表结构，不属于 FIELD_SCHEMA）────────────────
  "comments": [
    {
      "id":         "20260425_100000_123456",  // 唯一 ID（时间戳精确到微秒）
      "text":       "留给未来的自己……",
      "created_at": "2026-04-25 10:00:00"
    }
  ]
}
```

### edit_history 条目结构

```jsonc
{
  "edited_at": "2026-04-25 10:00:00",
  "changes": {
    "feeling": { "from": "旧感受", "to": "新感受" }
  }
}
```

只记录**有变化**的字段。纯文字记录的 `description` 字段不追踪变更（由内容自动填充，不允许手动修改）。每次对 Final 记录执行「保存更改」时自动追加。

---

## 核心接口（函数 API）

### 字段定义接口 — `FIELD_SCHEMA`

**这是整个应用最核心的扩展接口。** 所有元数据字段由此列表驱动，UI 渲染、校验逻辑、MD 生成均自动跟随，无需修改其他代码。

> 注意：评论区（`comments`）为独立的列表结构，不在 `FIELD_SCHEMA` 中定义，有专属的函数接口管理。

```python
FIELD_SCHEMA: list[dict] = [
    {
        "key":         str,   # 字段唯一标识符，对应 session dict 中的键名
        "label":       str,   # 界面显示名称
        "required":    bool,  # True = 必填（归档前必须填写）
        "type":        str,   # 控件类型，见下表
        "placeholder": str,   # 输入框占位文字
        "help":        str,   # 字段下方的说明小字
    },
    ...
]
```

**`type` 可选值**

| type | 渲染控件 | 存储格式 | 适用场景 |
|------|----------|----------|----------|
| `"textarea"` | 多行文本框 | `str` | 描述、感受等长文本 |
| `"text"` | 单行文本框 | `str` | 简短标签、标题 |
| `"date_or_text"` | 日历选取 + 自由输入双控件 | `str`（ISO日期或自由文本） | 时间类字段 |

`date_or_text` 优先级规则：自由输入框非空时使用自由输入值；否则使用日历选取值；两者均空时存储 `""`。

**当前默认字段**

| key | label | required | type |
|-----|-------|----------|------|
| `content_time` | 创建时间 | ✅ | `date_or_text` |
| `description` | 描述 | ✅ | `textarea` |
| `feeling` | 感受 | ✅ | `textarea` |
| `reason` | 记录原因 | ❌ | `textarea` |

---

### 数据库操作

```python
def load_db() -> list[dict]
```
读取 `pending_db.json`，返回所有 session 列表。文件不存在或损坏时返回 `[]`，不抛异常。

---

```python
def save_db(data: list[dict]) -> None
```
将 session 列表全量写入 `pending_db.json`（UTF-8，中文不转义，缩进 2）。

---

```python
def ensure_dirs() -> None
```
确保 `Assets/Pending/` 和 `Assets/Final/` 目录存在，应在应用启动时调用一次。

---

### Session 生命周期

```python
def save_session_pending(
    file_data_list: list[tuple[bytes, str]],
    source_type: str,
    field_values: dict,
) -> None
```
**暂存到待处理。** 将文件写入 `Assets/Pending/`，创建 session 记录（`status="pending"`）并追加到 DB。字段信息不完整也可调用。

| 参数 | 说明 |
|------|------|
| `file_data_list` | `[(文件字节, 原始文件名), ...]` |
| `source_type` | `"file"` 或 `"text"` |
| `field_values` | `{field_key: value}` 字典，字段可以不完整 |

---

```python
def save_session_final(
    file_data_list: list[tuple[bytes, str]],
    source_type: str,
    field_values: dict,
) -> None
```
**直接归档。** 将文件写入 `Assets/Final/`，创建 session 记录（`status="final"`），追加到 DB，并生成 `.md` 文件。调用前应确保必填项已通过 `validate_session` 校验。

---

```python
def move_to_final(session_id: str) -> None
```
**从 Pending 升级为 Final。** 将该 session 的所有文件从 `Assets/Pending/` 移动到 `Assets/Final/`，更新 DB 中的 `status`、`archive_time`、各文件 `path`，并生成 `.md` 文件。

---

```python
def update_session_fields(session_id: str, new_values: dict) -> None
```
**更新字段值。** 对 `pending` 记录：直接覆盖字段并重算 `is_complete`。对 `final` 记录：额外计算 diff 并追加到 `edit_history`，同时重写 `.md` 文件。纯文字记录的 `description` 字段不纳入 diff 计算。

---

### 评论操作

评论区为独立的列表结构（`session["comments"]`），与 `FIELD_SCHEMA` 字段完全分离，通过以下两个函数管理：

```python
def add_comment(session_id: str, text: str) -> None
```
**追加一条评论。** 自动生成 `id`（精确到微秒的时间戳字符串）和 `created_at`（当前时间），追加到指定 session 的 `comments` 列表。若 session 为 Final 状态，同时重写 `.md` 文件。

```python
# 生成的评论条目示例
{
    "id":         "20260425_100000_123456",
    "text":       "评论内容",
    "created_at": "2026-04-25 10:00:00"
}
```

---

```python
def delete_comment(session_id: str, comment_id: str) -> None
```
**删除指定 id 的评论。** 从 `comments` 列表中过滤掉对应条目。若 session 为 Final 状态，同时重写 `.md` 文件。

---

### 字段校验

```python
def validate_session(session: dict) -> list[str]
```
检查 session（或任意包含字段 key 的字典）中必填项是否已填写。  
返回**未填写的必填字段 label 列表**；空列表表示全部完整。

```python
# 示例
missing = validate_session({"content_time": "", "description": "内容", "feeling": "快乐"})
# → ["创建时间"]

missing = validate_session({"content_time": "2025-01", "description": "内容", "feeling": "快乐"})
# → []
```

---

```python
def _is_text_session(session: dict) -> bool
```
判断是否为纯文字记录（`source_type == "text"` 或全部文件均为 `.txt` / `.md`）。  
返回 `True` 时，`description` 字段由内容自动填充，UI 隐藏描述输入框，编辑历史不追踪描述变更。

---

### 视频处理

```python
def video_thumbnail(video_path: Path) -> Image.Image | None
```
使用 `cv2.VideoCapture` 提取视频第一帧，转换为 RGB PIL Image，并在左上角叠加黑底白字「▶ [视频]」标签。提取失败返回 `None`。

---

```python
def pil_to_png_bytes(img: Image.Image) -> bytes
```
将 PIL Image 转换为 PNG 格式的 bytes，供 `st.image()` 直接使用。

---

### UI 渲染层

```python
def render_field_inputs(
    prefix: str,
    defaults: dict | None = None,
    skip_keys: set | None = None,
) -> dict
```
遍历 `FIELD_SCHEMA`，在当前 Streamlit 上下文中渲染所有字段控件，返回 `{key: value}` 字典。  
**必须在 `with st.form():` 块内调用**，以避免每次交互触发重渲染。

| 参数 | 说明 |
|------|------|
| `prefix` | Widget key 前缀，同一页面多处调用时需保证唯一，如 `"upload"`、`"edit_20260424_192301"` |
| `defaults` | 字段预填值（编辑场景传入已有 session dict），`None` 表示空白表单 |
| `skip_keys` | 需要跳过渲染的字段 key 集合；跳过的字段仍以 `defaults` 中的值返回，不丢失 |

内部调用 `_render_date_or_text()` 处理 `date_or_text` 类型字段。

---

```python
def _render_comments(session: dict) -> None
```
**必须在 `st.form` 外部调用。** 渲染评论区，包含：
- 现有评论列表（时间戳 + 内容 + 删除按钮）
- 新评论输入框 + 发送按钮

点击删除或发送后立即写入 DB 并触发 `st.rerun()`。发送成功后自动清空输入框（通过清除对应 `session_state` key 实现）。

---

```python
def _render_card(col, session: dict, state_key: str) -> None
```
在给定的 `st.columns` 对象中渲染一张 session 卡片，包含：缩略图/文本预览、文件数徽章、评论数徽章、上传时间、完整度标签、选择按钮。点击按钮将 `session_id` 写入 `st.session_state[state_key]`。

---

```python
def _render_detail(session: dict, mode: str) -> None
```
渲染 session 详情区，包含：文件预览折叠区、编辑历史折叠区（Final 专有）、字段编辑表单、操作按钮、评论区。

| `mode` | 可用按钮 | 说明 |
|--------|----------|------|
| `"pending"` | 保存更改 / 完成并归档 / 取消 | 归档前校验必填项 |
| `"final"` | 保存更改 / 取消 | 保存时自动追加 edit_history |

纯文字记录（`_is_text_session` 返回 `True`）时，描述字段自动隐藏，显示提示信息。

---

### Streamlit 会话状态

应用使用以下三个 `st.session_state` 键：

| 键名 | 类型 | 说明 |
|------|------|------|
| `upload_key` | `int` | 递增计数器，用于重置 `file_uploader` 和粘贴文本框，使保存后控件清空 |
| `pending_selected` | `str \| None` | 当前在灵感墙选中的 `session_id`，`None` 表示无选中 |
| `archived_selected` | `str \| None` | 当前在已归档页选中的 `session_id`，`None` 表示无选中 |

此外，`_render_comments` 在发送评论后会删除 `new_cmt_{session_id}` 对应的 session_state key 以清空输入框。

---

## UI 页面说明

### Tab 1 — 🗂️ 记录舱（上传）

**上传方式**：顶部单选框切换「上传文件」和「粘贴文字」两种模式。

- **上传文件**：`st.file_uploader`，支持 jpg/png/mp4/md/txt，多选，同一批文件构成一条记录。
  - 若上传的**全部文件均为 txt/md**，描述字段自动使用第一个文件的内容填充，表单中隐藏描述输入框。
- **粘贴文字**：`st.text_area`，内容保存为 `.txt` 文件，文件名取文字首行前 20 字符（过滤 Windows 非法字符）。粘贴文字模式下描述字段始终自动填充，表单中隐藏。

**信息表单**：内容就绪后展示，包含 `FIELD_SCHEMA` 中除已自动填充字段外的所有字段。

**两个提交按钮**：

| 按钮 | 行为 |
|------|------|
| ✅ 完成并归档 | 校验必填项，通过则写入 Final；不通过显示 `st.error` |
| 📦 暂存到待处理 | 无条件暂存，有缺失项时显示 `st.warning` 提示缺少哪些字段 |

---

### Tab 2 — 🖼️ 灵感墙（待处理）

展示 `status="pending"` 的 session，按 `upload_time` **降序**排列（最新在前）。

**卡片内容**：第一个文件的缩略图（视频显示第一帧，文本显示文字预览）、文件数徽章、评论数徽章、上传时间、完整度标签（`✅ 信息完整` / `⚠️ 待补充：字段名`）。

**点击「查看/编辑」**：在页面下方展开详情区，可编辑所有字段，支持「保存更改」或「完成并归档」（归档前再次校验必填项），详情区底部为评论区。

---

### Tab 3 — 📚 已归档

展示 `status="final"` 的 session，按 `upload_time` **降序**排列。

**额外功能**：
- 详情区支持查看**编辑历史**（折叠展示，逆时间序）
- 保存更改时自动追加新的历史条目并重写 `.md` 文件
- 详情区底部为**评论区**，可随时追加或删除评论

---

### 评论区（所有记录通用）

评论区位于详情区底部（form 外部），无论记录状态（pending / final）均可操作。

- **查看**：按时间升序展示所有评论，每条显示时间戳和内容
- **发表**：输入内容后点击「发送评论」，自动记录当前时间，输入框自动清空
- **删除**：每条评论右侧有 🗑️ 按钮，点击立即删除

Final 记录的评论变更会同步重写对应的 `.md` 文件。

---

### Markdown 文件格式

每条 Final 记录在 `Assets/Final/{session_id}.md` 生成对应文档：

```markdown
# 原始文件名（等 N 个文件）

**上传时间**：2026-04-24 19:23:01
**归档时间**：2026-04-24 20:00:00

## 创建时间

2025-06-01

## 描述

关于这段内容的描述……

## 感受

当时的感受……

---

## 评论区

**2026-04-25 10:00:00**

留给未来的自己……

---

## 编辑历史

### 2026-04-25 11:00:00

- **感受**：「旧感受」→「新感受」
```

---

## 扩展开发指南

### 1. 新增元数据字段

只需在 `FIELD_SCHEMA` 列表中追加一个字典，无需修改任何其他代码：

```python
{
    "key":         "mood_score",
    "label":       "心情评分",
    "required":    False,
    "type":        "text",
    "placeholder": "1-10 分，10 分为最佳",
    "help":        "选填，用数字量化当时的心情",
},
```

新字段会自动出现在上传表单、灵感墙编辑区、已归档编辑区，并写入 `.md` 文件。  
> 注意：旧有的 session 记录中不含该字段，读取时 `session.get("mood_score", "")` 返回空字符串，功能不受影响。

---

### 2. 新增支持的文件类型

**a. 在上传器中允许新类型**（`render_upload_tab` 函数）：

```python
files = st.file_uploader(
    "...",
    type=["jpg", "jpeg", "png", "mp4", "md", "txt", "pdf"],  # 添加 "pdf"
    ...
)
```

**b. 在 `_session_thumb` 中添加缩略图生成逻辑**：

```python
if ext == ".pdf":
    # 使用 pymupdf / pdf2image 提取首页缩略图
    return render_pdf_thumb(fp)
```

**c. 在 `_render_detail` 的文件预览区添加对应渲染分支**：

```python
elif ext == ".pdf":
    st.markdown(f"📑 PDF 文件（{fp.stat().st_size // 1024} KB）")
```

**d. 若新类型属于「文字型」，在 `TEXT_EXTS` 中追加扩展名**（`app.py` 顶部常量）：

```python
TEXT_EXTS = {".txt", ".md", ".rst"}  # 新增 .rst
```

---

### 3. 接入外部存储

当前所有 I/O 集中在以下函数，替换它们即可切换存储后端：

| 函数 | 当前行为 | 替换方向 |
|------|----------|----------|
| `load_db()` | 读本地 JSON | 查询数据库 / 对象存储 |
| `save_db()` | 写本地 JSON | 写入数据库 / 对象存储 |
| `_write_files()` | 写本地文件 | 上传到 OSS / S3 |
| `move_to_final()` | 本地 `shutil.move` | 远程 copy + delete |
| `_write_md()` | 写本地 .md | 上传到对象存储 |

---

### 4. 新增 Tab 页面

在 `main()` 中添加新 Tab 并调用对应渲染函数：

```python
tab1, tab2, tab3, tab4 = st.tabs([
    "🗂️ 记录舱（上传）",
    "🖼️ 灵感墙（待处理）",
    "📚 已归档",
    "📊 统计分析",          # 新增
])
with tab4:
    render_stats_tab()    # 自定义函数
```

读取 DB 数据：

```python
def render_stats_tab() -> None:
    db = load_db()
    final = [s for s in db if s.get("status") == "final"]
    pending = [s for s in db if s.get("status") == "pending"]
    # 使用 pandas / st.bar_chart 等展示统计信息
```

---

### 5. 改造为多用户版本

当前瓶颈：`pending_db.json` 是单一全局文件，`Assets/` 目录不区分用户。

改造方向：

1. 在 Session 结构中添加 `"user_id"` 字段。
2. 将 `load_db()` / `save_db()` 改造为按 `user_id` 过滤。
3. 文件存储路径改为 `Assets/{user_id}/Pending/` 和 `Assets/{user_id}/Final/`。
4. 在 `init_state()` 中初始化 `st.session_state.user_id`（可结合 `st.login` 或简单的用户名输入实现）。
5. 评论区可扩展 `author` 字段标识评论者身份。
