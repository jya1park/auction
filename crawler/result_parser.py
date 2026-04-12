"""
매각결과 목록 파싱 모듈

대법원 경매 매각결과 테이블 구조:
- rowspan/colspan을 사용하는 구조를 정규화하여 파싱합니다.
- 사건번호 없이 용도/금액만 있는 서브행을 이전 행에 병합합니다.

【테이블 구조 분석】
메인행: 사건번호 | 물건번호 | 소재지 및 내역 | 비고 | 감정평가액 | 담당계매각기일
서브행: (rowspan) | 용도    | (rowspan)     |     | 최저매각가격| 매각금액/유찰

- rowspan 확장 후 서브행도 사건번호를 가지므로 사건번호 유무로 서브행을 판별할 수 없음
- 서브행 판별: 물건번호 위치에 부동산 용도명(아파트 등)이 있으면 서브행으로 처리
"""
import re
from typing import List, Dict, Optional, Tuple

from bs4 import BeautifulSoup


# 부동산 용도 유형 (서브행 판별에 사용)
PROPERTY_TYPES = frozenset({
    "아파트", "빌라", "연립", "연립주택", "다세대", "다가구", "단독주택",
    "상가", "근린상가", "근린시설", "사무실", "오피스텔", "공장", "창고",
    "토지", "임야", "전", "답", "대지", "잡종지", "주택", "점포", "건물",
})


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


def _is_property_type(text: str) -> bool:
    """텍스트가 부동산 용도 유형인지 판단합니다."""
    text = text.strip()
    return any(pt == text or pt in text for pt in PROPERTY_TYPES)


