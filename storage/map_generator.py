"""
경매 데이터 지도 시각화 모듈

output/courtauction_data.xlsx의 경매목록 시트를 읽어
각 물건의 위치를 Leaflet.js 지도에 마커로 표시하는 HTML 파일을 생성합니다.
"""
import os
import json
import time
import urllib.request
import urllib.parse
from typing import List, Dict, Optional, Tuple

import config


# 주소 컬럼 후보 (우선순위 순)
ADDRESS_COLUMNS = ["소재지", "주소", "물건소재지"]

# 팝업에 표시할 컬럼 후보 (있는 것만 표시)
POPUP_COLUMNS = ["사건번호", "물건번호", "소재지", "주소", "물건소재지",
                 "감정가", "최저입찰가", "최저매각가", "매각기일", "입찰기일",
                 "입찰방법", "진행상태", "상태"]

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "courtauction-map/1.0"
GEOCODE_DELAY = 1.0  # 초

# 기본 중심 좌표 (수원시)
DEFAULT_LAT = 37.2636
DEFAULT_LNG = 127.0286
DEFAULT_ZOOM = 12


def _get_output_dir() -> str:
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), config.OUTPUT_DIR)


def _find_xlsx_path() -> str:
    return os.path.join(_get_output_dir(), "courtauction_data.xlsx")


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


def _geocode(address: str) -> Optional[Tuple[float, float]]:
    """Nominatim API로 주소를 좌표로 변환합니다. 실패 시 None 반환."""
    if not address or not str(address).strip():
        return None

    query = str(address).strip()
    params = urllib.parse.urlencode({"q": query, "format": "json", "limit": 1})
    url = f"{NOMINATIM_URL}?{params}"

    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            results = json.loads(resp.read().decode("utf-8"))
        if results:
            return float(results[0]["lat"]), float(results[0]["lon"])
    except Exception as e:
        print(f"    [MapGen] geocoding 오류 ({query[:30]}...): {e}")
    return None


def _build_popup_fields(record: Dict, headers: List[str]) -> Dict[str, str]:
    """팝업에 표시할 필드만 추출합니다."""
    fields = {}
    for col in POPUP_COLUMNS:
        if col in headers and record.get(col) is not None:
            fields[col] = str(record[col])
    return fields


def _format_popup_html(fields: Dict[str, str]) -> str:
    rows = "".join(
        f"<tr><th>{k}</th><td>{v}</td></tr>"
        for k, v in fields.items()
    )
    return f"<table class='popup-table'>{rows}</table>"


def _build_html(markers: List[Dict]) -> str:
    """마커 데이터를 포함한 단일 HTML 파일 문자열을 반환합니다."""
    markers_json = json.dumps(markers, ensure_ascii=False, indent=2)
    total = len(markers)

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>경매 물건 지도</title>
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
    .popup-table {{ border-collapse: collapse; font-size: 13px; min-width: 200px; }}
    .popup-table th {{
      text-align: left;
      padding: 3px 8px 3px 0;
      color: #555;
      white-space: nowrap;
    }}
    .popup-table td {{
      padding: 3px 4px;
      color: #222;
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
      marker.bindPopup(item.popup);
      cluster.addLayer(marker);
    }});

    map.addLayer(cluster);

    // 마커가 있으면 전체가 보이도록 뷰 조정
    if (markers.length > 0) {{
      const group = L.featureGroup(
        markers.map(function(m) {{ return L.marker([m.lat, m.lng]); }})
      );
      map.fitBounds(group.getBounds().pad(0.1));
    }}
  </script>
</body>
</html>
"""


def generate_map(xlsx_path: str = None, output_path: str = None) -> str:
    """
    엑셀 파일을 읽어 지도 HTML을 생성합니다.

    Args:
        xlsx_path: 입력 엑셀 경로 (기본: output/courtauction_data.xlsx)
        output_path: 출력 HTML 경로 (기본: output/auction_map.html)
    Returns:
        생성된 HTML 파일 경로 (실패 시 빈 문자열)
    """
    if xlsx_path is None:
        xlsx_path = _find_xlsx_path()
    if output_path is None:
        output_path = os.path.join(_get_output_dir(), "auction_map.html")

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

    markers = []
    for i, record in enumerate(data):
        address = record.get(addr_col, "")
        coords = _geocode(address)
        if coords is None:
            print(f"  [{i+1}/{len(data)}] 스킵 (geocoding 실패): {str(address)[:40]}")
        else:
            lat, lng = coords
            fields = _build_popup_fields(record, headers)
            popup_html = _format_popup_html(fields)
            markers.append({"lat": lat, "lng": lng, "popup": popup_html})
            print(f"  [{i+1}/{len(data)}] OK ({lat:.4f}, {lng:.4f}): {str(address)[:40]}")

        # 마지막 항목이 아니면 딜레이
        if i < len(data) - 1:
            time.sleep(GEOCODE_DELAY)

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

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # 기존 파일 SHA 조회 (갱신 시 필요)
    sha = None
    req_get = urllib.request.Request(api_url, headers=headers, method="GET")
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
        "message": f"Add/update {filename} via courtauction-map",
        "content": content_b64,
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha

    body = json.dumps(payload).encode("utf-8")
    req_put = urllib.request.Request(api_url, data=body, headers=headers, method="PUT")
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
