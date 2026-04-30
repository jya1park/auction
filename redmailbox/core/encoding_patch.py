# -*- coding: utf-8 -*-
"""
한국어 Windows의 CP949 hostname이 UTF-8 디코딩 시 발생시키는
UnicodeDecodeError를 회피하기 위한 패치.

- HTTPServer.server_bind() 내부에서 socket.getfqdn() 호출
- 한국어 Windows는 호스트명을 CP949로 반환하므로 디코딩 실패
- 안전 래퍼로 감싸서 실패 시 'localhost' 반환

(open_map.py:14-24 패턴과 동일)
"""
import socket


_applied = False


def apply():
    global _applied
    if _applied:
        return
    _orig_getfqdn = socket.getfqdn

    def _safe_getfqdn(name=""):
        try:
            return _orig_getfqdn(name)
        except (UnicodeDecodeError, UnicodeEncodeError):
            return "localhost"

    socket.getfqdn = _safe_getfqdn
    _applied = True