def _parse_result_cell(text: str) -> Dict:
    """
    담당계/매각결과 컬럼 텍스트에서 결과 정보를 추출합니다.

    형태:
    - "유찰"                → 매각결과=유찰
    - "매각696,969,699"    → 매각결과=매각, 매각금액=696969699
    - "최저366,500,000매각696,969,699" 등 복합 형태도 처리
    """
    result: Dict = {}
    text = text.strip()

    if not text:
        return result

    # 유찰
    if "유찰" in text:
        result["매각결과"] = "유찰"
        return result

    # 매각 포함
    if "매각" in text:
        result["매각결과"] = "매각"
        # 최저매각가격 추출 시도 (복합 형태)
        min_match = re.search(r'최저\s*([\d,]+)', text)
        if min_match:
            raw_min = min_match.group(1).replace(",", "")
            if raw_min.isdigit():
                result["최저매각가격"] = f"{int(raw_min):,}"
                result["최저매각가격_원"] = int(raw_min)
        # 매각금액 추출
        sale_match = re.search(r'매각\s*([\d,]+)', text)
        if sale_match:
            raw_sale = sale_match.group(1).replace(",", "")
            if raw_sale.isdigit():
                result["매각금액"] = f"{int(raw_sale):,}"
                result["매각금액_원"] = int(raw_sale)
        return result

    # 순수 금액만 있는 경우 (숫자+콤마로만 구성)
    amount = parse_amount(text)
    if amount and amount >= 1_000_000:
        result["매각금액"] = f"{amount:,}"
        result["매각금액_원"] = amount

    return result


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

    【서브행 처리 전략】
    rowspan으로 인해 서브행도 사건번호를 가지므로, 사건번호 유무로 판별 불가.
    대신 물건번호 컬럼 위치에 부동산 용도명(아파트, 빌라 등)이 있으면 서브행으로 처리.

    서브행에서 추출:
    - 물건번호 위치 → 용도
    - 마지막 컬럼 위치 → _parse_result_cell()로 매각결과/최저매각가격/매각금액 추출
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

    # 물건번호 컬럼 인덱스 탐색
    gun_col_idx = None
    last_col_idx = len(headers) - 1
    for ci, h in enumerate(headers):
        if "물건번호" in h:
            gun_col_idx = ci
            break

    # 결과 컬럼 인덱스: 마지막 컬럼 또는 '매각기일', '결과' 포함 컬럼
    result_col_idx = last_col_idx
    for ci, h in enumerate(headers):
        if any(kw in h for kw in ["매각기일", "결과", "입찰기간", "담당"]):
            result_col_idx = ci

    if debug:
        print(f"[ResultParser] 물건번호 컬럼: {gun_col_idx}, 결과 컬럼: {result_col_idx}")

    # 중복 방지용 키 집합 (rowspan 확장으로 동일 행이 반복되는 경우)
    seen_keys = set()

    def row_to_dict(row: List[str]) -> Dict:
        row_data: Dict = {}
        for ci, text in enumerate(row):
            if ci < len(headers) and headers[ci]:
                col = headers[ci]
                if col not in row_data:
                    row_data[col] = text
            elif text:
                row_data[f"컬럼{ci+1}"] = text
        return row_data

    def finalize(row_data: Dict) -> Dict:
        """사건번호 파싱, 금액 변환, 날짜 정규화 등 후처리."""
        case_raw = row_data.get("사건번호", "")
        if case_raw and any(kw in case_raw for kw in ["지방법원", "가정법원", "지원"]):
            court, case_no = _extract_court_and_case(case_raw)
            row_data["사건번호"] = case_no
            row_data["법원"] = court
        elif not row_data.get("법원"):
            row_data["법원"] = ""

        # 금액 컬럼 파싱
        for col in ["감정평가액", "최저매각가격", "매각금액"]:
            if col in row_data and row_data[col] and not row_data.get(col + "_원"):
                row_data[col + "_원"] = parse_amount(row_data[col])

        # 날짜 정규화
        for col in ["매각일자", "매각기일"]:
            if col in row_data and row_data[col]:
                row_data[col] = _extract_date(row_data[col]) or row_data[col]

        # 물건번호 기본값
        if not row_data.get("물건번호"):
            row_data["물건번호"] = "1"

        return row_data

    def is_subrow_by_content(row_data: Dict, row: List[str]) -> bool:
        """
        행 내용을 보고 서브행 여부를 판단합니다.

        기준:
        1. 물건번호 위치에 부동산 용도명이 있음 (아파트, 빌라 등)
        2. 물건번호가 숫자가 아님 (물건번호는 보통 1, 2, 3 등 숫자)
        """
        if gun_col_idx is not None and gun_col_idx < len(row):
            gun_val = row[gun_col_idx].strip()
            if gun_val and not gun_val.isdigit():
                # 숫자가 아닌 값이 물건번호 위치에 있으면 서브행 의심
                if _is_property_type(gun_val):
                    return True
        return False

    def merge_subrow(prev: Dict, row: List[str], row_data: Dict):
        """서브행 데이터를 이전 메인행에 병합합니다."""
        # 물건번호 위치에서 용도 추출
        if gun_col_idx is not None and gun_col_idx < len(row):
            gun_val = row[gun_col_idx].strip()
            if gun_val and not prev.get("용도"):
                prev["용도"] = gun_val

        # 결과 컬럼에서 매각결과/최저매각가격/매각금액 추출
        if result_col_idx < len(row):
            result_text = row[result_col_idx].strip()
            if result_text:
                parsed = _parse_result_cell(result_text)
                for k, v in parsed.items():
                    if not prev.get(k):
                        prev[k] = v

        # 서브행 그리드 다른 컬럼에서도 최저매각가격 찾기
        # (감정평가액 컬럼이 rowspan이 아니라면 해당 위치에 최저매각가격이 있을 수 있음)
        for ci, h in enumerate(headers):
            if "최저" in h and "매각" in h:
                val = row[ci] if ci < len(row) else ""
                if val and val != prev.get("감정평가액") and not prev.get("최저매각가격"):
                    prev["최저매각가격"] = val
                    amt = parse_amount(val)
                    if amt:
                        prev["최저매각가격_원"] = amt
                break

    for ri, row in enumerate(grid):
        if ri == header_row_idx:
            continue
        if not any(row):
            continue
        if _is_header_row(row):
            continue

        row_data = row_to_dict(row)

        # 서브행 판별
        if is_subrow_by_content(row_data, row):
            # 서브행: 이전 메인행에 데이터 병합
            if results:
                merge_subrow(results[-1], row, row_data)
                if debug:
                    gun_val = row[gun_col_idx] if gun_col_idx and gun_col_idx < len(row) else ""
                    res_val = row[result_col_idx] if result_col_idx < len(row) else ""
                    print(f"  [서브행] 용도={gun_val}, 결과={res_val}")
            continue

        # 메인행 처리
        has_case = bool(row_data.get("사건번호", "").strip())
        has_loc = bool(
            row_data.get("소재지", "").strip()
            or row_data.get("소재지 및 내역", "").strip()
        )

        if not (has_case or has_loc):
            # 사건번호도 소재지도 없는 빈 행 → 서브행 재시도
            has_subrow_data = any(
                row_data.get(f) for f in ["용도", "감정평가액", "최저매각가격", "매각금액"]
            )
            if has_subrow_data and results:
                merge_subrow(results[-1], row, row_data)
            continue

        # 정상 메인행
        row_data = finalize(row_data)
        key = (row_data.get("사건번호", ""), row_data.get("물건번호", ""))

        if key in seen_keys:
            # rowspan으로 인한 중복 행 → 기존 레코드 보완
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

    if debug:
        print(f"[ResultParser] 파싱 완료: {len(results)}건")
        for r in results:
            print(f"  [{r.get('사건번호')}] 용도={r.get('용도')} 최저매각가격={r.get('최저매각가격')} 매각금액={r.get('매각금액')} 결과={r.get('매각결과')}")

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
