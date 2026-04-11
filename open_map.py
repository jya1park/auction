"""
open_map.py — 경매 지도를 localhost:8080 서버로 서비스하고 브라우저를 엽니다.

실행:
    python open_map.py
"""
import os
import sys
import threading
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

import config
from storage.map_generator import generate_map

PORT       = 8080
OUTPUT_DIR = os.path.join(ROOT, config.OUTPUT_DIR)
HTML_FILE  = os.path.join(OUTPUT_DIR, "auction_map.html")
HTML_URL   = f"http://localhost:{PORT}/auction_map.html"


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # 콘솔 노이즈 억제


def main():
    if not os.path.exists(HTML_FILE):
        print("[open_map] auction_map.html 없음 → 지도 생성 중...")
        result = generate_map()
        if not result:
            print("[open_map] 지도 생성 실패. 종료합니다.")
            sys.exit(1)

    os.chdir(OUTPUT_DIR)
    server = HTTPServer(("", PORT), _QuietHandler)
    print(f"[open_map] 서버 시작: http://localhost:{PORT}/")
    print(f"[open_map] 지도:      {HTML_URL}")
    print("[open_map] 종료하려면 Ctrl+C 를 누르세요.")

    def _open():
        import time
        time.sleep(0.6)
        webbrowser.open(HTML_URL)

    threading.Thread(target=_open, daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[open_map] 서버 종료.")


if __name__ == "__main__":
    main()
