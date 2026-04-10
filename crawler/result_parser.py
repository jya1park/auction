"""
매각결과 목록 파싱 모듈

대법원 경매 매각결과 테이블 구조 (일반적):
- 사건번호, 물건번호, 소재지, 용도, 감정평가액, 최저매각가격, 매각금액, 매각일자, 입찰자수
"""
import re
from typing import List, Dict, Optional
from bs4 import BeautifulSoup


def parse_amount(text: str) -> Optional[int]:
    """금액 문자열을 원(정수)으로 변환합니다."""
    if not text:
        return None
    text = str(text).strip()
    text = re.sub(r'\([\d.]+%?\)', '', text)
    match = re.search(r'([\d,]+)', text)
    if match:
        num_str = match.group(1).replace(",", "")
        if num_str.isdigit() and len(num_str) >= 4:
            return int(num_str)
    return None


def _extract_date(text: str) -> str:
    match = re.search(r'(\d{4}[.\-/]\d{2}[.\-/]\d{2})', str(text))
    return match.group(1) if match else ""


def _extract_court_and_case(raw: str):
    raw = str(raw).strip()
    if not raw:
        return "", ""
    court_match = re.match(
        r'^(.+?(?:지방법원|가정법원|지원|법원)(?:부동산경매)?)\s*(.+)$', raw
    )
    if not court_match:
        return "", raw
    court = court_match.group(1).strip()
    remainder = court_match.group(2).strip()
    CASE_PATTERN = r'(\d{4}(?:타경|타채|강경|강채|타기|경매|임의|강제)\d+?)(?=\d{4}(?:타경|타채|강경|강채|타기|경매|임의|강제)|\D|$)'
    cases = re.findall(CASE_PATTERN, remainder)
    return court, cases[0] if cases else remainder


def parse_result_page(page_source: str, debug: bool = False) -> List[Dict]:
    """
    매각결과 페이지 소스에서 데이터를 파싱합니다.

    매각결과 테이블은 사이트마다 구조가 다를 수 있으므로
    컬럼 헤더를 자동으로 감지하여 파싱합니다.
    """
    soup = BeautifulSoup(page_source, "html.parser")
    results = []

    # 데이터 행이 가장 많은 테이블 선택
    tables = soup.find_all("table")
    if debug:
        print(f"[ResultParser] 테이블 수: {len(tables)}")

    target_table = None
    max_rows = 0
    for i, table in enumerate(tables):
        rows = table.find_all("tr")
        data_rows = [r for r in rows if r.find_all("td")]
        if debug:
            print(f"  table[{i}]: {len(rows)}행 (데이터행 {len(data_rows)})")
        if len(data_rows) > max_rows:
            max_rows = len(data_rows)
            target_table = table

    if target_table is None:
        if debug:
            print("[ResultParser] 테이블 없음")
        return results

    # 헤더 행 감지 (th 또는 첫 tr)
    headers = []
    header_row = target_table.find("tr")
    if header_row:
        ths = header_row.find_all(["th", "td"])
        headers = [th.get_text(strip=True) for th in ths]
        if debug:
            print(f"[ResultParser] 감지된 헤더: {headers}")

    # 헤더가 없거나 부실하면 기본 컬럼명 사용
    DEFAULT_HEADERS = [
        "사건번호", "물건번호", "소재지", "용도",
        "감정평가액", "최저매각가격", "매각금액", "매각일자", "입찰자수"
    ]
    if not headers or all(not h for h in headers):
        headers = DEFAULT_HEADERS

    rows = target_table.find_all("tr")
    for row in rows:
        cells = row.find_all("td")
        if not cells:
            continue

        texts = [c.get_text(strip=True) for c in cells]
        if not any(texts):
            continue

        row_data = {}

        # 헤더 매핑
        for i, text in enumerate(texts):
            if i < len(headers):
                row_data[headers[i]] = text
            else:
                row_data[f"컬럼{i+1}"] = text

        # 사건번호 파싱 (법원명이 붙어있을 경우)
        case_raw = row_data.get("사건번호", "")
        if case_raw and any(kw in case_raw for kw in ["지방법원", "가정법원", "지원"]):
            court, case_no = _extract_court_and_case(case_raw)
            row_data["사건번호"] = case_no
            row_data["법원"] = court
        elif not row_data.get("법원"):
            row_data["법원"] = ""

        # 금액 컬럼 파싱
        for col in ["감정평가액", "최저매각가격", "매각금액"]:
            if col in row_data:
                row_data[col + "_원"] = parse_amount(row_data[col])

        # 매각일자 정규화
        for col in ["매각일자", "매각기일"]:
            if col in row_data and row_data[col]:
                row_data[col] = _extract_date(row_data[col]) or row_data[col]

        # 유효 행 필터링 (사건번호 또는 소재지가 있어야 함)
        if row_data.get("사건번호") or row_data.get("소재지"):
            results.append(row_data)

    if debug:
        print(f"[ResultParser] 파싱 완료: {len(results)}건")

    return results


def get_total_count(page_source: str) -> Optional[int]:
    """페이지에서 전체 결과 수를 추출합니다."""
    soup = BeautifulSoup(page_source, "html.parser")
    patterns = [
        r"총\s*([\d,]+)\s*건",
        r"전체\s*([\d,]+)\s*건",
        r"검색결과\s*:\s*([\d,]+)",
        r"총\s*([\d,]+)",
    ]
    text = soup.get_text()
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            val = int(match.group(1).replace(",", ""))
            if val > 0:
                return val
    return None
