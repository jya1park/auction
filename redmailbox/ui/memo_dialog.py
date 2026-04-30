# -*- coding: utf-8 -*-
"""메모 보내기 다이얼로그."""
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext

from core import settings
from client import sender
from ui._common import parse_ip_port, make_ip_combobox, center_on_screen


def open_dialog(root: tk.Tk):
    s = settings.load()
    win = tk.Toplevel(root)
    win.title("메모 보내기 — 빨간우체통")
    center_on_screen(win, 480, 360)
    win.transient(root)

    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)

    ttk.Label(frm, text="받는 사람 (IP[:포트])").pack(anchor="w")
    ip_cb = make_ip_combobox(frm, default_port=s.port)
    ip_cb.pack(fill="x", pady=(2, 10))

    ttk.Label(frm, text="메모 내용").pack(anchor="w")
    txt = scrolledtext.ScrolledText(frm, height=10, wrap="word")
    txt.pack(fill="both", expand=True, pady=(2, 10))
    txt.focus_set()

    status = ttk.Label(frm, text="", foreground="gray")
    status.pack(anchor="w")

    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=(8, 0))

    send_btn = ttk.Button(btns, text="보내기")
    send_btn.pack(side="right")
    ttk.Button(btns, text="취소", command=win.destroy).pack(side="right", padx=6)

    def do_send():
        ip_text = ip_cb.get().strip()
        body = txt.get("1.0", "end").strip()
        if not body:
            messagebox.showwarning("빨간우체통", "메모 내용을 입력해주세요.", parent=win)
            return
        try:
            ip, port = parse_ip_port(ip_text, default_port=s.port)
        except ValueError as e:
            messagebox.showerror("빨간우체통", str(e), parent=win)
            return
        send_btn.config(state="disabled")
        status.config(text="전송 중...", foreground="gray")

        def worker():
            try:
                if not sender.ping(ip, port, timeout=3):
                    raise sender.SendError(
                        f"수신 측({ip}:{port})에 연결할 수 없습니다.\n"
                        f"상대방이 빨간우체통을 실행 중이고 같은 LAN에 있는지,\n"
                        f"방화벽이 허용되어 있는지 확인하세요.")
                sender.send_memo(ip, port, body)
                settings.add_recent_ip(f"{ip}:{port}")
                root.after(0, lambda: (
                    messagebox.showinfo(
                        "빨간우체통", "메모를 보냈습니다.", parent=win),
                    win.destroy(),
                ))
            except sender.SendError as e:
                root.after(0, lambda: (
                    status.config(text=str(e), foreground="red"),
                    send_btn.config(state="normal"),
                ))
            except Exception as e:
                root.after(0, lambda: (
                    status.config(text=f"오류: {e}", foreground="red"),
                    send_btn.config(state="normal"),
                ))

        threading.Thread(target=worker, daemon=True).start()

    send_btn.config(command=do_send)
    win.bind("<Control-Return>", lambda _e: do_send())
