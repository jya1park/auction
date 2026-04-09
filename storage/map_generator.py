"""
지도 HTML 생성 모듈
output/courtauction_list.csv 를 읽어서 HTML 목록 페이지를 생성합니다.
"""
import os
import csv
import html as html_mod
from typing import Optional, List

import config


_ADDR_CANDIDATES = ["물건주소", "소재지", "물건소재지", "주소"]
_CSV_ENCODINGS = ["utf-8-sig", "utf-8", "cp949"]


def _find_address_column(fieldnames: list) -> Optional[str]:
    """주소 컬럼 자동 탐색"""
    for candidate in _ADDR_CANDIDATES:
        if candidate in fieldnames:
            return candidate
    for col in fieldnames:
        if "주소" in col or "소재지" in col:
            return col
    return None


def _read_csv(path: str):
    """
    CSV 파일을 읽습니다. utf-8-sig → utf-8 → cp949 순으로 인코딩을 시도합니다.
    Returns: (fieldnames: list, rows: list[dict])
    """
    last_err = None
    for enc in _CSV_ENCODINGS:
        try:
            with open(path, "r", newline="", encoding=enc) as f:
                reader = csv.DictReader(f)
                fieldnames = list(reader.fieldnames or [])
                rows = [dict(row) for row in reader]
            return fieldnames, rows
        except UnicodeDecodeError as e:
            last_err = e
            continue
    raise ValueError(f"[MapGenerator] CSV 인코딩 감지 실패: {path}") from last_err


def generate_map_html(output_dir: str = None) -> str:
    """
    output/courtauction_list.csv 를 읽어서 지도 HTML을 생성합니다.

    Returns:
        생성된 HTML 파일 경로 (실패 시 빈 문자열)
    """
    if output_dir is None:
        output_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), config.OUTPUT_DIR
        )

    csv_path = os.path.join(output_dir, "courtauction_list.csv")
    if not os.path.exists(csv_path):
        print(f"[MapGenerator] CSV 파일이 없습니다: {csv_path}")
        return ""

    try:
        fieldnames, rows = _read_csv(csv_path)
    except (ValueError, OSError) as e:
        print(f"[MapGenerator] CSV 읽기 오류: {e}")
        return ""

    if not rows:
        print("[MapGenerator] CSV 데이터가 없습니다.")
        return ""

    addr_col = _find_address_column(fieldnames)
    print(f"[MapGenerator] {len(rows)}건 로드, 주소 컬럼: {addr_col}")

    html_path = os.path.join(output_dir, "courtauction_map.html")
    # encoding='utf-8' 명시 — Windows 기본값(cp949) 방지
    with open(html_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(_build_html(rows, addr_col))

    print(f"[MapGenerator] 지도 HTML 생성 완료: {html_path}")
    return html_path


def _esc(value) -> str:
    """HTML 특수문자를 이스케이프합니다."""
    return html_mod.escape(str(value) if value is not None else "", quote=True)


def _build_html(rows: list, addr_col: Optional[str]) -> str:
    """HTML 목록 페이지를 생성합니다."""

    table_rows_html = ""
    for i, row in enumerate(rows, 1):
        addr      = _esc(row.get(addr_col, "") if addr_col else "")
        case_num  = _esc(row.get("사건번호", ""))
        item_num  = _esc(row.get("물건번호", ""))
        appraisal = _esc(row.get("감정가", row.get("감정가_원", "")))
        min_bid   = _esc(row.get("최저입찰가", row.get("최저입찰가_원", "")))
        bid_date  = _esc(row.get("입찰기일", ""))
        status    = _esc(row.get("진행상태", ""))
        # 카카오지도 링크: 주소를 URL 인코딩
        raw_addr = row.get(addr_col, "") if addr_col else ""
        import urllib.parse
        kakao_url = (
            "https://map.kakao.com/link/search/" + urllib.parse.quote(raw_addr)
            if raw_addr else "#"
        )

        table_rows_html += (
            f"<tr>"
            f"<td>{i}</td>"
            f"<td>{case_num}</td>"
            f"<td>{item_num}</td>"
            f'<td><a href="{kakao_url}" target="_blank" rel="noopener">{addr}</a></td>'
            f"<td>{appraisal}</td>"
            f"<td>{min_bid}</td>"
            f"<td>{bid_date}</td>"
            f"<td>{status}</td>"
            f"</tr>\n"
        )

    total = len(rows)
    addr_col_label = _esc(addr_col or "없음")

    return (
        "<!DOCTYPE html>\n"
        '<html lang="ko">\n'
        "<head>\n"
        # charset 선언을 최우선 배치 — 브라우저가 본문 파싱 전에 인식
        '  <meta charset="UTF-8">\n'
        '  <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        "  <title>법원 경매 목록</title>\n"
        "  <style>\n"
        "    * { box-sizing: border-box; margin: 0; padding: 0; }\n"
        "    body { font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif; background: #f4f6fb; }\n"
        "    #header { background: #1F4E79; color: #fff; padding: 14px 24px; }\n"
        "    #header h1 { font-size: 1.1rem; font-weight: 700; }\n"
        "    #stats { padding: 8px 24px; background: #EEF2F7; font-size: 0.85rem; color: #444; border-bottom: 1px solid #d0d7e2; }\n"
        "    #table-container { padding: 16px 24px; overflow-x: auto; }\n"
        "    table { border-collapse: collapse; width: 100%; font-size: 0.82rem; background: #fff;\n"
        "            box-shadow: 0 1px 4px rgba(0,0,0,.08); border-radius: 6px; overflow: hidden; }\n"
        "    thead tr { background: #1F4E79; color: #fff; }\n"
        "    th { padding: 9px 12px; text-align: center; font-weight: 600; white-space: nowrap; }\n"
        "    td { padding: 7px 12px; border-bottom: 1px solid #e8ecf2; vertical-align: middle; }\n"
        "    tbody tr:last-child td { border-bottom: none; }\n"
        "    tbody tr:hover { background: #f0f4fa; }\n"
        "    a { color: #1F4E79; text-decoration: none; }\n"
        "    a:hover { text-decoration: underline; }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        '  <div id="header"><h1>법원 경매 목록</h1></div>\n'
        f'  <div id="stats">총 <strong>{total}</strong>건 &nbsp;|&nbsp; 주소 컬럼: {addr_col_label}</div>\n'
        '  <div id="table-container">\n'
        "    <table>\n"
        "      <thead><tr>\n"
        "        <th>#</th><th>사건번호</th><th>물건번호</th>\n"
        "        <th>주소 (카카오지도 링크)</th>\n"
        "        <th>감정가</th><th>최저입찰가</th><th>입찰기일</th><th>진행상태</th>\n"
        "      </tr></thead>\n"
        "      <tbody>\n"
        f"{table_rows_html}"
        "      </tbody>\n"
        "    </table>\n"
        "  </div>\n"
        "</body>\n"
        "</html>\n"
    )
