"""全局常量、路径、文件格式、FIELD_SCHEMA。

扩展字段只需修改 FIELD_SCHEMA，UI / 校验 / .md 生成自动跟随。
"""
from __future__ import annotations

from pathlib import Path

# ─── 路径 ──────────────────────────────────────────────────────────────────────
DATA_DIR      = Path("data")
FINAL_DIR     = DATA_DIR / "final"
PENDING_DIR   = DATA_DIR / "pending"
DB_PATH       = DATA_DIR / "database.db"
VECTOR_DB_DIR = Path(__file__).parent.parent / "vector_db"

# ─── 文件格式 ──────────────────────────────────────────────────────────────────
TEXT_EXTS  = {".txt", ".md"}
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}

VIDEO_EXTS = {
    ".mp4", ".mov", ".avi", ".mkv", ".wmv", ".webm",
    ".flv", ".m4v", ".3gp", ".ts", ".mts", ".mpg", ".mpeg",
}
VIDEO_EXTS_PLAYABLE = {".mp4", ".webm", ".mov", ".m4v", ".ogg"}

SUPPORTED_IMPORT_EXTS = IMAGE_EXTS | VIDEO_EXTS | TEXT_EXTS

# ─── UI ───────────────────────────────────────────────────────────────────────
COLS = 3

# ─── 标签默认值 ────────────────────────────────────────────────────────────────
DEFAULT_TAGS: list[str] = ["个人规划", "生活感悟", "重要记忆", "工作总结", "随笔"]
DOMAINS: list[str] = ["个人成长", "情绪感受", "工作经验", "人际关系", "兴趣爱好", "财务理财"]
ATTRIBUTES: list[str] = ["反思避坑", "灵光一现", "阶段里程碑", "干货总结", "疑问困惑", "日常流水"]
EMOTIONS: list[str] = ["喜悦", "平静", "充实", "期待", "疲惫", "焦虑", "愤怒", "失落", "迷茫"]
TOPICS: list[str] = []

# ─── 字段定义 — 扩展接口 ────────────────────────────────────────────────────────
# 增删字段只改此列表；type 可选：textarea | text | date_or_text
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
    {
        "key":         "title",
        "label":       "标题",
        "required":    True,
        "type":        "text",
        "placeholder": "为这条记录取个名字",
        "help":        "必填",
    },
]

REQUIRED_KEYS: list[str] = [f["key"] for f in FIELD_SCHEMA if f["required"]]
