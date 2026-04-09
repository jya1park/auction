"""
지도 HTML 생성 모듈
output/courtauction_list.csv 를 읽어서 Leaflet 기반 지도 HTML을 생성합니다.
"""
import os
import csv
from typing import Optional, List

import config


_ADDR_CANDIDATES = ["물건주소", "소재지", "물건소재지", "주소"]


def _find_address_column(fieldnames: list) -> Optional[str]:
    """주소 컬럼 자동 탐색"""
    for candidate in _ADDR_CANDIDATES:
        if candidate in fieldnames:
            return candidate
    for col in fieldnames:
        if "주소" in col or "소재지" in col:
            return col
    return None


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

    rows = []
    addr_col = None
    with open(csv_path, "r", newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        addr_col = _find_address_column(fieldnames)
        for row in reader:
            rows.append(dict(row))

    if not rows:
        print("[MapGenerator] CSV 데이터가 없습니다.")
        return ""

    print(f"[MapGenerator] {len(rows)}건 로드, 주소 컬럼: {addr_col}")

    html_path = os.path.join(output_dir, "courtauction_map.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(_build_html(rows, addr_col))

    print(f"[MapGenerator] 지도 HTML 생성 완료: {html_path}")
    return html_path


def _build_html(rows: list, addr_col: Optional[str]) -> str:
    """Leaflet 기반 지도 HTML을 생성합니다."""

    # 테이블 행 생성
    table_rows_html = ""
    for i, row in enumerate(rows, 1):
        addr = row.get(addr_col, "") if addr_col else ""
        case_num = row.get("사건번호", "")
        item_num = row.get("물건번호", "")
        appraisal = row.get("감정가", row.get("감정가_원", ""))
        min_bid = row.get("최저입찰가", row.get("최저입찰가_원", ""))
        bid_date = row.get("입찰기일", "")
        status = row.get("진행상태", "")
        kakao_url = f"https://map.kakao.com/link/search/{addr}" if addr else "#"

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
    addr_col_label = addr_col or "없음"

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>법원 경매 목록</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif; background: #f4f6fb; }}
    #header {{ background: #1F4E79; color: #fff; padding: 14px 24px; display: flex; align-items: center; gap: 16px; }}
    #header h1 {{ font-size: 1.1rem; font-weight: 700; }}
    #stats {{ padding: 8px 24px; background: #EEF2F7; font-size: 0.85rem; color: #444; border-bottom: 1px solid #d0d7e2; }}
    #table-container {{ padding: 16px 24px; overflow-x: auto; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 0.82rem; background: #fff; box-shadow: 0 1px 4px rgba(0,0,0,.08); border-radius: 6px; overflow: hidden; }}
    thead tr {{ background: #1F4E79; color: #fff; }}
    th {{ padding: 9px 12px; text-align: center; font-weight: 600; white-space: nowrap; }}
    td {{ padding: 7px 12px; border-bottom: 1px solid #e8ecf2; vertical-align: middle; }}
    tbody tr:last-child td {{ border-bottom: none; }}
    tbody tr:hover {{ background: #f0f4fa; }}
    a {{ color: #1F4E79; text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
  </style>
</head>
<body>
  <div id="header">
    <h1>법원 경매 목록</h1>
  </div>
  <div id="stats">총 <strong>{total}</strong>건 &nbsp;|&nbsp; 주소 컬럼: {addr_col_label}</div>
  <div id="table-container">
    <table>
      <thead>
        <tr>
          <th>#</th>
          <th>사건번호</th>
          <th>물건번호</th>
          <th>주소 (카카오지도 링크)</th>
          <th>감정가</th>
          <th>최저입찰가</th>
          <th>입찰기일</th>
          <th>진행상태</th>
        </tr>
      </thead>
      <tbody>
        {table_rows_html}
      </tbody>
    </table>
  </div>
</body>
</html>"""
