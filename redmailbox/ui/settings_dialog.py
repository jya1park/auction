# -*- coding: utf-8 -*-
"""설정 다이얼로그 — 저장 폴더, 포트."""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from core import settings
from ui._common import center_on_screen


def open_dialog(root: tk.Tk, on_changed=None):
    s = settings.load()
    win = tk.Toplevel(root)
    win.title("설정 — 빨간우체통")
    center_on_screen(win, 480, 220)
    win.transient(root)

    frm = ttk.Frame(win, padding=12)
    frm.pack(fill="both", expand=True)

    # 저장 폴더
    ttk.Label(frm, text="받은 파일 저장 폴더").grid(
        row=0, column=0, sticky="w", pady=(0, 2))
    save_var = tk.StringVar(value=s.save_dir)
    save_entry = ttk.Entry(frm, textvariable=save_var)
    save_entry.grid(row=1, column=0, sticky="ew", padx=(0, 6))

    def pick_dir():
        d = filedialog.askdirectory(parent=win, initialdir=save_var.get(),
                                     title="저장 폴더 선택")
        if d:
            save_var.set(d)

    ttk.Button(frm, text="찾아보기...", command=pick_dir).grid(
        row=1, column=1, sticky="ew")

    # 포트
    ttk.Label(frm, text="HTTP 포트 (변경 후 재시작 필요)").grid(
        row=2, column=0, sticky="w", pady=(12, 2))
    port_var = tk.StringVar(value=str(s.port))
    ttk.Entry(frm, textvariable=port_var, width=10).grid(
        row=3, column=0, sticky="w")

    frm.columnconfigure(0, weight=1)

    # 버튼
    btns = ttk.Frame(frm)
    btns.grid(row=4, column=0, columnspan=2, sticky="e", pady=(20, 0))

    def save():
        new_dir = save_var.get().strip()
        if not new_dir:
            messagebox.showwarning(
                "빨간우체통", "저장 폴더를 입력하세요.", parent=win)
            return
        try:
            new_port = int(port_var.get().strip())
            if not (1 <= new_port <= 65535):
                raise ValueError
        except ValueError:
            messagebox.showerror(
                "빨간우체통", "포트는 1~65535 범위 정수여야 합니다.", parent=win)
            return

        port_changed = (new_port != s.port)
        try:
            settings.set_save_dir(new_dir)
            settings.set_port(new_port)
        except OSError as e:
            messagebox.showerror(
                "빨간우체통", f"저장 폴더 생성 실패: {e}", parent=win)
            return

        if on_changed:
            try:
                on_changed()
            except Exception:
                pass

        if port_changed:
            messagebox.showinfo(
                "빨간우체통",
                "포트 변경은 다음 실행부터 적용됩니다.",
                parent=win)
        win.destroy()

    ttk.Button(btns, text="저장", command=save).pack(side="right")
    ttk.Button(btns, text="취소", command=win.destroy).pack(
        side="right", padx=6)
