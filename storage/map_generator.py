"""
경매 데이터 지도 시각화 모듈

output/ 디렉토리의 최신 xlsx 파일을 읽어
각 물건의 위치를 Leaflet.js 지도에 마커로 표시하는 HTML 파일을 생성합니다.
"""
import os
import re
import json
import time
import glob
import urllib.request
import urllib.parse
from typing import List, Dict, Optional, Tuple

import config


# 주소 컬럼 후보 (우선순위 순)
ADDRESS_COLUMNS = ["물건주소", "소재지", "주소", "물건소재지"]

# 팝업에 표시할 컬럼 후보 (있는 것만 표시)
POPUP_COLUMNS = [
    "사건번호", "법원", "물건번호",
    "물건주소", "소재지", "주소", "물건소재지",
    "용도", "감정평가액", "감정가",
    "최저입찰가_표시", "최저입찰가", "최저매각가",
    "입찰기일", "매각기일", "진행상태", "상태",
    "유찰횟수", "입찰방법",
]

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "courtauction-map/1.0"
GEOCODE_DELAY = 1.0  # 초 (rate limit 준수)

# 기본 중심 좌표 (수원시)
DEFAULT_LAT = 37.2636
DEFAULT_LNG = 127.0286
DEFAULT_ZOOM = 12

# 샘플 데이터 (use_sample=True 시 사용)
SAMPLE_DATA = [
    {
        "사건번호": "2024타경10001",
        "물건번호": "1",
        "물건주소": "경기도 수원시 팔달구 효원로 1",
        "용도": "아파트",
        "감정평가액": "500,000,000",
        "최저입찰가_표시": "350,000,000(70%)",
        "입찰기일": "2024-03-15",
        "진행상태": "진행중",
    },
    {
        "사건번호": "2024타경10002",
        "물건번호": "1",
        "물건주소": "경기도 수원시 영통구 영통로 234",
        "용도": "아파트",
        "감정평가액": "450,000,000",
        "최저입찰가_표시": "315,000,000(70%)",
        "입찰기일": "2024-03-22",
        "진행상태": "진행중",
    },
    {
        "사건번호": "2024타경10003",
        "물건번호": "1",
        "물건주소": "경기도 수원시 권선구 권선로 921",
        "용도": "아파트",
        "감정평가액": "380,000,000",
        "최저입찰가_표시": "266,000,000(70%)",
        "입찰기일": "2024-04-05",
        "진행상태": "유찰",
    },
    {
        "사건번호": "2024타경10004",
        "물건번호": "1",
        "물건주소": "경기도 용인시 기흥구 구성로 357",
        "용도": "근린시설",
        "감정평가액": "980,000,000",
        "최저입찰가_표시": "686,000,000(70%)",
        "입찰기일": "2024-04-14",
        "진행상태": "진행중",
    },
    {
        "사건번호": "2024타경10005",
        "물건번호": "1",
        "물건주소": "경기도 화성시 동탄반석로 142",
        "용도": "아파트",
        "감정평가액": "620,000,000",
        "최저입찰가_표시": "434,000,000(70%)",
        "입찰기일": "2024-04-19",
        "진행상태": "진행중",
    },
]


def _get_output_dir() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), config.OUTPUT_DIR)


def _find_latest_xlsx() -> str:
    """output/ 디렉토리에서 가장 최근 xlsx 파일을 반환합니다 (임시파일 제외)."""
    out_dir = _get_output_dir()
    # ~$ 로 시작하는 임시 파일 제외
    candidates = [
        f for f in glob.glob(os.path.join(out_dir, "*.xlsx"))
        if not os.path.basename(f).startswith("~$")
    ]
    if not candidates:
        return os.path.join(out_dir, "courtauction_data.xlsx")
    return max(candidates, key=os.path.getmtime)


