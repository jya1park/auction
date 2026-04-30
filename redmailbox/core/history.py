# -*- coding: utf-8 -*-
"""
받은 항목 영속화: %LOCALAPPDATA%/RedMailbox/history.db (SQLite)

스키마:
    items(
        id, received_at, kind ('memo' | 'file'),
        sender_ip, name, body, path, size, is_read
    )
"""
import os
import sqlite3
import threading
from datetime import datetime
from typing import List, Optional

from . import paths


_lock = threading.Lock()
_conn: "sqlite3.Connection | None" = None


def _db_path() -> str:
    return os.path.join(paths.app_data_dir(), "history.db")


def _connect() -> sqlite3.Connection:
    global _conn
    if _conn is not None:
        return _conn
    conn = sqlite3.connect(_db_path(), check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            received_at TEXT NOT NULL,
            kind TEXT NOT NULL,
            sender_ip TEXT NOT NULL,
            name TEXT,
            body TEXT,
            path TEXT,
            size INTEGER,
            is_read INTEGER DEFAULT 0
        )
    """)
    conn.commit()
    _conn = conn
    return conn


class Item:
    def __init__(self, row):
        (self.id, self.received_at, self.kind, self.sender_ip,
         self.name, self.body, self.path, self.size, self.is_read) = row

    def to_dict(self):
        return {
            "id": self.id, "received_at": self.received_at, "kind": self.kind,
            "sender_ip": self.sender_ip, "name": self.name, "body": self.body,
            "path": self.path, "size": self.size, "is_read": bool(self.is_read),
        }


def add_memo(sender_ip: str, text: str) -> int:
    with _lock:
        conn = _connect()
        cur = conn.execute(
            "INSERT INTO items(received_at, kind, sender_ip, body) "
            "VALUES (?, 'memo', ?, ?)",
            (datetime.now().isoformat(timespec="seconds"), sender_ip, text),
        )
        conn.commit()
        return cur.lastrowid


def add_file(sender_ip: str, filename: str, path: str, size: int) -> int:
    with _lock:
        conn = _connect()
        cur = conn.execute(
            "INSERT INTO items(received_at, kind, sender_ip, name, path, size) "
            "VALUES (?, 'file', ?, ?, ?, ?)",
            (datetime.now().isoformat(timespec="seconds"),
             sender_ip, filename, path, size),
        )
        conn.commit()
        return cur.lastrowid


def list_recent(limit: int = 100) -> List[Item]:
    with _lock:
        conn = _connect()
        rows = conn.execute(
            "SELECT id, received_at, kind, sender_ip, name, body, path, size, is_read "
            "FROM items ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [Item(r) for r in rows]


def get(item_id: int) -> Optional[Item]:
    with _lock:
        conn = _connect()
        row = conn.execute(
            "SELECT id, received_at, kind, sender_ip, name, body, path, size, is_read "
            "FROM items WHERE id = ?",
            (item_id,),
        ).fetchone()
    return Item(row) if row else None


def unread_count() -> int:
    with _lock:
        conn = _connect()
        row = conn.execute(
            "SELECT COUNT(*) FROM items WHERE is_read = 0"
        ).fetchone()
    return int(row[0]) if row else 0


def mark_all_read() -> None:
    with _lock:
        conn = _connect()
        conn.execute("UPDATE items SET is_read = 1 WHERE is_read = 0")
        conn.commit()
