# -*- coding: utf-8 -*-
"""
빨간우체통 트레이 앱.

pystray.Icon은 run_detached()로 별도 스레드에서 실행하고,
tkinter mainloop는 메인 스레드에서 실행한다.
메뉴 콜백에서는 root.after(0, ...)로 GUI 작업을 메인 스레드에 위임.
"""
import logging
import socket
import threading

import pystray

from core import history, settings
from tray import icons
from tray.blinker import Blinker


_log = logging.getLogger("redmailbox.tray")


def _get_local_ip() -> str:
    """기본 라우트로 나가는 인터페이스의 LAN IP를 추정.
    실패 시 'localhost'."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # 실제로 연결되지는 않지만 라우팅 테이블 기반으로 IP 결정됨
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return "localhost"
    finally:
        s.close()


class TrayApp:
    """
    Args:
        on_menu: 메뉴 콜백 dispatcher.
                 키('memo'/'file'/'inbox'/'settings'/'quit')를
                 받아 메인 GUI 스레드에서 처리해야 함.
    """
    def __init__(self, on_menu):
        self._on_menu = on_menu
        self._idle = icons.load_idle()
        self._alert = icons.load_alert()
        self._icon: "pystray.Icon | None" = None
        self._blinker: "Blinker | None" = None
        self._local_ip = _get_local_ip()
        self._lock = threading.Lock()

    # ── 라이프사이클 ─────────────────────────────────────────────────────
    def start(self):
        self._icon = pystray.Icon(
            "redmailbox",
            icon=self._idle,
            title=self._title(),
            menu=self._build_menu(),
        )
        self._blinker = Blinker(self._icon, self._idle, self._alert)
        # 좌클릭 = 받은 목록 (pystray default_action)
        self._icon.run_detached()

    def stop(self):
        if self._icon:
            try:
                self._icon.stop()
            except Exception:
                _log.exception("아이콘 정지 실패")

    # ── 외부 트리거 ──────────────────────────────────────────────────────
    def on_received(self, kind: str):
        """HTTP 핸들러가 호출. 깜빡임 시작 + 메뉴/툴팁 갱신."""
        _log.info("수신: kind=%s", kind)
        if self._blinker:
            self._blinker.start()
        self._refresh()

    def on_inbox_opened(self):
        """사용자가 받은목록 창을 열었을 때."""
        if self._blinker:
            self._blinker.stop()
        history.mark_all_read()
        self._refresh()

    def refresh_after_settings_change(self):
        self._local_ip = _get_local_ip()
        self._refresh()

    # ── 내부 ─────────────────────────────────────────────────────────────
    def _title(self) -> str:
        s = settings.load()
        unread = history.unread_count()
        suffix = f" (새 항목 {unread})" if unread > 0 else ""
        return f"빨간우체통 — 내 IP: {self._local_ip}:{s.port}{suffix}"

    def _refresh(self):
        if not self._icon:
            return
        try:
            self._icon.title = self._title()
            self._icon.menu = self._build_menu()
            self._icon.update_menu()
        except Exception:
            _log.exception("트레이 갱신 실패")

    def _build_menu(self):
        s = settings.load()
        unread = history.unread_count()
        inbox_label = f"받은 목록 ({unread})" if unread > 0 else "받은 목록"
        return pystray.Menu(
            pystray.MenuItem(
                f"내 IP: {self._local_ip}:{s.port}",
                None, enabled=False,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("메모 보내기", self._wrap("memo")),
            pystray.MenuItem("대용량 파일 보내기", self._wrap("file")),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                inbox_label, self._wrap("inbox"), default=True),
            pystray.MenuItem("설정", self._wrap("settings")),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("종료", self._wrap("quit")),
        )

    def _wrap(self, key: str):
        # pystray 콜백은 별도 스레드일 수 있으므로 dispatcher가 메인 위임
        def _cb(icon=None, item=None):
            try:
                self._on_menu(key)
            except Exception:
                _log.exception("메뉴 콜백 실패: %s", key)
        return _cb