def _read_excel(xlsx_path: str) -> Tuple[List[str], List[Dict]]:
    """경매목록 시트에서 헤더와 데이터를 읽어 반환합니다."""
    try:
        import openpyxl
    except ImportError:
        raise ImportError("openpyxl이 설치되지 않았습니다. pip install openpyxl")

    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=True)

    # "경매목록" 시트 우선, 없으면 첫 번째 시트
    if "경매목록" in wb.sheetnames:
        ws = wb["경매목록"]
    else:
        ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    wb.close()

    if not rows:
        return [], []

    headers = [str(h) if h is not None else "" for h in rows[0]]
    data = []
    for row in rows[1:]:
        if all(v is None for v in row):
            continue
        record = {headers[i]: row[i] for i in range(len(headers)) if headers[i]}
        data.append(record)

    return headers, data


def _find_address_column(headers: List[str]) -> Optional[str]:
    """주소 컬럼명을 우선순위에 따라 탐색합니다."""
    for candidate in ADDRESS_COLUMNS:
        if candidate in headers:
            return candidate
    # 부분 매칭 fallback
    for h in headers:
        if "소재" in h or "주소" in h:
            return h
    return None


def _clean_address(address: str) -> str:
    """
    geocoding용 주소 정제:
    - '[...]' 이후 건물 상세 설명 제거
    - '(' 이후 건물명 제거
    - 동/호수 등 세부 번지 제거 후 도로명+번지까지만 남김
    """
    addr = str(address).strip()

    # '[' 이후 제거 (건물 구조/면적 설명)
    addr = addr.split("[")[0].strip()

    # '(' 이후 제거 (건물명 등)
    addr = addr.split("(")[0].strip()

    # 개행 이후 제거
    addr = addr.split("\n")[0].strip()

    return addr


def _shorten_address(address: str) -> List[str]:
    """
    주소를 단계적으로 줄인 후보 목록을 반환합니다.
    예) "경기도 수원시 팔달구 효원로 1 3층310호"
      → ["경기도 수원시 팔달구 효원로 1", "경기도 수원시 팔달구 효원로", "경기도 수원시 팔달구"]
    """
    parts = address.split()
    candidates = []

    # 숫자+층/호/동 패턴 이전까지 잘라내기
    clean_end = len(parts)
    for i, p in enumerate(parts):
        if re.search(r'\d+[층호동]$', p) and i >= 4:
            clean_end = i
            break

    if clean_end < len(parts):
        candidates.append(" ".join(parts[:clean_end]))

    # 원본 전체
    candidates.append(address)

    # 뒤에서 한 토큰씩 제거 (최소 3토큰 유지)
    for n in range(len(parts) - 1, 2, -1):
        shortened = " ".join(parts[:n])
        if shortened not in candidates:
            candidates.append(shortened)

    return candidates


def _geocode(address: str) -> Optional[Tuple[float, float]]:
    """
    Nominatim API로 주소를 좌표로 변환합니다.
    1. 정제된 전체 주소로 시도
    2. 실패 시 단계적으로 주소를 줄여 재시도
    실패 시 None 반환.
    """
    if not address or not str(address).strip():
        return None

    cleaned = _clean_address(address)
    candidates = _shorten_address(cleaned)

    for attempt, query in enumerate(candidates):
        if not query.strip():
            continue
        params = urllib.parse.urlencode({
            "q": query,
            "format": "json",
            "limit": 1,
            "countrycodes": "kr",
        })
        url = f"{NOMINATIM_URL}?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                results = json.loads(resp.read().decode("utf-8"))
            if results:
                if attempt > 0:
                    print(f"      → 재시도 성공 (단계 {attempt}): '{query}'")
                return float(results[0]["lat"]), float(results[0]["lon"])
        except Exception as e:
            print(f"    [MapGen] geocoding 오류 ('{query[:30]}'): {e}")

        # 재시도 전 딜레이
        if attempt < len(candidates) - 1:
            time.sleep(GEOCODE_DELAY)

    return None


def _build_popup_fields(record: Dict, headers: List[str]) -> Dict[str, str]:
    """팝업에 표시할 필드만 추출합니다."""
    fields = {}
    for col in POPUP_COLUMNS:
        if col in headers and record.get(col) is not None:
            val = str(record[col]).strip()
            if val and val != "None":
                fields[col] = val
    return fields


