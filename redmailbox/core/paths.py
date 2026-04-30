# -*- coding: utf-8 -*-
"""경로 헬퍼: dev / PyInstaller --onefile 양쪽에서 동일 동작."""
import os
import sys


def resource_path(rel_path: str) -> str:
    """
    PyInstaller --onefile 빌드에서는 sys._MEIPASS,
    dev 환경에서는 redmailbox/ 패키지 루트 기준으로 해결.
    """
    base = getattr(sys, "_MEIPASS", None)
    if base is None:
        # redmailbox/core/paths.py → redmailbox/
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel_path)


def app_data_dir() -> str:
    """%LOCALAPPDATA%/RedMailbox/ (Windows) 또는 ~/.local/share/RedMailbox (기타)."""
    root = os.environ.get("LOCALAPPDATA")
    if not root:
        root = os.path.join(os.path.expanduser("~"), ".local", "share")
    p = os.path.join(root, "RedMailbox")
    os.makedirs(p, exist_ok=True)
    return p


def default_download_dir() -> str:
    """기본 저장 폴더: ~/Downloads/RedMailbox/."""
    p = os.path.join(os.path.expanduser("~"), "Downloads", "RedMailbox")
    return p


def log_path() -> str:
    return os.path.join(app_data_dir(), "redmailbox.log")
