# -*- coding: utf-8 -*-
"""urllib 기반 메모/파일 송신. 진행률 콜백 지원."""
import json
import os
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Callable, Optional


_DEFAULT_TIMEOUT = 5
_FILE_TIMEOUT = 600  # 10분 — 대용량 파일 전송용


class SendError(Exception):
    pass


def _url(ip: str, port: int, path: str) -> str:
    return f"http://{ip}:{port}{path}"


def ping(ip: str, port: int, timeout: int = _DEFAULT_TIMEOUT) -> bool:
    """수신측이 살아있는지 헬스체크. False면 빠른 실패."""
    try:
        with urllib.request.urlopen(_url(ip, port, "/ping"),
                                     timeout=timeout) as r:
            data = json.loads(r.read().decode("utf-8"))
            return bool(data.get("ok"))
    except (urllib.error.URLError, socket.timeout, ConnectionError,
            json.JSONDecodeError, OSError):
        return False


def send_memo(ip: str, port: int, text: str,
              timeout: int = _DEFAULT_TIMEOUT) -> dict:
    payload = json.dumps({"text": text}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        _url(ip, port, "/memo"),
        data=payload,
        method="POST",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Content-Length": str(len(payload)),
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise SendError(f"서버 오류 {e.code}: {e.read().decode('utf-8', 'replace')}")
    except (urllib.error.URLError, socket.timeout, ConnectionError, OSError) as e:
        raise SendError(f"연결 실패: {e}")


class _ProgressReader:
    """urllib에 file-like로 넘겨주면서 read마다 진행률 콜백."""
    def __init__(self, fp, total: int,
                 on_progress: Optional[Callable[[int, int], None]],
                 chunk: int = 1024 * 1024):
        self.fp = fp
        self.total = total
        self.read_bytes = 0
        self.chunk = chunk
        self.on_progress = on_progress

    def read(self, n: int = -1) -> bytes:
        size = self.chunk if n < 0 else min(n, self.chunk)
        buf = self.fp.read(size)
        if buf:
            self.read_bytes += len(buf)
            if self.on_progress:
                try:
                    self.on_progress(self.read_bytes, self.total)
                except Exception:
                    pass
        return buf


def send_file(ip: str, port: int, path: str,
              on_progress: Optional[Callable[[int, int], None]] = None,
              timeout: int = _FILE_TIMEOUT) -> dict:
    """대용량 파일을 청크 스트림으로 전송. 한글 파일명은 X-Filename에 URL-encode."""
    if not os.path.isfile(path):
        raise SendError(f"파일이 존재하지 않음: {path}")
    size = os.path.getsize(path)
    if size <= 0:
        raise SendError("빈 파일은 전송할 수 없습니다.")
    name_enc = urllib.parse.quote(os.path.basename(path), safe="")

    with open(path, "rb") as fp:
        reader = _ProgressReader(fp, size, on_progress)
        req = urllib.request.Request(
            _url(ip, port, "/file"),
            data=reader,
            method="POST",
            headers={
                "Content-Type": "application/octet-stream",
                "Content-Length": str(size),
                "X-Filename": name_enc,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raise SendError(f"서버 오류 {e.code}: "
                            f"{e.read().decode('utf-8', 'replace')}")
        except (urllib.error.URLError, socket.timeout,
                ConnectionError, OSError) as e:
            raise SendError(f"전송 실패: {e}")
