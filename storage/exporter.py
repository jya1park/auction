"""
데이터 저장 모듈
CSV 형식으로 수집 데이터를 저장합니다. (누적 upsert by 사건번호+물건번호)
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
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _upsert_csv(data: List[Dict], filepath: str, key_fields: List[str]) -> str:
    """
    CSV 파일에 데이터를 누적 upsert합니다.
    key_fields 조합이 같으면 덮어쓰고, 없으면 추가합니다.
    """
    existing: dict = {}
    existing_fieldnames: list = []

    if os.path.exists(filepath):
        with open(filepath, "r", newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            existing_fieldnames = list(reader.fieldnames or [])
            for row in reader:
                key = tuple(row.get(k, "") for k in key_fields)
                existing[key] = dict(row)

    # 업데이트일시 추가 후 upsert
    now = get_timestamp()
    for row in data:
        row = dict(row)
        row["업데이트일시"] = now
        key = tuple(row.get(k, "") for k in key_fields)
        existing[key] = row

    # 전체 fieldnames 재구성 (기존 순서 유지 후 신규 추가)
    all_rows = list(existing.values())
    fieldnames = list(existing_fieldnames)
    seen = set(fieldnames)
    for row in all_rows:
        for k in row.keys():
            if k not in seen:
                fieldnames.append(k)
                seen.add(k)

    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_rows)

    return filepath


def save_list_csv(data: List[Dict]) -> str:
    """
    경매목록을 output/courtauction_list.csv 에 누적 저장합니다.
    upsert key: 사건번호 + 물건번호
    """
    if not data:
        print("[Exporter] 저장할 데이터가 없습니다.")
        return ""

    out_dir = ensure_output_dir()
    filepath = os.path.join(out_dir, "courtauction_list.csv")
    _upsert_csv(data, filepath, ["사건번호", "물건번호"])
    total = sum(1 for _ in open(filepath, encoding="utf-8-sig")) - 1  # 헤더 제외
    print(f"[Exporter] 경매목록 CSV 저장 완료: {filepath} (이번 {len(data)}건, 누적 {total}건)")
    return filepath


def save_result_csv(data: List[Dict]) -> str:
    """
    매각결과를 output/courtauction_result.csv 에 누적 저장합니다.
    upsert key: 사건번호 + 물건번호
    """
    if not data:
        print("[Exporter] 저장할 데이터가 없습니다.")
        return ""

    out_dir = ensure_output_dir()
    filepath = os.path.join(out_dir, "courtauction_result.csv")
    _upsert_csv(data, filepath, ["사건번호", "물건번호"])
    total = sum(1 for _ in open(filepath, encoding="utf-8-sig")) - 1
    print(f"[Exporter] 매각결과 CSV 저장 완료: {filepath} (이번 {len(data)}건, 누적 {total}건)")
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
