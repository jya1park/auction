# -*- coding: utf-8 -*-
"""
assets/ 폴더에 트레이 아이콘 PNG와 .exe 아이콘 ICO를 생성.

빌드 전에 한 번 실행하면 됨. tray.icons.py의 폴백 그림과 동일한 빨간 우체통.

실행:
    cd redmailbox && python generate_assets.py
"""
import os
import sys


ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from tray.icons import _draw_mailbox  # noqa: E402


def main():
    out = os.path.join(ROOT, "assets")
    os.makedirs(out, exist_ok=True)

    idle = _draw_mailbox(flag_up=False)
    alert = _draw_mailbox(flag_up=True)

    idle_path = os.path.join(out, "mailbox_idle.png")
    alert_path = os.path.join(out, "mailbox_alert.png")
    ico_path = os.path.join(out, "mailbox.ico")

    idle.save(idle_path, "PNG")
    alert.save(alert_path, "PNG")
    # .exe 아이콘용 ICO (여러 사이즈 포함)
    idle.save(ico_path, "ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])

    print(f"생성: {idle_path}")
    print(f"생성: {alert_path}")
    print(f"생성: {ico_path}")


if __name__ == "__main__":
    main()