def _format_popup_html(fields: Dict[str, str]) -> str:
    rows_html = "".join(
        f"<tr><th>{k}</th><td>{v}</td></tr>"
        for k, v in fields.items()
    )
    return f"<table class='popup-table'>{rows_html}</table>"


def _build_html(markers: List[Dict], title_suffix: str = "") -> str:
    """마커 데이터를 포함한 단일 HTML 파일 문자열을 반환합니다."""
    markers_json = json.dumps(markers, ensure_ascii=False, indent=2)
    total = len(markers)
    title = f"경매 물건 지도{title_suffix}"

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
  <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.css" />
  <link rel="stylesheet" href="https://unpkg.com/leaflet.markercluster@1.5.3/dist/MarkerCluster.Default.css" />
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Malgun Gothic', sans-serif; }}
    #map {{ width: 100%; height: 100vh; }}
    .info-box {{
      position: absolute;
      top: 10px;
      right: 10px;
      z-index: 1000;
      background: rgba(255,255,255,0.92);
      padding: 10px 16px;
      border-radius: 6px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.25);
      font-size: 14px;
      font-weight: bold;
      color: #1F4E79;
      pointer-events: none;
    }}
    .popup-table {{ border-collapse: collapse; font-size: 13px; min-width: 220px; }}
    .popup-table th {{
      text-align: left;
      padding: 3px 10px 3px 0;
      color: #555;
      white-space: nowrap;
      vertical-align: top;
    }}
    .popup-table td {{
      padding: 3px 4px;
      color: #222;
      max-width: 240px;
      word-break: break-all;
    }}
  </style>
</head>
<body>
  <div id="map"></div>
  <div class="info-box">총 {total}건</div>

  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script src="https://unpkg.com/leaflet.markercluster@1.5.3/dist/leaflet.markercluster.js"></script>
  <script>
    const markers = {markers_json};

    const map = L.map('map').setView([{DEFAULT_LAT}, {DEFAULT_LNG}], {DEFAULT_ZOOM});

    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 19
    }}).addTo(map);

    const cluster = L.markerClusterGroup();

    markers.forEach(function(item) {{
      const marker = L.marker([item.lat, item.lng]);
      marker.bindPopup(item.popup, {{ maxWidth: 320 }});
      cluster.addLayer(marker);
    }});

    map.addLayer(cluster);

    if (markers.length > 0) {{
      const group = L.featureGroup(
        markers.map(function(m) {{ return L.marker([m.lat, m.lng]); }})
      );
      map.fitBounds(group.getBounds().pad(0.15));
    }}
  </script>
