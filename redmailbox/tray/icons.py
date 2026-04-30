# -*- coding: utf-8 -*-
"""
트레이 아이콘 이미지 로더.

assets/mailbox_idle.png, mailbox_alert.png가 있으면 그 파일 사용.
없으면 PIL로 즉석 생성 (빨간 우체통 + 깃발 토글) — dev 환경 첫 실행 시 폴백.
"""
import os

from PIL import Image, ImageDraw

from core import paths


_IDLE_NAME = "assets/mailbox_idle.png"
_ALERT_NAME = "assets/mailbox_alert.png"
_SIZE = 64


def _draw_mailbox(flag_up: bool) -> Image.Image:
    """64x64 빨간 우체통 — flag_up=True면 깃발 올라감(수신 알림)."""
    img = Image.new("RGBA", (_SIZE, _SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    red = (220, 30, 30, 255)
    dark = (140, 20, 20, 255)
    yellow = (255, 200, 0, 255)
    white = (250, 250, 250, 255)

    # 본체 (둥근 위 + 사각 아래)
    d.pieslice([8, 8, 56, 40], 180, 360, fill=red, outline=dark, width=2)
    d.rectangle([8, 24, 56, 56], fill=red, outline=dark, width=2)
    # 투입구
    d.rectangle([18, 22, 46, 28], fill=dark)
    # 다리
    d.rectangle([14, 56, 18, 62], fill=dark)
    d.rectangle([46, 56, 50, 62], fill=dark)
    # 깃발 (alert일 때만 위로)
    if flag_up:
        d.rectangle([54, 16, 56, 36], fill=dark)  # 깃대
        d.polygon([(56, 16), (62, 20), (56, 24)], fill=yellow)  # 깃발
    else:
        d.rectangle([54, 30, 56, 50], fill=dark)
        d.polygon([(56, 32), (62, 36), (56, 40)], fill=yellow)
    # 글자 'M'
    try:
        d.text((26, 32), "M", fill=white)
    except Exception:
        pass
    return img


def _load_or_create(rel_path: str, fallback_flag_up: bool) -> Image.Image:
    p = paths.resource_path(rel_path)
    if os.path.exists(p):
        try:
            return Image.open(p).convert("RGBA")
        except Exception:
            pass
    return _draw_mailbox(flag_up=fallback_flag_up)


def load_idle() -> Image.Image:
    return _load_or_create(_IDLE_NAME, fallback_flag_up=False)


def load_alert() -> Image.Image:
    return _load_or_create(_ALERT_NAME, fallback_flag_up=True)
