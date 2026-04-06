"""
검색 결과 목록 파싱 모듈

대법원 경매 사이트 테이블 구조:
- 8셀 행: [체크박스, 사건번호, 물건번호, 소재지및면적, 용도, 비고, 감정평가액, 최저입찰가/기일]
- 3셀 행: [진행상태, 최저입찰가(비율%), 유찰횟수]  ← 8셀 행과 쌍을 이룸
"""
import re
from typing import List, Dict, Optional
from bs4 import BeautifulSoup


def parse_amount(text: str) -> Optional[int]:
    """
    금액 문자열을 원(정수)으로 변환합니다.
    예: "350,000,000" → 350000000
        "350,000,000원" → 350000000
        "545,617,000(49%)" → 545617000
    """
    if not text:
        return None
    text = text.strip()

    # 괄호 안 비율 제거: "545,617,000(49%)" → "545,617,000"
    text = re.sub(r'\([\d.]+%?\)', '', text)

    # 숫자+콤마 패턴
    match = re.search(r'([\d,]+)', text)
    if match:
        num_str = match.group(1).replace(",", "")
        if num_str.isdigit() and len(num_str) >= 4:
            return int(num_str)

    # 억/만 단위 패턴
    result = 0
    eok = re.search(r'(\d+(?:\.\d+)?)억', text)
    man = re.search(r'([\d,]+)만', text)
    if eok:
        result += int(float(eok.group(1)) * 100_000_000)
    if man:
        result += int(man.group(1).replace(",", "")) * 10_000
    if result > 0:
        return result

    return None


def _extract_date(text: str) -> str:
    """텍스트에서 날짜(YYYY.MM.DD)를 추출합니다."""
    match = re.search(r'(\d{4}[.\-/]\d{2}[.\-/]\d{2})', text)
    return match.group(1) if match else ""


def _extract_fail_count(text: str) -> int:
    """텍스트에서 유찰 횟수를 추출합니다. 예: '유찰 7회' → 7"""
    match = re.search(r'(\d+)\s*회', text)
    return int(match.group(1)) if match else 0


def _extract_court_and_case(raw: str):
    """
    '수원지방법원2022타경56861' 또는 '수원지방법원2022타경568612022타경2574(중복)' 형태에서
    법원명과 첫 번째 사건번호만 분리합니다.
    """
    raw = raw.strip()
    if not raw:
        return "", ""

    # 법원명 추출
    court_match = re.match(
        r'^(.+?(?:지방법원|가정법원|지원|법원)(?:부동산경매)?)\s*(.+)$',
        raw
    )
    if not court_match:
        return "", raw

    court = court_match.group(1).strip()
    remainder = court_match.group(2).strip()

    # 사건번호 패턴: YYYY + 사건구분(타경/강제/임의/타채/강채 등) + 숫자
    CASE_PATTERN = r'(\d{4}(?:타경|타채|강경|강채|타기|경매|임의|강제)\d+?)(?=\d{4}(?:타경|타채|강경|강채|타기|경매|임의|강제)|\D|$)'
    cases = re.findall(CASE_PATTERN, remainder)
    if cases:
        return court, cases[0]  # 첫 번째 사건번호만 반환

    # 패턴 매칭 실패 시 원본 반환
    return court, remainder


