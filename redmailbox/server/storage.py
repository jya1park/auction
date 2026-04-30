# -*- coding: utf-8 -*-
"""받은 파일을 디스크에 저장. 같은 이름은 ' (1)', ' (2)' 자동 numbering."""
import os
from typing import Iterable

from core import settings


def _unique_path(directory: str, filename: str) -> str:
    base, ext = os.path.splitext(filename)
    candidate = os.path.join(directory, filename)
    n = 1
    while os.path.exists(candidate):
        candidate = os.path.join(directory, f"{base} ({n}){ext}")
        n += 1
    return candidate


def save_stream(filename: str, chunks: Iterable[bytes]) -> str:
    """
    chunks를 .part 임시 파일에 쓰고 완료 후 원자적 rename.
    중간 실패 시 깨진 파일 안 남김.

    returns: 최종 저장된 절대 경로
    """
    save_dir = settings.load().save_dir
    os.makedirs(save_dir, exist_ok=True)
    safe = os.path.basename(filename) or "untitled.bin"  # path traversal 차단
    target = _unique_path(save_dir, safe)
    tmp = target + ".part"
    try:
        with open(tmp, "wb") as f:
            for buf in chunks:
                if buf:
                    f.write(buf)
        os.replace(tmp, target)
    except BaseException:
        # 실패 시 .part 정리
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass
        raise
    return target
