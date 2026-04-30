# -*- coding: utf-8 -*-
"""
트레이 아이콘 깜빡임 — pystray.Icon.icon 속성을 idle/alert 이미지로 토글.

검증된 패턴 (pystray issue #30, #68):
    icon.icon = new_image  # 런타임 교체 가능

사용:
    blinker = Blinker(icon, idle_img, alert_img)
    blinker.start()  # 수신 시 호출 — 기존 깜빡임 중이면 타이머 연장
    blinker.stop()   # 사용자가 받은 목록 열면 호출
"""
import logging
import threading
import time


_log = logging.getLogger("redmailbox.blinker")


class Blinker:
    def __init__(self, icon, idle_img, alert_img,
                 period: float = 0.5, duration: float = 10.0):
        self._icon = icon
        self._idle = idle_img
        self._alert = alert_img
        self._period = period
        self._duration = duration
        self._stop_evt = threading.Event()
        self._thread: "threading.Thread | None" = None
        self._lock = threading.Lock()

    def start(self):
        with self._lock:
            # 이미 깜빡이는 중이면 기존 스레드 종료 후 재시작 (타이머 연장)
            if self._thread and self._thread.is_alive():
                self._stop_evt.set()
                self._thread.join(timeout=1.0)
            self._stop_evt = threading.Event()
            self._thread = threading.Thread(
                target=self._loop, name="redmailbox-blink", daemon=True)
            self._thread.start()

    def stop(self):
        with self._lock:
            self._stop_evt.set()
        # 항상 idle 상태로 복귀
        self._set_icon(self._idle)

    def _set_icon(self, img):
        try:
            self._icon.icon = img
        except Exception:
            _log.exception("아이콘 교체 실패")

    def _loop(self):
        end = time.time() + self._duration
        on = False
        while not self._stop_evt.is_set() and time.time() < end:
            on = not on
            self._set_icon(self._alert if on else self._idle)
            self._stop_evt.wait(self._period)
        # 종료 시 항상 idle 강제 (race 방지)
        self._set_icon(self._idle)
