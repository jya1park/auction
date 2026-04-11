"""
매각결과 목록 파싱 모듈

대법원 경매 매각결과 테이블 구조:
- rowspan/colspan을 사용하는 구조를 정규화하여 파싱합니다.
- 사건번호 없이 용도/금액만 있는 서브행을 이전 행에 병합합니다.
"""
import re
from typing import List, Dict, Optional, Tuple

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


def _extract_court_and_case(raw: str) -> Tuple[str, str]:
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


def _safe_int(val, default: int = 1) -> int:
    """빈 문자열이나 None도 안전하게 int로 변환합니다."""
    try:
        return max(1, int(val))
    except (ValueError, TypeError):
        return default


def _expand_table(table) -> List[List[str]]:
    """
    rowspan/colspan을 처리하여 정규화된 2D 그리드를 반환합니다.
    각 셀은 텍스트 문자열이며, rowspan/colspan으로 확장된 셀은 동일한 값이 반복됩니다.
    """
    raw_rows = table.find_all("tr")
    if not raw_rows:
        return []

    # 최대 열 수 계산
    n_cols = 0
    for tr in raw_rows:
        w = sum(_safe_int(c.get("colspan", 1)) for c in tr.find_all(["td", "th"]))
        n_cols = max(n_cols, w)
    n_cols = max(n_cols, 1)
    n_rows = len(raw_rows)

    # None으로 초기화된 그리드
    grid: List[List[Optional[str]]] = [[None] * n_cols for _ in range(n_rows)]

    for ri, tr in enumerate(raw_rows):
        ci = 0
        for cell in tr.find_all(["td", "th"]):
            # 이미 채워진 셀 건너뛰기 (rowspan으로 채워진 경우)
            while ci < n_cols and grid[ri][ci] is not None:
                ci += 1
            if ci >= n_cols:
                break

            rowspan = min(_safe_int(cell.get("rowspan", 1)), n_rows - ri)
            colspan = min(_safe_int(cell.get("colspan", 1)), n_cols - ci)
            text = cell.get_text(strip=True)

            for r in range(rowspan):
                for c in range(colspan):
                    if ri + r < n_rows and ci + c < n_cols:
                        grid[ri + r][ci + c] = text
            ci += colspan

    return [[v if v is not None else "" for v in row] for row in grid]


def _is_header_row(row: List[str]) -> bool:
    """헤더 행 여부를 판단합니다."""
    keywords = {"사건번호", "물건번호", "소재지", "용도", "감정", "매각", "입찰"}
    return any(any(kw in cell for kw in keywords) and len(cell) <= 10 for cell in row)


def parse_result_page(page_source: str, debug: bool = False) -> List[Dict]:
    """
    매각결과 페이지 소스에서 데이터를 파싱합니다.

    rowspan/colspan 구조 및 용도·금액이 서브행으로 분리된 구조 모두 처리합니다.
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
        data_rows = [r for r in table.find_all("tr") if r.find_all("td")]
        if debug:
            print(f"  table[{i}]: {len(data_rows)}행")
        if len(data_rows) > max_rows:
            max_rows = len(data_rows)
            target_table = table

    if target_table is None:
        if debug:
            print("[ResultParser] 테이블 없음")
        return results

    # rowspan/colspan 정규화
    grid = _expand_table(target_table)
    if not grid:
        return results

    if debug:
        print(f"[ResultParser] 그리드: {len(grid)}행 x {len(grid[0])}열")

    # 헤더 행 탐색 (th 태그 포함 행 우선)
    raw_rows = target_table.find_all("tr")
    header_row_idx = 0
    for i, tr in enumerate(raw_rows):
        if tr.find("th"):
            header_row_idx = i
            break

    headers = grid[header_row_idx] if grid else []

    # 헤더가 비어있으면 기본값 사용
    DEFAULT_HEADERS = [
        "사건번호", "물건번호", "소재지", "용도",
        "감정평가액", "최저매각가격", "매각금액", "매각일자", "입찰자수"
    ]
    if not any(h.strip() for h in headers):
        headers = DEFAULT_HEADERS

    if debug:
        print(f"[ResultParser] 헤더: {headers}")

    # 중복 방지용 키 집합 (rowspan 확장으로 동일 행이 반복되는 경우)
    seen_keys = set()

    def row_to_dict(row: List[str]) -> Dict:
        row_data: Dict = {}
        for ci, text in enumerate(row):
            if ci < len(headers) and headers[ci]:
                col = headers[ci]
                if col not in row_data:  # 중복 헤더는 첫 번째 값 사용
                    row_data[col] = text
            elif text:
                row_data[f"컬럼{ci+1}"] = text
        return row_data

    def finalize(row_data: Dict) -> Dict:
        """사건번호 파싱, 금액 변환, 날짜 정규화 등 후처리."""
        # 사건번호에 법원명이 붙어있는 경우 분리
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

        # 물건번호 기본값
        if not row_data.get("물건번호"):
            row_data["물건번호"] = "1"

        return row_data

    # 서브행 판단: 사건번호·소재지 없이 용도·금액만 있는 행
    SUBROW_FIELDS = {"용도", "감정평가액", "최저매각가격", "매각금액"}

    for ri, row in enumerate(grid):
        if ri == header_row_idx:
            continue
        if not any(row):
            continue
        # 순수 헤더 반복 행 건너뛰기
        if _is_header_row(row):
            continue

        row_data = row_to_dict(row)

        has_case = bool(row_data.get("사건번호", "").strip())
        has_loc  = bool(row_data.get("소재지", "").strip())

        if has_case or has_loc:
            # 정상 메인 행
            row_data = finalize(row_data)
            key = (row_data.get("사건번호", ""), row_data.get("물건번호", ""))

            if key in seen_keys:
                # rowspan 확장으로 인한 중복 → 비어있는 필드만 보완
                for existing in reversed(results):
                    ek = (existing.get("사건번호", ""), existing.get("물건번호", ""))
                    if ek == key:
                        for k, v in row_data.items():
                            if v and not existing.get(k):
                                existing[k] = v
                        break
                continue

            seen_keys.add(key)
            results.append(row_data)

        else:
            # 서브행: 용도·금액 정보가 있으면 직전 결과에 병합
            has_subrow_data = any(row_data.get(f) for f in SUBROW_FIELDS)
            if has_subrow_data and results:
                prev = results[-1]
                for k, v in row_data.items():
                    if v and not prev.get(k):
                        prev[k] = v
                # 금액 원 단위 재계산 (새로 병합된 경우)
                for col in ["감정평가액", "최저매각가격", "매각금액"]:
                    if col in prev and not prev.get(col + "_원"):
                        prev[col + "_원"] = parse_amount(prev[col])

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