</body>
</html>
"""


def _geocode_records(
    data: List[Dict],
    addr_col: str,
    headers: List[str],
) -> List[Dict]:
    """데이터 목록을 geocoding하여 마커 목록을 반환합니다."""
    markers = []
    total = len(data)
    for i, record in enumerate(data):
        address = record.get(addr_col, "")
        coords = _geocode(address)
        if coords is None:
            print(f"  [{i+1}/{total}] 스킵 (geocoding 실패): {str(address)[:50]}")
        else:
            lat, lng = coords
            fields = _build_popup_fields(record, headers)
            popup_html = _format_popup_html(fields)
            markers.append({"lat": lat, "lng": lng, "popup": popup_html})
            print(f"  [{i+1}/{total}] OK ({lat:.4f}, {lng:.4f}): {str(address)[:50]}")

        if i < total - 1:
            time.sleep(GEOCODE_DELAY)

    return markers


def generate_map(
    xlsx_path: str = None,
    output_path: str = None,
    use_sample: bool = False,
) -> str:
    """
    엑셀 파일을 읽어 지도 HTML을 생성합니다.

    Args:
        xlsx_path: 입력 엑셀 경로 (기본: output/ 최신 xlsx 자동 탐색)
        output_path: 출력 HTML 경로 (기본: output/auction_map.html)
        use_sample: True이면 엑셀 없이 샘플 더미 데이터로 HTML 생성
    Returns:
        생성된 HTML 파일 경로 (실패 시 빈 문자열)
    """
    if output_path is None:
        output_path = os.path.join(_get_output_dir(), "auction_map.html")

    # 샘플 모드
    if use_sample:
        print("[MapGen] 샘플 데이터로 지도 생성 중...")
        sample_headers = list(SAMPLE_DATA[0].keys())
        addr_col = _find_address_column(sample_headers)
        markers = _geocode_records(SAMPLE_DATA, addr_col, sample_headers)
        if not markers:
            print("[MapGen] 샘플 geocoding 실패.")
            return ""
        html_content = _build_html(markers, " (샘플)")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"[MapGen] 샘플 지도 생성 완료: {output_path} ({len(markers)}개 마커)")
        return output_path

    # 엑셀 경로 자동 탐색
    if xlsx_path is None:
        xlsx_path = _find_latest_xlsx()

    print(f"[MapGen] 엑셀 읽기: {xlsx_path}")
    if not os.path.exists(xlsx_path):
        print(f"[MapGen] 파일 없음: {xlsx_path}")
        return ""

    headers, data = _read_excel(xlsx_path)
    if not data:
        print("[MapGen] 데이터가 없습니다.")
        return ""

    addr_col = _find_address_column(headers)
    if not addr_col:
        print(f"[MapGen] 주소 컬럼을 찾을 수 없습니다. (헤더: {headers})")
        return ""

    print(f"[MapGen] 주소 컬럼: '{addr_col}', 총 {len(data)}건 geocoding 시작")

    markers = _geocode_records(data, addr_col, headers)

    if not markers:
        print("[MapGen] 유효한 좌표가 없어 지도 생성을 건너뜁니다.")
        return ""

    html_content = _build_html(markers)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"[MapGen] 지도 생성 완료: {output_path} ({len(markers)}개 마커)")
    return output_path


def upload_to_github(
    filepath: str,
    token: str,
    owner: str = "jya1park",
    repo: str = "auction",
    branch: str = "main",
) -> bool:
    """
    GitHub REST API를 사용해 파일을 업로드(또는 갱신)합니다.

    Args:
        filepath: 업로드할 로컬 파일 경로
        token: GitHub Personal Access Token
        owner: 저장소 소유자
        repo: 저장소 이름
        branch: 대상 브랜치
    Returns:
        성공 여부
    """
    import base64

    filename = os.path.basename(filepath)
    remote_path = f"storage/{filename}"
    api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{remote_path}"

    with open(filepath, "rb") as f:
        content_b64 = base64.b64encode(f.read()).decode("utf-8")

    req_headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # 기존 파일 SHA 조회 (갱신 시 필요)
    sha = None
    req_get = urllib.request.Request(api_url, headers=req_headers, method="GET")
    try:
        with urllib.request.urlopen(req_get, timeout=10) as resp:
            existing = json.loads(resp.read().decode("utf-8"))
            sha = existing.get("sha")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            print(f"[MapGen] GitHub SHA 조회 오류: {e}")
            return False
    except Exception as e:
        print(f"[MapGen] GitHub 연결 오류: {e}")
        return False

    payload: Dict = {
        "message": f"feat: update {filename}",
        "content": content_b64,
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha

    body = json.dumps(payload).encode("utf-8")
    req_put = urllib.request.Request(api_url, data=body, headers=req_headers, method="PUT")
    try:
        with urllib.request.urlopen(req_put, timeout=15) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            html_url = result.get("content", {}).get("html_url", "")
            print(f"[MapGen] GitHub 업로드 완료: {html_url}")
            return True
    except urllib.error.HTTPError as e:
        print(f"[MapGen] GitHub 업로드 실패 ({e.code}): {e.read().decode()}")
        return False
    except Exception as e:
        print(f"[MapGen] GitHub 업로드 오류: {e}")
        return False
