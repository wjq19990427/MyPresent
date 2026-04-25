from __future__ import annotations

import io
import json
import shutil
from datetime import datetime
from pathlib import Path

import cv2
import streamlit as st
from PIL import Image, ImageDraw

# ─── 路径常量 ──────────────────────────────────────────────────────────────────
ASSETS_DIR    = Path("Assets")
FINAL_DIR     = ASSETS_DIR / "Final"
PENDING_DIR   = ASSETS_DIR / "Pending"
DB_FILE       = Path("pending_db.json")
VECTOR_DB_DIR = Path(__file__).parent / "vector_db"
COLS          = 3
TEXT_EXTS     = {".txt", ".md"}
IMAGE_EXTS    = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}

# 所有支持上传的视频格式
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".webm",
              ".flv", ".m4v", ".3gp", ".ts", ".mts", ".mpg", ".mpeg"}
# 浏览器 HTML5 可直接播放的格式
VIDEO_EXTS_PLAYABLE = {".mp4", ".webm", ".mov", ".m4v", ".ogg"}


def _file_subdir(filename: str) -> str:
    """根据扩展名返回子目录名：images / videos / text。"""
    ext = Path(filename).suffix.lower()
    if ext in IMAGE_EXTS:  return "images"
    if ext in VIDEO_EXTS:  return "videos"
    return "text"


# ═══════════════════════════════════════════════════════════════════════════════
# 字段定义 ── 扩展接口：增删字段只改此处，UI/校验逻辑自动跟随
# type 可选: "textarea" | "text" | "date_or_text"
# 注：评论区（comments）为独立列表结构，不在此定义
# ═══════════════════════════════════════════════════════════════════════════════
FIELD_SCHEMA: list[dict] = [
    {
        "key":         "content_time",
        "label":       "创建时间",
        "required":    True,
        "type":        "date_or_text",
        "placeholder": "不知确切日期可填「去年夏天」等描述",
        "help":        "这段文字 / 视频 / 图片被创建的时间（必填）",
    },
    {
        "key":         "description",
        "label":       "描述",
        "required":    True,
        "type":        "textarea",
        "placeholder": "关于这段记录的具体内容……",
        "help":        "必填；纯文字记录自动使用内容填充，无需手动填写",
    },
    {
        "key":         "feeling",
        "label":       "感受",
        "required":    True,
        "type":        "textarea",
        "placeholder": "这段记忆带给你怎样的感受？",
        "help":        "必填",
    },
    {
        "key":         "reason",
        "label":       "记录原因",
        "required":    False,
        "type":        "textarea",
        "placeholder": "为什么想要记录这段内容？（选填）",
        "help":        "选填",
    },
]

REQUIRED_KEYS = [f["key"] for f in FIELD_SCHEMA if f["required"]]


# ═══════════════════════════════════════════════════════════════════════════════
# 文件与数据操作
# ═══════════════════════════════════════════════════════════════════════════════

def ensure_dirs() -> None:
    for base in (FINAL_DIR, PENDING_DIR):
        for sub in ("images", "videos", "text"):
            (base / sub).mkdir(parents=True, exist_ok=True)
    VECTOR_DB_DIR.mkdir(parents=True, exist_ok=True)


