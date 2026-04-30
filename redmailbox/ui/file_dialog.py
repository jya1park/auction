# -*- coding: utf-8 -*-
"""대용량 파일 보내기 다이얼로그."""
import os
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from core import settings
from client import sender
from ui._common import (parse_ip_port, make_ip_combobox,
                        center_on_screen, format_size)


def open_dialog(root: tk.Tk):
    s = settings.load()
    win = tk.Toplevel(root)
    win.title("대용량 파일 보내기 — 빨간우체통")
    center_on_screen(win, 520, 280)
    win.transient(root)

    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)

    ttk.Label(frm, text="받는 사람 (IP[:포트])").pack(anchor="w")
    ip_cb = make_ip_combobox(frm, default_port=s.port)
    ip_cb.pack(fill="x", pady=(2, 10))

    ttk.Label(frm, text="보낼 파일").pack(anchor="w")
    path_row = ttk.Frame(frm)
    path_row.pack(fill="x", pady=(2, 10))
    path_var = tk.StringVar()
    path_entry = ttk.Entry(path_row, textvariable=path_var, state="readonly")
    path_entry.pack(side="left", fill="x", expand=True)

    def pick():
        p = filedialog.askopenfilename(parent=win, title="보낼 파일 선택")
        if p:
            path_var.set(p)
            size_label.config(
                text=f"크기: {format_size(os.path.getsize(p))}")

    ttk.Button(path_row, text="찾아보기...", command=pick).pack(
        side="left", padx=(6, 0))

    size_label = ttk.Label(frm, text="크기: -", foreground="gray")
    size_label.pack(anchor="w")

    pb = ttk.Progressbar(frm, mode="determinate", maximum=100)
    pb.pack(fill="x", pady=(10, 4))
    progress_label = ttk.Label(frm, text="대기 중", foreground="gray")
    progress_label.pack(anchor="w")

    btns = ttk.Frame(frm)
    btns.pack(fill="x", pady=(8, 0))
    send_btn = ttk.Button(btns, text="보내기")
    send_btn.pack(side="right")
    ttk.Button(btns, text="닫기", command=win.destroy).pack(side="right", padx=6)

    def do_send():
        ip_text = ip_cb.get().strip()
        path = path_var.get().strip()
        if not path or not os.path.isfile(path):
            messagebox.showwarning(
                "빨간우체통", "보낼 파일을 선택해주세요.", parent=win)
            return
        try:
            ip, port = parse_ip_port(ip_text, default_port=s.port)
        except ValueError as e:
            messagebox.showerror("빨간우체통", str(e), parent=win)
            return
        send_btn.config(state="disabled")
        pb["value"] = 0
        progress_label.config(text="연결 확인 중...", foreground="gray")

        start_time = [time.time()]

        def on_progress(read, total):
            pct = (read / total) * 100 if total else 0
            elapsed = time.time() - start_time[0]
            speed = read / elapsed if elapsed > 0 else 0

            def upd():
                pb["value"] = pct
                progress_label.config(
                    text=f"{format_size(read)} / {format_size(total)}  "
                         f"({pct:.1f}%, {format_size(int(speed))}/s)",
                    foreground="black")
            root.after(0, upd)

        def worker():
            try:
                if not sender.ping(ip, port, timeout=3):
                    raise sender.SendError(
                        f"수신 측({ip}:{port})에 연결할 수 없습니다.")
                start_time[0] = time.time()
                r = sender.send_file(ip, port, path, on_progress=on_progress)
                settings.add_recent_ip(f"{ip}:{port}")
                root.after(0, lambda: (
                    progress_label.config(
                        text=f"전송 완료 — 저장: {r.get('saved', '?')}",
                        foreground="green"),
                    messagebox.showinfo(
                        "빨간우체통", "파일을 보냈습니다.", parent=win),
                    send_btn.config(state="normal"),
                ))
            except sender.SendError as e:
                root.after(0, lambda: (
                    progress_label.config(text=str(e), foreground="red"),
                    send_btn.config(state="normal"),
                ))
            except Exception as e:
                root.after(0, lambda: (
                    progress_label.config(text=f"오류: {e}", foreground="red"),
                    send_btn.config(state="normal"),
                ))

        threading.Thread(target=worker, daemon=True).start()

    send_btn.config(command=do_send)
