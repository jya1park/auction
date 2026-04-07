"""
데이터 저장 모듈
CSV와 Excel 형식으로 수집 데이터를 저장합니다.
"""
import os
import csv
from datetime import datetime
from typing import List, Dict

import config

# 고정 Excel 파일명 (항상 이 파일에 누적 업데이트)
EXCEL_FIXED_FILENAME = "courtauction_data.xlsx"


def ensure_output_dir() -> str:
    """출력 디렉토리를 생성하고 경로를 반환합니다."""
    out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), config.OUTPUT_DIR)
    os.makedirs(out_dir, exist_ok=True)
    return out_dir


def get_timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def get_datetime_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


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


def update_excel(data: List[Dict]) -> str:
    """
    고정 Excel 파일(courtauction_data.xlsx)에 데이터를 누적 업데이트합니다.

    - 파일이 없으면 새로 생성
    - 파일이 있으면 기존 데이터와 병합 (사건번호+물건번호 기준 upsert)
    - 모든 행에 '업데이트일시' 열 기록
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
    filepath = os.path.join(out_dir, EXCEL_FIXED_FILENAME)
    now_str = get_datetime_str()

    # 새 데이터에 업데이트일시 추가
    for row in data:
        row["업데이트일시"] = now_str

    # 기존 파일에서 데이터 로드
    existing_data = []
    if os.path.exists(filepath):
        try:
            wb_old = openpyxl.load_workbook(filepath)
            ws_old = wb_old.active
            headers = [cell.value for cell in ws_old[1]]
            for row in ws_old.iter_rows(min_row=2, values_only=True):
                if any(v is not None for v in row):
                    existing_data.append(dict(zip(headers, row)))
            print(f"[Exporter] 기존 데이터 로드: {len(existing_data)}건")
        except Exception as e:
            print(f"[Exporter] 기존 파일 로드 실패 (새로 생성): {e}")
            existing_data = []

    # 사건번호+물건번호 기준으로 upsert
    key_fn = lambda r: (str(r.get("사건번호", "")), str(r.get("물건번호", "")))
    existing_map = {key_fn(r): r for r in existing_data}
    new_count = 0
    update_count = 0
    for row in data:
        k = key_fn(row)
        if k in existing_map:
            existing_map[k] = row  # 업데이트
            update_count += 1
        else:
            existing_map[k] = row  # 신규 추가
            new_count += 1

    merged = list(existing_map.values())
    print(f"[Exporter] 신규 {new_count}건 추가, {update_count}건 업데이트 → 총 {len(merged)}건")

    # 헤더 구성 (업데이트일시를 첫 번째 컬럼으로)
    fieldnames = ["업데이트일시"]
    seen = {"업데이트일시"}
    for row in merged:
        for k in row.keys():
            if k not in seen:
                fieldnames.append(k)
                seen.add(k)

    # 만원 단위 컬럼 삽입
    extended_fields = []
    for f in fieldnames:
        extended_fields.append(f)
        if not f.endswith("_원") and f + "_원" not in fieldnames:
            if any(kw in f for kw in ["감정가", "최저입찰가", "낙찰가"]) and not f.endswith("율") and not f.endswith("_표시"):
                extended_fields.append(f + "_만원")

    # 스타일 정의
    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, name="맑은 고딕", size=10)
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    date_fill = PatternFill(start_color="2E7D32", end_color="2E7D32", fill_type="solid")  # 업데이트일시 열 강조
    thin_border = Border(
        left=Side(style="thin"), right=Side(style="thin"),
        top=Side(style="thin"), bottom=Side(style="thin"),
    )
    alt_fill = PatternFill(start_color="EEF2F7", end_color="EEF2F7", fill_type="solid")
    data_font = Font(name="맑은 고딕", size=9)
    data_align = Alignment(vertical="center")
    money_align = Alignment(horizontal="right", vertical="center")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "경매목록"

    # 헤더 행
    for col_idx, field in enumerate(extended_fields, 1):
        cell = ws.cell(row=1, column=col_idx, value=field)
        cell.fill = date_fill if field == "업데이트일시" else header_fill
        cell.font = header_font
        cell.alignment = header_align
        cell.border = thin_border
    ws.row_dimensions[1].height = 25

    # 데이터 행 (최신 업데이트일시 기준 내림차순 정렬)
    merged_sorted = sorted(merged, key=lambda r: str(r.get("업데이트일시", "")), reverse=True)
    for row_idx, row_data in enumerate(merged_sorted, 2):
        is_alt = (row_idx % 2 == 0)
        for col_idx, field in enumerate(extended_fields, 1):
            if field.endswith("_만원"):
                base_field = field.replace("_만원", "") + "_원"
                raw_val = row_data.get(base_field)
                if raw_val is None:
                    from crawler.list_parser import parse_amount
                    raw_val = parse_amount(str(row_data.get(field.replace("_만원", ""), "")))
                value = int(raw_val) // 10_000 if raw_val else None
            else:
                value = row_data.get(field)

            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.font = data_font
            cell.border = thin_border
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
        header_len = sum(2 if ord(c) > 127 else 1 for c in field)
        max_data_len = 0
        for row_data in merged_sorted:
            val = str(row_data.get(field, ""))
            val_len = sum(2 if ord(c) > 127 else 1 for c in val)
            max_data_len = max(max_data_len, val_len)
        ws.column_dimensions[col_letter].width = max(header_len + 2, min(max_data_len + 2, 40))

    ws.freeze_panes = "B2"  # 업데이트일시 열 고정
    ws.auto_filter.ref = f"A1:{get_column_letter(len(extended_fields))}1"

    wb.save(filepath)
    print(f"[Exporter] Excel 업데이트 완료: {filepath} (총 {len(merged)}건)")
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