def load_db() -> list[dict]:
    if not DB_FILE.exists():
        return []
    try:
        return json.loads(DB_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def save_db(data: list[dict]) -> None:
    DB_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def validate_session(session: dict) -> list[str]:
    """返回未填写的必填项 label 列表；空列表 = 全部完整。"""
    label_map = {f["key"]: f["label"] for f in FIELD_SCHEMA}
    return [label_map[k] for k in REQUIRED_KEYS
            if not str(session.get(k, "")).strip()]


def _is_text_session(session: dict) -> bool:
    """粘贴文字 或 全部文件均为 txt/md 时返回 True。"""
    if session.get("source_type") == "text":
        return True
    files = session.get("files", [])
    return bool(files) and all(
        Path(fe["filename"]).suffix.lower() in TEXT_EXTS for fe in files
    )


def _apply_fields(session: dict, field_values: dict) -> None:
    for f in FIELD_SCHEMA:
        session[f["key"]] = str(field_values.get(f["key"], "")).strip()
    session["is_complete"] = not validate_session(session)


def _make_session(
    session_id: str,
    file_entries: list[dict],
    source_type: str,
    field_values: dict,
) -> dict:
    session = {
        "session_id":   session_id,
        "status":       "pending",
        "files":        file_entries,
        "source_type":  source_type,
        "upload_time":  datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "archive_time": "",
        "edit_history": [],
        "comments":     [],
    }
    _apply_fields(session, field_values)
    return session


def _write_files(
    file_data_list: list[tuple], dest_dir: Path, session_id: str
) -> list[dict]:
    """data 可以是 bytes 或 file-like 对象（大文件流式写入，避免内存双倍占用）。
    文件按类型自动存入 images / videos / text 子目录。
    """
    entries = []
    for idx, (data, orig_name) in enumerate(file_data_list):
        filename = f"{session_id}_{idx:03d}_{orig_name}"
        sub      = _file_subdir(filename)
        dest     = dest_dir / sub / filename
        dest.parent.mkdir(parents=True, exist_ok=True)
        if hasattr(data, "read"):
            with dest.open("wb") as f:
                shutil.copyfileobj(data, f)
        else:
            dest.write_bytes(data)
        entries.append({
            "filename":      filename,
            "original_name": orig_name,
            "path":          str(dest),
        })
    return entries


def _write_md(session: dict) -> None:
    """生成/更新 Final 目录中该 session 的 .md 文件。"""
    title = session["files"][0]["original_name"] if session["files"] else "记录"
    if len(session["files"]) > 1:
        title += f" 等 {len(session['files'])} 个文件"

    lines = [f"# {title}\n\n"]
    lines.append(f"**上传时间**：{session.get('upload_time', '')}\n")
    if session.get("archive_time"):
        lines.append(f"**归档时间**：{session['archive_time']}\n")
    lines.append("\n")

    for field in FIELD_SCHEMA:
        v = str(session.get(field["key"], "")).strip()
        if v:
            lines.append(f"## {field['label']}\n\n{v}\n\n")

    comments = [c for c in session.get("comments", []) if isinstance(c, dict)]
    if comments:
        lines.append("---\n\n## 评论区\n\n")
        for c in comments:
            lines.append(f"**{c.get('created_at', '')}**\n\n{c.get('text', '')}\n\n")

    history = session.get("edit_history", [])
    if history:
        lines.append("---\n\n## 编辑历史\n\n")
        for edit in history:
            lines.append(f"### {edit['edited_at']}\n\n")
            for fk, change in edit["changes"].items():
                lbl = next((f["label"] for f in FIELD_SCHEMA if f["key"] == fk), fk)
                lines.append(f"- **{lbl}**：「{change['from']}」→「{change['to']}」\n")
            lines.append("\n")

    (FINAL_DIR / f"{session['session_id']}.md").write_text(
        "".join(lines), encoding="utf-8"
    )


def save_session_pending(
    file_data_list: list[tuple], source_type: str, field_values: dict
) -> None:
    sid          = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_entries = _write_files(file_data_list, PENDING_DIR, sid)
    session      = _make_session(sid, file_entries, source_type, field_values)
    db = load_db()
    db.append(session)
    save_db(db)


def save_session_final(
    file_data_list: list[tuple], source_type: str, field_values: dict
) -> None:
    sid          = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_entries = _write_files(file_data_list, FINAL_DIR, sid)
    session      = _make_session(sid, file_entries, source_type, field_values)
    session["status"]       = "final"
    session["archive_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    session["is_complete"]  = True
    db = load_db()
    db.append(session)
    save_db(db)
    _write_md(session)
    embed_session(session)


def move_to_final(session_id: str) -> None:
    db      = load_db()
    session = next((s for s in db if s["session_id"] == session_id), None)
    if not session:
        return
    for fe in session["files"]:
        src  = Path(fe["path"])
        sub  = _file_subdir(fe["filename"])
        dest = FINAL_DIR / sub / fe["filename"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.exists():
            shutil.move(str(src), str(dest))
        fe["path"] = str(dest)
    session["status"]       = "final"
    session["archive_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    session["is_complete"]  = True
    save_db(db)
    _write_md(session)
    embed_session(session)


def update_session_fields(session_id: str, new_values: dict) -> None:
    """更新字段；Final 记录额外追加 edit_history 并重写 .md。"""
    db      = load_db()
    session = next((s for s in db if s["session_id"] == session_id), None)
    if not session:
        return

    if session.get("status") == "final":
        is_text = _is_text_session(session)
        changes = {}
        for f in FIELD_SCHEMA:
            k = f["key"]
            if is_text and k == "description":
                continue
            old = str(session.get(k, "")).strip()
            new = str(new_values.get(k, "")).strip()
            if old != new:
                changes[k] = {"from": old, "to": new}
        if changes:
            session.setdefault("edit_history", []).append({
                "edited_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "changes":   changes,
            })

    _apply_fields(session, new_values)
    save_db(db)

    if session.get("status") == "final":
        _write_md(session)
        embed_session(session)


def add_comment(session_id: str, text: str) -> None:
    """追加一条评论（含自动时间戳）。"""
    db      = load_db()
    session = next((s for s in db if s["session_id"] == session_id), None)
    if not session or not text.strip():
        return
    now = datetime.now()
    session.setdefault("comments", []).append({
        "id":         now.strftime("%Y%m%d_%H%M%S_%f"),
        "text":       text.strip(),
        "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
    })
    save_db(db)
    if session.get("status") == "final":
        _write_md(session)


def delete_comment(session_id: str, comment_id: str) -> None:
    """删除指定 id 的评论。"""
    db      = load_db()
    session = next((s for s in db if s["session_id"] == session_id), None)
    if not session:
        return
    session["comments"] = [
        c for c in session.get("comments", [])
        if isinstance(c, dict) and c.get("id") != comment_id
    ]
    save_db(db)
    if session.get("status") == "final":
        _write_md(session)


# ═══════════════════════════════════════════════════════════════════════════════
# 向量数据库 — Phase 2.1 Embedding 层
# ═══════════════════════════════════════════════════════════════════════════════

@st.cache_resource(show_spinner="正在加载 Embedding 模型（首次需要下载，请稍候）…")
def _get_embedder():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer("BAAI/bge-small-zh-v1.5")


@st.cache_resource(show_spinner="正在初始化向量数据库…")
def _get_collection():
    import chromadb
    client = chromadb.PersistentClient(path=str(VECTOR_DB_DIR))
    return client.get_or_create_collection(
        name="sessions",
        metadata={"hnsw:space": "cosine"},
    )


def _build_embed_text(session: dict) -> str:
    """将 session 的文本字段拼接为用于 embedding 的文档字符串。"""
    parts = []
    for key, label in [
        ("content_time", "创建时间"),
        ("description",  "描述"),
        ("feeling",      "感受"),
        ("reason",       "记录原因"),
    ]:
        v = str(session.get(key, "")).strip()
        if v:
            parts.append(f"{label}：{v}")
    return "\n".join(parts)


def _parse_date_iso(raw: str) -> tuple[str, int]:
    """将 content_time 解析为 (YYYY-MM-DD, YYYYMMDD整数)；无法解析返回 ('', 0)。"""
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d",
                "%Y-%m",   "%Y/%m",    "%Y"):
        try:
            dt = datetime.strptime(raw.strip(), fmt)
            return dt.strftime("%Y-%m-%d"), int(dt.strftime("%Y%m%d"))
        except ValueError:
            continue
    return "", 0


def _build_chroma_metadata(session: dict) -> dict:
    raw      = str(session.get("content_time", "")).strip()
    iso, num = _parse_date_iso(raw)
    return {
        "session_id":        session["session_id"],
        "content_time_raw":  raw,
        "content_time_iso":  iso,
        "content_time_num":  num,   # int YYYYMMDD，供 $gte/$lte 数值比较
        "has_exact_date":    iso != "",
        "upload_time":       session.get("upload_time", ""),
        "archive_time":      session.get("archive_time", ""),
        "source_type":       session.get("source_type", ""),
    }


def embed_session(session: dict) -> None:
    """将 session 写入向量库（upsert，插入与更新均适用）。"""
    try:
        text = _build_embed_text(session)
        if not text.strip():
            return
        embedding = _get_embedder().encode(
            text, normalize_embeddings=True
        ).tolist()
        _get_collection().upsert(
            ids=[session["session_id"]],
            embeddings=[embedding],
            documents=[text],
            metadatas=[_build_chroma_metadata(session)],
        )
    except Exception:
        pass  # 向量库写入失败不影响主流程


def delete_embedding(session_id: str) -> None:
    try:
        _get_collection().delete(ids=[session_id])
    except Exception:
        pass


def index_existing_finals() -> int:
    """将尚未入库的 Final 记录批量写入向量库，返回新增数量。"""
    db     = load_db()
    finals = [s for s in db if s.get("status") == "final"]
    if not finals:
        return 0
    existing = set(_get_collection().get(include=[])["ids"])
    to_index = [s for s in finals if s["session_id"] not in existing]
    for s in to_index:
        embed_session(s)
    return len(to_index)


def _ensure_indexed() -> None:
    """应用启动时调用，补全历史 Final 记录的向量索引。
    若检测到 metadata schema 升级（缺少 content_time_num），自动全量重建。
    """
    if st.session_state.get("_vector_db_ready"):
        return
    st.session_state["_vector_db_ready"] = True
    db     = load_db()
    finals = [s for s in db if s.get("status") == "final"]
    if not finals:
        return
    try:
        with st.spinner("🗄️ 正在初始化向量库…"):
            col      = _get_collection()
            existing = col.get(include=["metadatas"])
            existing_ids = set(existing["ids"])

            # 检测旧 schema（缺少 content_time_num 字段）→ 全量重建
            needs_migration = bool(existing["metadatas"]) and \
                              "content_time_num" not in existing["metadatas"][0]

            if needs_migration:
                for s in finals:
                    embed_session(s)
                count = len(finals)
            else:
                to_index = [s for s in finals if s["session_id"] not in existing_ids]
                for s in to_index:
                    embed_session(s)
                count = len(to_index)

        if count > 0:
            label = "已迁移并重建" if needs_migration else "已补全索引"
            st.toast(f"向量库{label}：{count} 条归档记录", icon="🗄️")
    except Exception as e:
        st.warning(f"向量库初始化失败（搜索功能不可用）：{e}")


# ═══════════════════════════════════════════════════════════════════════════════
# 视频处理
# ═══════════════════════════════════════════════════════════════════════════════

def video_thumbnail(video_path: Path) -> Image.Image | None:
    cap = cv2.VideoCapture(str(video_path))
    ok, frame = cap.read()
    cap.release()
    if not ok:
        return None
    img  = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, 90, 26], fill=(0, 0, 0))
    draw.text((6, 5), "▶ [视频]", fill=(255, 255, 255))
    return img


def pil_to_png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════════════════
# 表单字段渲染
# ═══════════════════════════════════════════════════════════════════════════════

def _render_date_or_text(field: dict, prefix: str, default: str = "") -> str:
    """渲染日历选取 + 自由输入双控件，自由输入优先。"""
    default_date = None
    default_free = default
    if default:
        try:
            default_date = datetime.strptime(default, "%Y-%m-%d").date()
            default_free = ""
        except ValueError:
            pass

    col1, col2 = st.columns(2)
    with col1:
        sel_date = st.date_input(
            "📅 日历选取",
            value=default_date,
            key=f"{prefix}_{field['key']}_date",
        )
    with col2:
        free = st.text_input(
            "✏️ 自由输入",
            value=default_free,
            placeholder=field["placeholder"],
            key=f"{prefix}_{field['key']}_text",
        )
    return free.strip() if free.strip() else (str(sel_date) if sel_date else "")


def render_field_inputs(
    prefix: str,
    defaults: dict | None = None,
    skip_keys: set | None = None,
) -> dict:
    """根据 FIELD_SCHEMA 渲染所有字段，返回 {key: value}。
    skip_keys 中的字段不渲染控件，但其已有值仍保留在返回值中。
    """
    defaults         = defaults or {}
    skip_keys        = skip_keys or set()
    values           = {}
    shown_opt_header = False

    for field in FIELD_SCHEMA:
        key = field["key"]

        if key in skip_keys:
            values[key] = str(defaults.get(key, ""))
            continue

        if not field["required"] and not shown_opt_header:
            st.divider()
            st.caption("以下为选填项")
            shown_opt_header = True

        badge = " **\\*（必填）**" if field["required"] else " （选填）"
        st.markdown(f"**{field['label']}**{badge}")
        if field.get("help"):
            st.caption(field["help"])

        default = str(defaults.get(key, ""))
        wkey    = f"{prefix}_{key}"

        if field["type"] == "date_or_text":
            values[key] = _render_date_or_text(field, prefix, default)
        elif field["type"] == "textarea":
            values[key] = st.text_area(
                field["label"],
                value=default,
                placeholder=field["placeholder"],
                height=100,
                key=wkey,
                label_visibility="collapsed",
            )
        else:
            values[key] = st.text_input(
                field["label"],
                value=default,
                placeholder=field["placeholder"],
                key=wkey,
                label_visibility="collapsed",
            )

    return values


# ═══════════════════════════════════════════════════════════════════════════════
# 评论区渲染（在 form 外部调用，支持实时增删）
# ═══════════════════════════════════════════════════════════════════════════════

def _render_comments(session: dict) -> None:
    sid       = session["session_id"]
    comments  = [c for c in session.get("comments", []) if isinstance(c, dict)]
    input_key = f"new_cmt_{sid}"

    st.markdown("#### 💬 评论区")

    if comments:
        for c in comments:
            col_text, col_del = st.columns([11, 1])
            with col_text:
                st.markdown(
                    f"<small style='color:gray'>{c.get('created_at', '')}</small>  \n"
                    f"{c.get('text', '')}",
                    unsafe_allow_html=True,
                )
            with col_del:
                if st.button("🗑️", key=f"del_cmt_{c['id']}", help="删除此评论"):
                    delete_comment(sid, c["id"])
                    st.rerun()
        st.divider()
    else:
        st.caption("暂无评论，发表第一条吧～")

    new_text = st.text_area(
        "发表评论",
        placeholder="写点什么……",
        height=80,
        key=input_key,
        label_visibility="collapsed",
    )
    if st.button("发送评论", key=f"send_cmt_{sid}"):
        if new_text.strip():
            add_comment(sid, new_text)
            if input_key in st.session_state:
                del st.session_state[input_key]
            st.rerun()
        else:
            st.warning("评论内容不能为空")


# ═══════════════════════════════════════════════════════════════════════════════
# 会话状态初始化
# ═══════════════════════════════════════════════════════════════════════════════

def init_state() -> None:
    for k, v in {
        "upload_key":          0,
        "pending_selected":    None,
        "archived_selected":   None,
        "search_selected":     None,
        # 搜索结果持久化（rerun 后仍可展示详情）
        "semantic_results":    None,   # list[(sid, score)] | None
        "semantic_query_used": "",
        "date_filter_exact":   None,   # list[(sid, meta)] | None
        "date_filter_fuzzy":   None,   # list[sid] | None
        "date_filter_range":   ("", ""),
        "_search_mode_prev":   None,
    }.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ═══════════════════════════════════════════════════════════════════════════════
# 🗂️ 记录舱 Tab
# ═══════════════════════════════════════════════════════════════════════════════

def _pasted_filename(text: str) -> str:
    first = text.strip().split("\n")[0][:20].strip()
    safe  = "".join(c for c in first if c not in r'\/:*?"<>|').strip()
    return f"{safe}.txt" if safe else "paste.txt"


def render_upload_tab() -> None:
    source_mode = st.radio(
        "上传方式",
        ["📁 上传文件", "📝 粘贴文字"],
        horizontal=True,
        key="source_mode",
    )

    files: list      = []
    pasted_text      = ""
    is_text_content  = False
    auto_description = ""

    if source_mode == "📁 上传文件":
        files = st.file_uploader(
            "支持图片、各种格式视频、文本（可多选，本次上传构成一条记录）",
            type=["jpg", "jpeg", "png",
                  "mp4", "mov", "avi", "mkv", "wmv", "webm",
                  "flv", "m4v", "3gp", "ts", "mts", "mpg", "mpeg",
                  "md", "txt"],
            accept_multiple_files=True,
            key=f"uploader_{st.session_state.upload_key}",
        ) or []
        content_ready = bool(files)
        if files and all(Path(f.name).suffix.lower() in TEXT_EXTS for f in files):
            is_text_content = True
            try:
                auto_description = files[0].getvalue().decode("utf-8")
            except Exception:
                auto_description = ""
    else:
        pasted_text = st.text_area(
            "在此粘贴或输入文字",
            placeholder="将文字内容粘贴到此处……",
            height=200,
            key=f"paste_{st.session_state.upload_key}",
        ) or ""
        content_ready    = bool(pasted_text.strip())
        is_text_content  = True
        auto_description = pasted_text

    if not content_ready:
        st.info("请先提供内容（上传文件 或 粘贴文字）")
        return

    if source_mode == "📁 上传文件":
        st.write(f"已选 **{len(files)}** 个文件，本次作为**一条记录**保存")
        if is_text_content:
            st.info("📝 纯文本文件，描述将自动使用文件内容填充")
    else:
        st.caption(f"文字长度：{len(pasted_text)} 字符")
    st.caption("⏱️ 上传时间将在保存时自动记录")
    st.divider()

    skip = {"description"} if is_text_content else set()

    with st.form("upload_meta_form"):
        st.markdown("### 📋 填写记录信息")
        if is_text_content:
            st.caption("💡 描述已自动使用内容填充，无需手动填写")
        field_values = render_field_inputs("upload", skip_keys=skip)
        if is_text_content:
            field_values["description"] = auto_description
        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            do_archive = st.form_submit_button(
                "✅ 完成并归档", type="primary", use_container_width=True
            )
        with c2:
            do_pending = st.form_submit_button(
                "📦 暂存到待处理", use_container_width=True
            )

    if source_mode == "📁 上传文件":
        file_data = [(f, f.name) for f in files]
        src_type  = "file"
    else:
        file_data = [(pasted_text.encode("utf-8"), _pasted_filename(pasted_text))]
        src_type  = "text"

    if do_archive:
        missing = validate_session(
            {f["key"]: str(field_values.get(f["key"], "")).strip() for f in FIELD_SCHEMA}
        )
        if missing:
            st.error(
                f"❌ 以下必填项未填写：**{'、'.join(missing)}**\n\n"
                "请补充后归档，或点「暂存到待处理」先保存。"
            )
        else:
            save_session_final(file_data, src_type, field_values)
            st.session_state.upload_key += 1
            st.rerun()

    if do_pending:
        save_session_pending(file_data, src_type, field_values)
        missing = validate_session(
            {f["key"]: str(field_values.get(f["key"], "")).strip() for f in FIELD_SCHEMA}
        )
        if missing:
            st.warning(
                f"📦 已暂存！缺少必填项：**{'、'.join(missing)}**\n\n"
                "请到「灵感墙」补充完整后再归档。"
            )
        else:
            st.success("📦 已暂存！信息完整，也可在「灵感墙」直接归档。")
        st.session_state.upload_key += 1
        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# 画廊共用工具
# ═══════════════════════════════════════════════════════════════════════════════

def _session_thumb(session: dict) -> bytes | str | None:
    if not session.get("files"):
        return None
    fp  = Path(session["files"][0]["path"])
    ext = fp.suffix.lower()
    if not fp.exists():
        return None
    if ext in {".jpg", ".jpeg", ".png"}:
        return str(fp)
    if ext in VIDEO_EXTS:
        thumb = video_thumbnail(fp)
        return pil_to_png_bytes(thumb) if thumb else None
    return None


def _completion_badge(session: dict) -> str:
    missing = validate_session(session)
    return "✅ 信息完整" if not missing else f"⚠️ 待补充：{'、'.join(missing)}"


def _render_card(
    col, session: dict, state_key: str, score: float | None = None
) -> None:
    sid     = session["session_id"]
    is_sel  = st.session_state.get(state_key) == sid
    thumb   = _session_thumb(session)
    n_files = len(session.get("files", []))
    n_cmts  = len([c for c in session.get("comments", []) if isinstance(c, dict)])

    with col:
        if thumb:
            st.image(thumb, use_container_width=True)
        elif session.get("source_type") == "text":
            st.markdown("📄 **文本记录**")
            try:
                fp = Path(session["files"][0]["path"])
                st.caption(fp.read_text(encoding="utf-8")[:50].replace("\n", " ") + "…")
            except OSError:
                pass
        else:
            st.markdown("📎 **文件记录**")

        if n_files > 1:
            st.caption(f"📎 共 {n_files} 个文件")
        if n_cmts:
            st.caption(f"💬 {n_cmts} 条评论")
        if score is not None:
            st.caption(f"🎯 相似度 {score:.0%}")
        st.caption(f"🕐 {session.get('upload_time', '')}")
        st.caption(_completion_badge(session))

        label = "✅ 已选" if is_sel else "🔍 查看 / 编辑"
        if st.button(label, key=f"{state_key}_btn_{sid}", use_container_width=True):
            st.session_state[state_key] = None if is_sel else sid
            st.rerun()


def _render_detail(
    session: dict, mode: str, state_key: str | None = None
) -> None:
    """共用详情 + 编辑表单，mode='pending'|'final'。
    state_key 默认由 mode 推导，搜索 Tab 需显式传入 'search_selected'。
    """
    sid = session["session_id"]
    if state_key is None:
        state_key = "pending_selected" if mode == "pending" else "archived_selected"
    title     = session["files"][0]["original_name"] if session["files"] else "记录"
    is_text   = _is_text_session(session)

    heading = "编辑待处理记录" if mode == "pending" else "编辑已归档记录"
    st.subheader(f"📝 {heading}：{title}")

    time_info = f"上传时间：{session.get('upload_time', '')}"
    if mode == "final" and session.get("archive_time"):
        time_info += f"  ·  归档时间：{session['archive_time']}"
    st.caption(time_info)

    missing_now = validate_session(session)
    if missing_now and mode == "pending":
        st.warning(f"⚠️ 以下必填项尚未填写：**{'、'.join(missing_now)}**")
    elif not missing_now:
        st.success("✅ 所有必填项已完整")

    with st.expander(f"查看文件（{len(session.get('files', []))} 个）", expanded=False):
        for fe in session.get("files", []):
            fp  = Path(fe["path"])
            ext = fp.suffix.lower()
            st.markdown(f"**{fe['original_name']}**")
            if not fp.exists():
                st.warning("文件不存在")
                continue
            if ext in {".jpg", ".jpeg", ".png"}:
                st.image(str(fp), use_container_width=True)
            elif ext in VIDEO_EXTS_PLAYABLE:
                st.video(str(fp))
            elif ext in VIDEO_EXTS:
                size_mb = fp.stat().st_size / 1024 / 1024
                st.info(f"🎬 {fe['original_name']}（{size_mb:.1f} MB）\n\n"
                        "该格式浏览器不支持直接播放，请用本地播放器打开文件。")
                with open(fp, "rb") as fh:
                    st.download_button(
                        "⬇️ 下载文件",
                        data=fh,
                        file_name=fe["original_name"],
                        key=f"dl_{fe['filename']}",
                    )
            else:
                try:
                    st.text_area(
                        "内容预览",
                        fp.read_text(encoding="utf-8"),
                        height=150,
                        disabled=True,
                        key=f"prev_{fe['filename']}",
                    )
                except OSError:
                    st.warning("无法读取文件内容")

    if mode == "final" and session.get("edit_history"):
        with st.expander(f"编辑历史（{len(session['edit_history'])} 次）"):
            for edit in reversed(session["edit_history"]):
                st.markdown(f"**{edit['edited_at']}**")
                for fk, change in edit["changes"].items():
                    lbl = next((f["label"] for f in FIELD_SCHEMA if f["key"] == fk), fk)
                    st.markdown(f"- **{lbl}**：「{change['from']}」→「{change['to']}」")
                st.divider()

    safe_sid    = "".join(c if c.isalnum() else "_" for c in sid)
    edit_prefix = f"edit_{safe_sid}"
    skip_keys   = {"description"} if is_text else set()

    if is_text:
        st.info("📝 纯文字记录：描述由内容自动填充，不可手动修改")

    with st.form(f"form_{safe_sid}"):
        st.markdown("#### ✏️ 编辑字段")
        field_values = render_field_inputs(edit_prefix, defaults=session, skip_keys=skip_keys)
        if is_text:
            field_values["description"] = str(session.get("description", ""))
        st.divider()

        if mode == "pending":
            c1, c2, c3 = st.columns(3)
            with c1:
                do_save    = st.form_submit_button("💾 保存更改", use_container_width=True)
            with c2:
                do_archive = st.form_submit_button(
                    "✅ 完成并归档", type="primary", use_container_width=True
                )
            with c3:
                do_cancel  = st.form_submit_button("取消", use_container_width=True)
        else:
            c1, c2 = st.columns([3, 1])
            with c1:
                do_save   = st.form_submit_button(
                    "💾 保存更改", type="primary", use_container_width=True
                )
            with c2:
                do_cancel = st.form_submit_button("取消", use_container_width=True)
            do_archive = False

    if do_cancel:
        st.session_state[state_key] = None
        st.rerun()

    if do_save:
        update_session_fields(sid, field_values)
        st.session_state[state_key] = sid
        st.rerun()

    if do_archive:
        merged  = {f["key"]: str(field_values.get(f["key"], "")).strip() for f in FIELD_SCHEMA}
        missing = validate_session(merged)
        if missing:
            st.error(f"❌ 以下必填项仍未填写：**{'、'.join(missing)}**，请补充后再归档。")
        else:
            update_session_fields(sid, field_values)
            move_to_final(sid)
            st.session_state[state_key] = None
            st.rerun()

    st.divider()
    _render_comments(session)


# ═══════════════════════════════════════════════════════════════════════════════
# 🖼️ 灵感墙 Tab（Pending）
# ═══════════════════════════════════════════════════════════════════════════════

def render_gallery_tab() -> None:
    all_db = load_db()
    db = sorted(
        [s for s in all_db
         if s.get("status") == "pending"
         and any(Path(fe["path"]).exists() for fe in s.get("files", []))],
        key=lambda s: s.get("upload_time", ""),
        reverse=True,
    )

    if not db:
        st.info("🎉 待处理队列为空！去「记录舱」上传内容吧。")
        return

    st.caption(f"共 **{len(db)}** 条待处理记录，按上传时间由近到远排列")
    st.divider()

    for row_start in range(0, len(db), COLS):
        cols = st.columns(COLS)
        for col, session in zip(cols, db[row_start: row_start + COLS]):
            _render_card(col, session, "pending_selected")

    sel = st.session_state.pending_selected
    if not sel:
        return
    target = next((s for s in db if s["session_id"] == sel), None)
    if not target:
        st.session_state.pending_selected = None
        return
    st.divider()
    _render_detail(target, "pending")


# ═══════════════════════════════════════════════════════════════════════════════
# 📚 已归档 Tab（Final）
# ═══════════════════════════════════════════════════════════════════════════════

def render_archived_tab() -> None:
    all_db = load_db()
    db = sorted(
        [s for s in all_db if s.get("status") == "final"],
        key=lambda s: s.get("upload_time", ""),
        reverse=True,
    )

    if not db:
        st.info("暂无已归档记录。在「灵感墙」补全后归档，或在「记录舱」直接完成归档。")
        return

    st.caption(f"共 **{len(db)}** 条已归档记录")
    st.divider()

    for row_start in range(0, len(db), COLS):
        cols = st.columns(COLS)
        for col, session in zip(cols, db[row_start: row_start + COLS]):
            _render_card(col, session, "archived_selected")

    sel = st.session_state.archived_selected
    if not sel:
        return
    target = next((s for s in all_db if s["session_id"] == sel), None)
    if not target:
        st.session_state.archived_selected = None
        return
    st.divider()
    _render_detail(target, "final")


# ═══════════════════════════════════════════════════════════════════════════════
# 🔍 搜索 Tab — Phase 2.2 日期过滤 + Phase 2.3 语义检索
# ═══════════════════════════════════════════════════════════════════════════════

def _render_search_results(sessions_scores: list[tuple], state_key: str) -> None:
    """渲染搜索结果卡片列表，score 为 None 时不显示相似度。"""
    all_db  = load_db()
    db_map  = {s["session_id"]: s for s in all_db}

    rows = []
    for sid, score in sessions_scores:
        session = db_map.get(sid)
        if session:
            rows.append((session, score))

    if not rows:
        st.info("没有找到匹配的记录。")
        return

    for row_start in range(0, len(rows), COLS):
        cols = st.columns(COLS)
        for col, (session, score) in zip(cols, rows[row_start: row_start + COLS]):
            _render_card(col, session, state_key, score=score)

    sel = st.session_state.get(state_key)
    if sel:
        target = db_map.get(sel)
        if target:
            st.divider()
            _render_detail(target, "final", state_key=state_key)


def _render_date_filter() -> None:
    """Phase 2.2：日期范围过滤检索。结果持久化到 session_state，rerun 后仍可展示详情。"""
    c1, c2 = st.columns(2)
    with c1:
        start = st.date_input("开始日期", value=None, key="filter_start")
    with c2:
        end = st.date_input("结束日期", value=None, key="filter_end")

    bc1, bc2 = st.columns([1, 5])
    with bc1:
        do_search = st.button("🔍 查询", type="primary", key="date_filter_btn")
    with bc2:
        if st.button("清除结果", key="date_filter_clear"):
            st.session_state["date_filter_exact"] = None
            st.session_state["date_filter_fuzzy"] = None
            st.session_state["search_selected"]   = None
            st.rerun()

    if do_search:
        if not start or not end:
            st.warning("请选择开始和结束日期")
        elif start > end:
            st.error("开始日期不能晚于结束日期")
        else:
            start_num = int(start.strftime("%Y%m%d"))
            end_num   = int(end.strftime("%Y%m%d"))
            try:
                col   = _get_collection()
                total = col.count()
                if total == 0:
                    st.info("向量库暂无数据，请先归档一些记录。")
                else:
                    exact = col.get(
                        where={"$and": [
                            {"has_exact_date":   {"$eq": True}},
                            {"content_time_num": {"$gte": start_num}},
                            {"content_time_num": {"$lte": end_num}},
                        ]},
                        include=["metadatas"],
                    )
                    fuzzy = col.get(
                        where={"has_exact_date": {"$eq": False}},
                        include=["metadatas"],
                    )
                    st.session_state["date_filter_exact"] = list(
                        zip(exact["ids"], exact["metadatas"])
                    )
                    st.session_state["date_filter_fuzzy"] = fuzzy["ids"]
                    st.session_state["date_filter_range"] = (
                        start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")
                    )
                    st.session_state["search_selected"] = None
            except Exception as e:
                st.error(f"查询失败：{e}")

    # ── 渲染持久化的结果（卡片 rerun 后仍存在）──────────────────────────
    exact_data = st.session_state.get("date_filter_exact")
    if exact_data is None:
        return

    fuzzy_ids          = st.session_state.get("date_filter_fuzzy") or []
    start_str, end_str = st.session_state.get("date_filter_range", ("", ""))

    st.divider()
    st.markdown(f"### 📅 精确日期匹配（{len(exact_data)} 条）")
    if exact_data:
        sorted_data = sorted(exact_data,
                             key=lambda x: x[1].get("content_time_num", 0),
                             reverse=True)
        _render_search_results(
            [(sid, None) for sid, _ in sorted_data], "search_selected"
        )
    else:
        st.caption(f"该日期范围（{start_str} 至 {end_str}）内无精确日期记录")

    if fuzzy_ids:
        st.divider()
        with st.expander(f"⚠️ 以下 {len(fuzzy_ids)} 条记录使用了模糊时间描述，无法按日期过滤"):
            _render_search_results(
                [(sid, None) for sid in fuzzy_ids], "search_selected"
            )


def _render_semantic_search() -> None:
    """Phase 2.3：自然语言语义检索。结果持久化到 session_state，rerun 后仍可展示详情。"""
    query = st.text_input(
        "描述你想找的内容",
        placeholder="例如：和朋友一起看日落的那次旅行……",
        key="semantic_query",
    )
    top_k = st.slider("最多返回结果数", min_value=1, max_value=10, value=5,
                      key="semantic_topk")

    bc1, bc2 = st.columns([1, 5])
    with bc1:
        do_search = st.button("🔍 检索", type="primary", key="semantic_btn")
    with bc2:
        if st.button("清除结果", key="semantic_clear"):
            st.session_state["semantic_results"]    = None
            st.session_state["semantic_query_used"] = ""
            st.session_state["search_selected"]     = None
            st.rerun()

    if do_search:
        if not query.strip():
            st.warning("请输入检索内容")
        else:
            try:
                col   = _get_collection()
                total = col.count()
                if total == 0:
                    st.info("向量库暂无数据，请先归档一些记录。")
                else:
                    with st.spinner("检索中…"):
                        query_text = "为这个句子生成表示以用于检索相关文章：" + query.strip()
                        embedding  = _get_embedder().encode(
                            query_text, normalize_embeddings=True
                        ).tolist()
                        results = col.query(
                            query_embeddings=[embedding],
                            n_results=min(top_k, total),
                            include=["metadatas", "distances"],
                        )
                    pairs = [
                        (sid, 1 - dist)
                        for sid, dist in zip(results["ids"][0], results["distances"][0])
                    ]
                    st.session_state["semantic_results"]    = pairs
                    st.session_state["semantic_query_used"] = query.strip()
                    st.session_state["search_selected"]     = None
            except Exception as e:
                st.error(f"检索失败：{e}")

    # ── 渲染持久化的结果（卡片 rerun 后仍存在）──────────────────────────
    pairs = st.session_state.get("semantic_results")
    if not pairs:
        return

    st.divider()
    q = st.session_state.get("semantic_query_used", "")
    st.markdown(f"### 🎯 语义检索结果（{len(pairs)} 条）")
    if q:
        st.caption(f"检索词：{q}")
    _render_search_results(pairs, "search_selected")


def render_search_tab() -> None:
    mode = st.radio(
        "检索模式",
        ["📅 日期过滤", "🔍 语义检索", "💬 智能问答（即将上线）"],
        horizontal=True,
        key="search_mode",
    )

    # 切换模式时清空上一个模式的结果和选中状态
    prev = st.session_state.get("_search_mode_prev")
    if prev != mode:
        st.session_state["semantic_results"]  = None
        st.session_state["date_filter_exact"] = None
        st.session_state["date_filter_fuzzy"] = None
        st.session_state["search_selected"]   = None
        st.session_state["_search_mode_prev"] = mode

    if mode == "💬 智能问答（即将上线）":
        st.info("智能问答功能正在开发中（Phase 2.4），敬请期待。")
        return

    st.divider()

    if mode == "📅 日期过滤":
        _render_date_filter()
    else:
        _render_semantic_search()


# ═══════════════════════════════════════════════════════════════════════════════
# 入口
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    st.set_page_config(page_title="灵感记录工具", page_icon="🗂️", layout="wide")
    ensure_dirs()
    init_state()
    _ensure_indexed()

    st.title("🗂️ 灵感记录工具")
    tab1, tab2, tab3, tab4 = st.tabs([
        "🗂️ 记录舱（上传）",
        "🖼️ 灵感墙（待处理）",
        "📚 已归档",
        "🔍 搜索",
    ])

    with tab1:
        render_upload_tab()
    with tab2:
        render_gallery_tab()
    with tab3:
        render_archived_tab()
    with tab4:
        render_search_tab()


if __name__ == "__main__":
    main()
