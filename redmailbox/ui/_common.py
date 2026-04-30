# -*- coding: utf-8 -*-
"""UI 공용 헬퍼."""
import re
import tkinter as tk
from tkinter import ttk
from typing import Tuple

from core import settings


_IP_PORT_RE = re.compile(
    r"^(\d{1,3}(?:\.\d{1,3}){3})(?::(\d{1,5}))?$"
)


def parse_ip_port(text: str, default_port: int) -> Tuple[str, int]:
    """
    '192.168.0.42' 또는 '192.168.0.42:8765' 파싱.
    잘못된 형식이면 ValueError.
    """
    text = (text or "").strip()
    m = _IP_PORT_RE.match(text)
    if not m:
        raise ValueError("IP 형식이 올바르지 않습니다. 예: 192.168.0.42 또는 192.168.0.42:8765")
    ip = m.group(1)
    octets = ip.split(".")
    if any(int(o) > 255 for o in octets):
        raise ValueError(f"잘못된 IP 주소: {ip}")
    port = int(m.group(2)) if m.group(2) else default_port
    if not (1 <= port <= 65535):
        raise ValueError(f"잘못된 포트: {port}")
    return ip, port


def make_ip_combobox(parent, default_port: int) -> ttk.Combobox:
    """최근 IP 드롭다운이 채워진 Combobox 생성."""
    s = settings.load()
    cb = ttk.Combobox(parent, values=list(s.recent_ips), width=30)
    if s.recent_ips:
        cb.set(s.recent_ips[0])
    return cb


def center_on_screen(win: tk.Toplevel, width: int, height: int):
    win.update_idletasks()
    sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
    x = (sw - width) // 2
    y = (sh - height) // 2
    win.geometry(f"{width}x{height}+{x}+{y}")


def format_size(n: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    f = float(n)
    i = 0
    while f >= 1024 and i < len(units) - 1:
        f /= 1024
        i += 1
    return f"{f:.1f} {units[i]}" if i > 0 else f"{int(f)} B"
