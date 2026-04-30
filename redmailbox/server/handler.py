# -*- coding: utf-8 -*-
"""
HTTP 핸들러: /ping, /memo, /file

설계:
- multipart 회피 → /file은 raw stream + X-Filename 헤더 (URL-encoded UTF-8)
- 청크 스트림 (64KB)으로 대용량 파일 OOM 방지
- handler.server.on_received(kind) 콜백으로 트레이 깜빡임 트리거
"""
import json
import logging
import urllib.parse
from http.server import BaseHTTPRequestHandler

from core import history
from server import storage


_CHUNK = 64 * 1024
_log = logging.getLogger("redmailbox.handler")


class RedMailHandler(BaseHTTPRequestHandler):
    server_version = "RedMailbox/1.0"

    # CP949 역DNS 회피 — 그냥 IP만 표시
    def address_string(self):
        return self.client_address[0]

    def log_message(self, fmt, *args):
        _log.info("%s - %s", self.address_string(), fmt % args)

    # ── helpers ──────────────────────────────────────────────────────────
    def _read_exact(self, n: int):
        remaining = n
        while remaining > 0:
            buf = self.rfile.read(min(_CHUNK, remaining))
            if not buf:
                break
            remaining -= len(buf)
            yield buf

    def _json(self, status: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _trigger(self, kind: str):
        cb = getattr(self.server, "on_received", None)
        if callable(cb):
            try:
                cb(kind)
            except Exception:
                _log.exception("on_received 콜백 실패")

    # ── routes ───────────────────────────────────────────────────────────
    def do_GET(self):
        if self.path == "/ping":
            self._json(200, {"ok": True, "service": "redmailbox"})
            return
        self.send_error(404)

    def do_POST(self):
        try:
            if self.path == "/memo":
                self._handle_memo()
            elif self.path.startswith("/file"):
                self._handle_file()
            else:
                self.send_error(404)
        except Exception as e:
            _log.exception("요청 처리 실패")
            try:
                self._json(500, {"ok": False, "error": str(e)})
            except Exception:
                pass

    def _handle_memo(self):
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 1024 * 1024:  # 메모는 1MB 이내
            self._json(400, {"ok": False, "error": "invalid memo size"})
            return
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self._json(400, {"ok": False, "error": "invalid json"})
            return
        text = (data.get("text") or "").strip()
        if not text:
            self._json(400, {"ok": False, "error": "empty memo"})
            return
        history.add_memo(sender_ip=self.client_address[0], text=text)
        self._trigger("memo")
        self._json(200, {"ok": True})

    def _handle_file(self):
        raw_name = self.headers.get("X-Filename", "")
        if not raw_name:
            self._json(400, {"ok": False, "error": "missing X-Filename"})
            return
        try:
            filename = urllib.parse.unquote(raw_name, encoding="utf-8")
        except Exception:
            filename = raw_name
        length_hdr = self.headers.get("Content-Length")
        if length_hdr is None:
            self._json(411, {"ok": False, "error": "Content-Length required"})
            return
        total = int(length_hdr)
        if total <= 0:
            self._json(400, {"ok": False, "error": "empty file"})
            return
        saved_path = storage.save_stream(
            filename=filename,
            chunks=self._read_exact(total),
        )
        import os
        history.add_file(
            sender_ip=self.client_address[0],
            filename=os.path.basename(saved_path),
            path=saved_path,
            size=total,
        )
        self._trigger("file")
        self._json(200, {"ok": True, "saved": os.path.basename(saved_path)})
