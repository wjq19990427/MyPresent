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
ASSETS_DIR  = Path("Assets")
FINAL_DIR   = ASSETS_DIR / "Final"
PENDING_DIR = ASSETS_DIR / "Pending"
DB_FILE     = Path("pending_db.json")
COLS        = 3
TEXT_EXTS   = {".txt", ".md"}


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
    FINAL_DIR.mkdir(parents=True, exist_ok=True)
    PENDING_DIR.mkdir(parents=True, exist_ok=True)


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
    entries = []
    for idx, (data, orig_name) in enumerate(file_data_list):
        filename = f"{session_id}_{idx:03d}_{orig_name}"
        dest     = dest_dir / filename
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


def move_to_final(session_id: str) -> None:
    db      = load_db()
    session = next((s for s in db if s["session_id"] == session_id), None)
    if not session:
        return
    for fe in session["files"]:
        src  = Path(fe["path"])
        dest = FINAL_DIR / fe["filename"]
        if src.exists():
            shutil.move(str(src), str(dest))
        fe["path"] = str(dest)
    session["status"]       = "final"
    session["archive_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    session["is_complete"]  = True
    save_db(db)
    _write_md(session)


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
                continue  # 文字记录的描述由内容自动填充，不追踪变更
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
    sid           = session["session_id"]
    comments      = [c for c in session.get("comments", []) if isinstance(c, dict)]
    input_key     = f"new_cmt_{sid}"

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
        "upload_key":        0,
        "pending_selected":  None,
        "archived_selected": None,
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
            "支持 jpg / png / mp4 / md / txt（可多选，本次上传构成一条记录）",
            type=["jpg", "jpeg", "png", "mp4", "md", "txt"],
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
        file_data = [(f.getvalue(), f.name) for f in files]
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
    if ext == ".mp4":
        thumb = video_thumbnail(fp)
        return pil_to_png_bytes(thumb) if thumb else None
    return None


def _completion_badge(session: dict) -> str:
    missing = validate_session(session)
    return "✅ 信息完整" if not missing else f"⚠️ 待补充：{'、'.join(missing)}"


def _render_card(col, session: dict, state_key: str) -> None:
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
        st.caption(f"🕐 {session.get('upload_time', '')}")
        st.caption(_completion_badge(session))

        label = "✅ 已选" if is_sel else "🔍 查看 / 编辑"
        if st.button(label, key=f"{state_key}_btn_{sid}", use_container_width=True):
            st.session_state[state_key] = None if is_sel else sid
            st.rerun()


def _render_detail(session: dict, mode: str) -> None:
    """共用详情 + 编辑表单，mode='pending'|'final'。"""
    sid       = session["session_id"]
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

    # 文件预览
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
            elif ext == ".mp4":
                st.video(fp.read_bytes())
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

    # 编辑历史（仅 Final）
    if mode == "final" and session.get("edit_history"):
        with st.expander(f"编辑历史（{len(session['edit_history'])} 次）"):
            for edit in reversed(session["edit_history"]):
                st.markdown(f"**{edit['edited_at']}**")
                for fk, change in edit["changes"].items():
                    lbl = next((f["label"] for f in FIELD_SCHEMA if f["key"] == fk), fk)
                    st.markdown(f"- **{lbl}**：「{change['from']}」→「{change['to']}」")
                st.divider()

    # 编辑表单
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

    # 评论区（form 外部，支持实时增删）
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
# 入口
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    st.set_page_config(page_title="灵感记录工具", page_icon="🗂️", layout="wide")
    ensure_dirs()
    init_state()

    st.title("🗂️ 灵感记录工具")
    tab1, tab2, tab3 = st.tabs(["🗂️ 记录舱（上传）", "🖼️ 灵感墙（待处理）", "📚 已归档"])

    with tab1:
        render_upload_tab()
    with tab2:
        render_gallery_tab()
    with tab3:
        render_archived_tab()


if __name__ == "__main__":
    main()