def _parse_main_row(cells) -> Optional[Dict]:
    """8셀 메인 행을 파싱합니다."""
    texts = [c.get_text(strip=True) for c in cells]
    if len(texts) < 8:
        return None

    # cells[1]: 사건번호
    case_raw = texts[1]
    court, case_no = _extract_court_and_case(case_raw)

    # cells[7]: '최저입찰가(입찰기간)' - "토7회2026.04.14" 또는 "금14회2026.04.10" 형식
    bid_field = texts[7]
    bid_date = _extract_date(bid_field)
    fail_count_from_main = _extract_fail_count(bid_field)

    # cells[6]: 감정평가액
    appraisal_text = texts[6]
    appraisal_amount = parse_amount(appraisal_text)

    # 링크에서 href/onclick 추출
    link = ""
    for cell in cells:
        a_tag = cell.find("a")
        if a_tag:
            href = a_tag.get("href", "")
            onclick = a_tag.get("onclick", "")
            if href and href != "#":
                link = href
            elif onclick:
                link = onclick[:80]
            break

    data = {
        "사건번호": case_no,
        "법원": court,
        "물건번호": texts[2],
        "물건주소": texts[3],
        "용도": texts[4],
        "비고": texts[5],
        "감정평가액": appraisal_text,
        "감정가_원": appraisal_amount,
        "입찰기일": bid_date,
        "유찰횟수_입찰란": fail_count_from_main,
        "링크": link,
    }
    return data


def _parse_detail_row(cells) -> Dict:
    """3셀 상세 행을 파싱합니다: [진행상태, 최저입찰가(%), 유찰횟수]"""
    texts = [c.get_text(strip=True) for c in cells]
    detail = {}

    if len(texts) >= 1:
        detail["진행상태"] = texts[0]
    if len(texts) >= 2:
        # "545,617,000(49%)" 형식
        bid_text = texts[1]
        detail["최저입찰가_표시"] = bid_text
        detail["최저입찰가_원"] = parse_amount(bid_text)
        # 비율 추출
        rate_match = re.search(r'\(([\d.]+)%\)', bid_text)
        if rate_match:
            detail["최저입찰가율"] = float(rate_match.group(1))
    if len(texts) >= 3:
        detail["유찰횟수"] = _extract_fail_count(texts[2])
        detail["유찰횟수_원문"] = texts[2]

    return detail


def parse_list_page(page_source: str, debug: bool = False) -> List[Dict]:
    """
    페이지 소스에서 경매 목록을 파싱합니다.

    테이블은 메인 행(8셀) + 상세 행(3셀) 쌍으로 구성됩니다.
    동일 사건번호의 복수 물건은 빈 셀 행으로 이어집니다.
    """
    soup = BeautifulSoup(page_source, "lxml")
    results = []

    # 데이터 테이블 선택 (데이터 행이 가장 많은 테이블)
    tables = soup.find_all("table")
    if debug:
        print(f"[ListParser] 테이블 수: {len(tables)}")

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
            print("[ListParser] 테이블 없음")
        return results

    rows = target_table.find_all("tr")
    if debug:
        print(f"[ListParser] 선택된 테이블: {len(rows)}행")

    current_item = None
    prev_case_no = ""
    prev_court = ""

    for row in rows:
        cells = row.find_all("td")
        if not cells:
            continue

        n = len(cells)

        if n == 8:
            # ─ 메인 행 ─
            main = _parse_main_row(cells)
            if main is None:
                continue

            # 사건번호가 비어있으면 이전 사건번호 상속 (동일 사건 복수 물건)
            if not main["사건번호"] and prev_case_no:
                main["사건번호"] = prev_case_no
                main["법원"] = prev_court
            elif main["사건번호"]:
                prev_case_no = main["사건번호"]
                prev_court = main["법원"]

            # 유효한 물건만 추가 (주소가 있어야 함)
            if main.get("물건주소"):
                if current_item:
                    results.append(current_item)
                current_item = main

        elif n == 3:
            # ─ 상세 행 ─ 이전 메인 행에 병합
            if current_item is not None:
                detail = _parse_detail_row(cells)
                current_item.update(detail)
                results.append(current_item)
                current_item = None
        else:
            # 기타 행 무시
            continue

    # 마지막 아이템 처리
    if current_item:
        results.append(current_item)

    if debug:
        print(f"[ListParser] 파싱 완료: {len(results)}건")

    return results


def get_total_count(page_source: str) -> Optional[int]:
    """페이지에서 전체 결과 수를 추출합니다."""
    soup = BeautifulSoup(page_source, "lxml")
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
