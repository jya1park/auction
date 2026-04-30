# -*- coding: utf-8 -*-
"""
백그라운드 서버 + 클라이언트 라운드트립 테스트.

실행:
    cd redmailbox && python -m pytest tests/ -v
또는 직접:
    cd redmailbox && python tests/test_roundtrip.py
"""
import os
import sys
import time
import tempfile
import threading
import unittest


# redmailbox/ 를 sys.path에 추가
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from core import encoding_patch  # noqa: E402
encoding_patch.apply()

from core import paths, settings, history  # noqa: E402
from server import http_server  # noqa: E402
from client import sender  # noqa: E402


_PORT = 18765


class RoundtripTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 격리된 임시 디렉터리에 settings/history 보관
        cls.tmpdir = tempfile.mkdtemp(prefix="redmailbox_test_")
        os.environ["LOCALAPPDATA"] = cls.tmpdir
        os.environ["REDMAIL_SAVE"] = os.path.join(cls.tmpdir, "inbox")
        # 캐시 리셋
        settings._cache = None
        history._conn = None
        # 수신 이벤트 카운터
        cls.events = []
        cls.event_lock = threading.Lock()

        def on_received(kind):
            with cls.event_lock:
                cls.events.append(kind)

        cls.handle = http_server.start(_PORT, on_received=on_received,
                                        host="127.0.0.1")
        time.sleep(0.3)  # 서버 부팅 대기

    @classmethod
    def tearDownClass(cls):
        cls.handle.shutdown()

    def test_01_ping(self):
        self.assertTrue(sender.ping("127.0.0.1", _PORT, timeout=2))

    def test_02_ping_fail(self):
        # 다른 포트는 실패해야 함
        self.assertFalse(sender.ping("127.0.0.1", _PORT + 1, timeout=1))

    def test_03_memo_korean(self):
        before = len(self.events)
        r = sender.send_memo("127.0.0.1", _PORT, "안녕하세요 — 한글 메모 ✉️")
        self.assertTrue(r["ok"])
        # 이벤트 트리거 확인
        time.sleep(0.1)
        self.assertGreater(len(self.events), before)
        self.assertEqual(self.events[-1], "memo")
        # DB 기록 확인
        items = history.list_recent(5)
        memos = [i for i in items if i.kind == "memo"]
        self.assertTrue(any("한글 메모" in (m.body or "") for m in memos))

    def test_04_file_korean_name(self):
        # 한글 파일명 + 1MB 더미
        with tempfile.NamedTemporaryFile(
                prefix="테스트_", suffix=".bin", delete=False) as f:
            f.write(os.urandom(1024 * 1024))
            src = f.name
        try:
            progress = []

            def cb(read, total):
                progress.append((read, total))

            r = sender.send_file("127.0.0.1", _PORT, src, on_progress=cb)
            self.assertTrue(r["ok"])
            self.assertIn(".bin", r["saved"])
            # 진행률이 한 번 이상 콜백되어야 함
            self.assertTrue(progress)
            self.assertEqual(progress[-1][0], progress[-1][1])
            # 파일이 inbox에 저장됐는지
            saved = os.path.join(settings.load().save_dir, r["saved"])
            self.assertTrue(os.path.exists(saved))
            self.assertEqual(os.path.getsize(saved), 1024 * 1024)
        finally:
            os.unlink(src)

    def test_05_file_collision_numbering(self):
        with tempfile.NamedTemporaryFile(
                prefix="dup_", suffix=".txt", delete=False) as f:
            f.write(b"hello")
            src = f.name
        try:
            r1 = sender.send_file("127.0.0.1", _PORT, src)
            r2 = sender.send_file("127.0.0.1", _PORT, src)
            self.assertNotEqual(r1["saved"], r2["saved"])
            # r2는 ' (1)' 패턴을 포함해야 함
            self.assertIn("(1)", r2["saved"])
        finally:
            os.unlink(src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
