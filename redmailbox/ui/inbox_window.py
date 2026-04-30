# -*- coding: utf-8 -*-
"""받은 목록 창."""
import os
import sys
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox

from core import history, settings
from ui._common import center_on_screen, format_size


def _open_path(path: str):
    """OS 기본 프로그램으로 파일/폴더 열기."""
    try:
        if sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception as e:
        messagebox.showerror("빨간우체통", f"열기 실패: {e}")


def open_window(root: tk.Tk):
    win = tk.Toplevel(root)
    win.title("받은 목록 — 빨간우체통")
    center_on_screen(win, 720, 420)
    win.transient(root)

    frm = ttk.Frame(win, padding=8)
    frm.pack(fill="both", expand=True)

    cols = ("received_at", "kind", "sender_ip", "name", "size")
    tree = ttk.Treeview(frm, columns=cols, show="headings", height=15)
    tree.heading("received_at", text="시각")
    tree.heading("kind", text="종류")
    tree.heading("sender_ip", text="발신 IP")
    tree.heading("name", text="이름 / 본문")
    tree.heading("size", text="크기")
    tree.column("received_at", width=140, anchor="w")
    tree.column("kind", width=60, anchor="center")
    tree.column("sender_ip", width=110, anchor="w")
    tree.column("name", width=320, anchor="w")
    tree.column("size", width=80, anchor="e")

    scroll = ttk.Scrollbar(frm, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")

    items_by_iid = {}

    def load():
        tree.delete(*tree.get_children())
        items_by_iid.clear()
        for it in history.list_recent(200):
            preview = (it.body or "").replace("\n", " ")[:80] \
                if it.kind == "memo" else (it.name or "?")
            size = format_size(it.size) if it.size else "-"
            iid = tree.insert(
                "", "end",
                values=(it.received_at,
                        "메모" if it.kind == "memo" else "파일",
                        it.sender_ip, preview, size),
            )
            items_by_iid[iid] = it

    def on_double_click(_e):
        sel = tree.selection()
        if not sel:
            return
        it = items_by_iid.get(sel[0])
        if not it:
            return
        if it.kind == "memo":
            # 메모 본문 팝업
            popup = tk.Toplevel(win)
            popup.title(f"메모 — {it.sender_ip} @ {it.received_at}")
            center_on_screen(popup, 480, 320)
            t = tk.Text(popup, wrap="word", padx=8, pady=8)
            t.insert("1.0", it.body or "")
            t.config(state="disabled")
            t.pack(fill="both", expand=True)
        else:
            if it.path and os.path.exists(it.path):
                _open_path(it.path)
            else:
                messagebox.showwarning(
                    "빨간우체통",
                    "파일을 찾을 수 없습니다 (이동/삭제됨).",
                    parent=win)

    tree.bind("<Double-Button-1>", on_double_click)

    bar = ttk.Frame(win, padding=(8, 4))
    bar.pack(fill="x")
    ttk.Button(bar, text="새로고침", command=load).pack(side="left")
    ttk.Button(
        bar, text="저장 폴더 열기",
        command=lambda: _open_path(settings.load().save_dir),
    ).pack(side="left", padx=6)
    ttk.Button(bar, text="닫기", command=win.destroy).pack(side="right")

    load()
    return win
