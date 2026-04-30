# -*- coding: utf-8 -*-
"""
설정 영속화: %LOCALAPPDATA%/RedMailbox/settings.json

저장 항목:
- save_dir: 받은 파일 저장 폴더 (기본 ~/Downloads/RedMailbox)
- port: HTTP 서버 포트 (기본 8765)
- recent_ips: 최근 송신 IP 목록 (최대 10개, 최신순)
- blink_seconds: 깜빡임 지속 시간 (기본 10초)

환경변수 오버라이드:
- REDMAIL_PORT, REDMAIL_SAVE
"""
import json
import os
import threading
from typing import List

from . import paths


_DEFAULT_PORT = 8765
_DEFAULT_BLINK = 10.0
_RECENT_MAX = 10


class Settings:
    def __init__(self, save_dir: str, port: int, recent_ips: List[str],
                 blink_seconds: float):
        self.save_dir = save_dir
        self.port = port
        self.recent_ips = recent_ips
        self.blink_seconds = blink_seconds

    def to_dict(self):
        return {
            "save_dir": self.save_dir,
            "port": self.port,
            "recent_ips": self.recent_ips,
            "blink_seconds": self.blink_seconds,
        }


_lock = threading.Lock()
_cache: "Settings | None" = None


def _config_file() -> str:
    return os.path.join(paths.app_data_dir(), "settings.json")


def _read_disk() -> dict:
    path = _config_file()
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        # 손상 시 빈 설정으로 재시작
        return {}


def _apply_env_overrides(d: dict) -> dict:
    env_port = os.environ.get("REDMAIL_PORT")
    if env_port and env_port.isdigit():
        d["port"] = int(env_port)
    env_save = os.environ.get("REDMAIL_SAVE")
    if env_save:
        d["save_dir"] = env_save
    return d


def load() -> Settings:
    global _cache
    with _lock:
        if _cache is not None:
            return _cache
        d = _read_disk()
        d = _apply_env_overrides(d)
        s = Settings(
            save_dir=d.get("save_dir") or paths.default_download_dir(),
            port=int(d.get("port", _DEFAULT_PORT)),
            recent_ips=list(d.get("recent_ips", [])),
            blink_seconds=float(d.get("blink_seconds", _DEFAULT_BLINK)),
        )
        os.makedirs(s.save_dir, exist_ok=True)
        _cache = s
        return s


def save() -> None:
    with _lock:
        if _cache is None:
            return
        path = _config_file()
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_cache.to_dict(), f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)


def add_recent_ip(ip_port: str) -> None:
    """ip_port 예: '192.168.0.42:8765' — 최신순 dedupe."""
    s = load()
    with _lock:
        if ip_port in s.recent_ips:
            s.recent_ips.remove(ip_port)
        s.recent_ips.insert(0, ip_port)
        del s.recent_ips[_RECENT_MAX:]
    save()


def set_save_dir(new_dir: str) -> None:
    s = load()
    os.makedirs(new_dir, exist_ok=True)
    with _lock:
        s.save_dir = new_dir
    save()


def set_port(new_port: int) -> None:
    s = load()
    with _lock:
        s.port = int(new_port)
    save()
