"""视频缩略图提取与图像格式转换。"""
from __future__ import annotations

import io
from pathlib import Path

import cv2
from PIL import Image, ImageDraw


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
