# -*- coding: utf-8 -*-
"""
빨간우체통 (RedMailbox) — LAN 메모/파일 전송 트레이 앱.

진입점:
    python redmailbox.py
또는 PyInstaller 빌드 .exe.

스레드 모델:
    [메인 스레드]      tk.Tk() hidden root → mainloop()
    [pystray 스레드]   icon.run_detached()
    [HTTP 서버 스레드] ThreadingHTTPServer (daemon)
    [깜빡임 스레드]    Blinker (daemon)

메뉴 콜백 → root.after(0, fn) 으로 GUI 작업을 메인 스레드에 위임.
"""
import logging
import os
import sys

# ─ CP949 hostname 패치를 다른 import보다 먼저 ─────────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from core import encoding_patch  # noqa: E402
encoding_patch.apply()
# ──────────────────────────────────────────────────────────────────────────

import tkinter as tk  # noqa: E402

from core import paths, settings  # noqa: E402
from server import http_server  # noqa: E402
from tray.tray_app import TrayApp  # noqa: E402
from ui import memo_dialog, file_dialog, inbox_window, settings_dialog  # noqa: E402


def _setup_logging():
    level = logging.DEBUG if os.environ.get("REDMAIL_DEBUG") else logging.INFO
    handlers = [logging.FileHandler(paths.log_path(), encoding="utf-8")]
    if os.environ.get("REDMAIL_DEBUG"):
        handlers.append(logging.StreamHandler())
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=handlers,
    )


_log = logging.getLogger("redmailbox")


def main():
    _setup_logging()
    _log.info("빨간우체통 시작")

    s = settings.load()

    # 1) 메인 스레드: hidden Tk root
    root = tk.Tk()
    root.withdraw()
    root.title("빨간우체통")

    # 2) Tray app — 메뉴 콜백은 root.after()로 GUI 스레드 위임
    tray: "TrayApp | None" = None

    def dispatch(key: str):
        """pystray 콜백 (별도 스레드) → 메인 GUI 스레드로 위임."""
        if key == "memo":
            root.after(0, lambda: memo_dialog.open_dialog(root))
        elif key == "file":
            root.after(0, lambda: file_dialog.open_dialog(root))
        elif key == "inbox":
            def _inbox():
                inbox_window.open_window(root)
                if tray:
                    tray.on_inbox_opened()
            root.after(0, _inbox)
        elif key == "settings":
            def _settings():
                settings_dialog.open_dialog(
                    root,
                    on_changed=lambda: tray and tray.refresh_after_settings_change(),
                )
            root.after(0, _settings)
        elif key == "quit":
            root.after(0, _quit)

    def _quit():
        try:
            if tray:
                tray.stop()
        finally:
            try:
                handle.shutdown()
            except Exception:
                pass
            root.quit()

    tray = TrayApp(on_menu=dispatch)

    # 3) HTTP 서버: 수신 시 트레이 깜빡임
    def on_received(kind: str):
        if tray:
            tray.on_received(kind)
            # 메뉴 갱신 (미확인 카운트 변경)
            root.after(0, lambda: None)

    handle = http_server.start(port=s.port, on_received=on_received,
                                host="0.0.0.0")

    # 4) 트레이 시작
    tray.start()

    # 5) 메인 루프
    try:
        root.mainloop()
    finally:
        try:
            handle.shutdown()
        except Exception:
            pass
        try:
            tray.stop()
        except Exception:
            pass
        _log.info("빨간우체통 종료")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        # PyInstaller --windowed에서는 print 사라짐 → 로그 파일만 남음
        try:
            logging.getLogger("redmailbox").exception("치명적 오류로 종료")
        except Exception:
            pass
        traceback.print_exc()
        sys.exit(1)
