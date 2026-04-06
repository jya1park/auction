"""
데이터 저장 모듈
CSV와 Excel 형식으로 수집 데이터를 저장합니다.
"""
import os
import csv
from datetime import datetime
from typing import List, Dict

import config


def ensure_output_dir() -> str:
    """출력 디렉토리를 생성하고 경로를 반환합니다."""
    out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), config.OUTPUT_DIR)
    os.makedirs(out_dir, exist_ok=True)
    return out_dir


def get_timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def save_csv(data: List[Dict], filename: str = None) -> str:
    """
    데이터를 CSV 파일로 저장합니다.

    Args:
        data: 저장할 딕셔너리 목록
        filename: 파일명 (없으면 타임스탬프 자동 생성)
    Returns:
        저장된 파일 경로
    """
    if not data:
        print("[Exporter] 저장할 데이터가 없습니다.")
        return ""

    out_dir = ensure_output_dir()
    if not filename:
        filename = f"courtauction_{get_timestamp()}.csv"

    filepath = os.path.join(out_dir, filename)

    # 모든 딕셔너리의 키를 합쳐 헤더 생성 (순서 유지)
    fieldnames = []
    seen = set()
    for row in data:
        for k in row.keys():
            if k not in seen:
                fieldnames.append(k)
                seen.add(k)

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(data)

    print(f"[Exporter] CSV 저장 완료: {filepath} ({len(data)}건)")
    return filepath


def save_excel(data: List[Dict], filename: str = None) -> str:
    """
    데이터를 Excel 파일로 저장합니다.
    - 컬럼 너비 자동 조정
    - 금액 컬럼에 만원 단위 추가
    - 헤더 스타일 적용

    Args:
        data: 저장할 딕셔너리 목록
        filename: 파일명 (없으면 타임스탬프 자동 생성)
    Returns:
        저장된 파일 경로
    """
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
    except ImportError:
        print("[Exporter] openpyxl이 설치되지 않았습니다. pip install openpyxl")
        return ""

    if not data:
        print("[Exporter] 저장할 데이터가 없습니다.")
        return ""

    out_dir = ensure_output_dir()
    if not filename:
        filename = f"courtauction_{get_timestamp()}.xlsx"

    filepath = os.path.join(out_dir, filename)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "경매목록"

    # 헤더 구성 (만원 단위 컬럼 추가)
    fieldnames = []
    seen = set()
    for row in data:
        for k in row.keys():
            if k not in seen:
                fieldnames.append(k)
                seen.add(k)

    # 금액 원 컬럼 뒤에 만원 컬럼 삽입
    extended_fields = []
    for f in fieldnames:
        extended_fields.append(f)
        if f.endswith("_원") and f.replace("_원", "") in fieldnames:
            pass  # 이미 _원 컬럼이면 건너뜀
        elif not f.endswith("_원") and f + "_원" not in fieldnames:
            # 금액처럼 보이는 컬럼에 만원 단위 추가 (비율/횟수 컬럼 제외)
            if any(kw in f for kw in ["감정가", "최저입찰가", "낙찰가"]) and not f.endswith("율") and not f.endswith("_표시"):
                extended_fields.append(f + "_만원")

    # 헤더 스타일
    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, name="맑은 고딕", size=10)
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )

    # 헤더 행 작성
    for col_idx, field in enumerate(extended_fields, 1):
        cell = ws.cell(row=1, column=col_idx, value=field)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = header_align
        cell.border = thin_border

    ws.row_dimensions[1].height = 25

    # 데이터 행 작성
    data_font = Font(name="맑은 고딕", size=9)
    data_align = Alignment(vertical="center")
    money_align = Alignment(horizontal="right", vertical="center")
    alt_fill = PatternFill(start_color="EEF2F7", end_color="EEF2F7", fill_type="solid")

    for row_idx, row_data in enumerate(data, 2):
        is_alt = (row_idx % 2 == 0)
        for col_idx, field in enumerate(extended_fields, 1):
            # 만원 단위 컬럼 처리
            if field.endswith("_만원"):
                base_field = field.replace("_만원", "") + "_원"
                raw_val = row_data.get(base_field)
                if raw_val is None:
                    base_field2 = field.replace("_만원", "")
                    from crawler.list_parser import parse_amount
                    raw_val = parse_amount(str(row_data.get(base_field2, "")))
                if raw_val:
                    try:
                        value = int(raw_val) // 10_000
                    except (TypeError, ValueError):
                        value = None
                else:
                    value = None
            else:
                value = row_data.get(field)

            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.font = data_font
            cell.border = thin_border

            # 금액 컬럼은 오른쪽 정렬
            if any(kw in field for kw in ["_원", "_만원", "감정가", "최저입찰가", "낙찰가"]):
                cell.alignment = money_align
            else:
                cell.alignment = data_align

            if is_alt:
                cell.fill = alt_fill

        ws.row_dimensions[row_idx].height = 18

    # 컬럼 너비 자동 조정
    for col_idx, field in enumerate(extended_fields, 1):
        col_letter = get_column_letter(col_idx)
        # 헤더 너비 계산 (한글 2배)
        header_len = sum(2 if ord(c) > 127 else 1 for c in field)
        # 데이터 최대 너비
        max_data_len = 0
        for row_data in data:
            val = str(row_data.get(field, ""))
            val_len = sum(2 if ord(c) > 127 else 1 for c in val)
            max_data_len = max(max_data_len, val_len)
        col_width = max(header_len + 2, min(max_data_len + 2, 40))
        ws.column_dimensions[col_letter].width = col_width

    # 헤더 행 고정
    ws.freeze_panes = "A2"

    # 자동 필터
    ws.auto_filter.ref = f"A1:{get_column_letter(len(extended_fields))}1"

    wb.save(filepath)
    print(f"[Exporter] Excel 저장 완료: {filepath} ({len(data)}건)")
    return filepath


def print_summary(data: List[Dict]):
    """수집 데이터의 요약 통계를 출력합니다."""
    if not data:
        print("데이터가 없습니다.")
        return

    print("\n" + "="*60)
    print(f"수집 결과 요약")
    print("="*60)
    print(f"총 수집 건수: {len(data)}건")

    # 감정가 통계
    amounts = [v for v in (d.get("감정가_원") for d in data) if v]
    if amounts:
        print(f"감정가 범위: {min(amounts):,}원 ~ {max(amounts):,}원")
        print(f"감정가 평균: {sum(amounts)//len(amounts):,}원")

    # 최저입찰가 통계
    min_bids = [v for v in (d.get("최저입찰가_원") for d in data) if v]
    if min_bids:
        print(f"최저입찰가 평균: {sum(min_bids)//len(min_bids):,}원")

    # 입찰기일 분포
    dates = {}
    for d in data:
        date = d.get("입찰기일", "")
        if date:
            dates[date] = dates.get(date, 0) + 1
    if dates:
        print(f"\n입찰기일 분포 (상위 5):")
        for date, cnt in sorted(dates.items(), key=lambda x: -x[1])[:5]:
            print(f"  {date}: {cnt}건")

    print("="*60)
