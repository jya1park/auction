# -*- coding: utf-8 -*-
"""ThreadingHTTPServer를 백그라운드 데몬 스레드로 부트스트랩."""
import logging
import threading
from http.server import ThreadingHTTPServer
from typing import Callable, Optional

from server.handler import RedMailHandler


_log = logging.getLogger("redmailbox.server")


class ServerHandle:
    def __init__(self, server: ThreadingHTTPServer, thread: threading.Thread):
        self.server = server
        self.thread = thread

    def shutdown(self):
        try:
            self.server.shutdown()
            self.server.server_close()
        finally:
            self.thread.join(timeout=2.0)


def start(port: int,
          on_received: Optional[Callable[[str], None]] = None,
          host: str = "0.0.0.0") -> ServerHandle:
    """
    on_received(kind: 'memo' | 'file') — 수신 시 트레이 깜빡임 트리거.
    """
    server = ThreadingHTTPServer((host, port), RedMailHandler)
    server.on_received = on_received  # type: ignore[attr-defined]
    thread = threading.Thread(
        target=server.serve_forever,
        name="redmailbox-http",
        daemon=True,
    )
    thread.start()
    _log.info("HTTP 서버 시작: %s:%d", host, port)
    return ServerHandle(server, thread)
