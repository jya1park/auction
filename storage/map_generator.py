"""
경매 데이터 지도 시각화 모듈 (카카오맵)

output/ 디렉토리의 최신 xlsx 파일을 읽어 데이터를 JSON으로 삽입한
단일 HTML 파일을 생성합니다. Geocoding은 브라우저에서 카카오맵 JS SDK로 처리합니다.
"""
import os
import json
import glob
from typing import List, Dict, Optional, Tuple

import config


KAKAO_APP_KEY = "614ddc420a052c47f1b0a7eb2169d862"

# 주소 컬럼 후보 (우선순위 순)
ADDRESS_COLUMNS = ["물건주소", "소재지", "주소", "물건소재지"]

# HTML에 포함할 데이터 컬럼 후보 (있는 것만)
DATA_COLUMNS = [
    "사건번호", "법원", "물건번호",
    "물건주소", "소재지", "주소", "물건소재지",
    "용도", "감정평가액", "감정가",
    "최저입찰가_표시", "최저입찰가", "최저매각가",
    "입찰기일", "매각기일", "진행상태", "상태",
    "유찰횟수", "입찰방법",
]

# 기본 중심 좌표 (수원시)
DEFAULT_LAT = 37.2636
DEFAULT_LNG = 127.0286
DEFAULT_LEVEL = 7

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
    for candidate in ADDRESS_COLUMNS:
        if candidate in headers:
            return candidate
    for h in headers:
        if "소재" in h or "주소" in h:
            return h
    return None


def _build_items_json(data: List[Dict], headers: List[str], addr_col: str) -> str:
    """HTML에 인라인으로 삽입할 JS 배열 문자열을 반환합니다."""
    items = []
    for record in data:
        address = str(record.get(addr_col, "") or "").strip()
        if not address or address == "None":
            continue

        item: Dict = {"addr": address}
        for col in DATA_COLUMNS:
            if col in headers and record.get(col) is not None:
                val = str(record[col]).strip()
                if val and val != "None":
                    item[col] = val

        items.append(item)

    return json.dumps(items, ensure_ascii=False)


def _build_html(items_json: str, total: int, title_suffix: str = "") -> str:
    title = f"경매 물건 지도{title_suffix}"

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Malgun Gothic', sans-serif; }}
    #map {{ width: 100%; height: 100vh; }}
    #panel {{
      position: absolute;
      top: 10px;
      left: 10px;
      z-index: 2;
      background: rgba(255,255,255,0.93);
      padding: 8px 14px;
      border-radius: 6px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.22);
      font-size: 13px;
      font-weight: bold;
      color: #1F4E79;
    }}
    .iw-wrap {{
      padding: 10px 30px 10px 12px;
      font-family: 'Malgun Gothic', sans-serif;
      font-size: 13px;
      min-width: 200px;
      max-width: 300px;
      position: relative;
    }}
    .iw-close {{
      position: absolute;
      top: 6px;
      right: 8px;
      background: none;
      border: none;
      font-size: 15px;
      cursor: pointer;
      color: #888;
      line-height: 1;
      padding: 2px;
    }}
    .iw-close:hover {{ color: #333; }}
    .iw-table {{ border-collapse: collapse; width: 100%; margin-top: 4px; }}
    .iw-table th {{
      text-align: left;
      padding: 2px 10px 2px 0;
      color: #666;
      white-space: nowrap;
      vertical-align: top;
      font-weight: normal;
    }}
    .iw-table td {{
      padding: 2px 0;
      color: #222;
      word-break: break-all;
    }}
  </style>
</head>
<body>
  <div id="map"></div>
  <div id="panel">
    총 {total}건 | 지도 표시: <span id="mapped-count">0</span>건
  </div>

  <script>
    var ITEMS = {items_json};
  </script>
  <script src="//dapi.kakao.com/v2/maps/sdk.js?appkey={KAKAO_APP_KEY}&libraries=services,clusterer"></script>
  <script>
    window.onload = function() {{
        var mapContainer = document.getElementById('map');
        var map = new kakao.maps.Map(mapContainer, {{
          center: new kakao.maps.LatLng({DEFAULT_LAT}, {DEFAULT_LNG}),
          level: {DEFAULT_LEVEL}
        }});

        map.addControl(new kakao.maps.ZoomControl(),    kakao.maps.ControlPosition.RIGHT);
        map.addControl(new kakao.maps.MapTypeControl(), kakao.maps.ControlPosition.TOPRIGHT);

        var geocoder  = new kakao.maps.services.Geocoder();
        var clusterer = new kakao.maps.MarkerClusterer({{
          map: map,
          averageCenter: true,
          minLevel: 4
        }});

        var currentIW = null;
        var mappedCount = 0;
        var bounds = new kakao.maps.LatLngBounds();
        var markerList = [];

        // InfoWindow 닫기 (전역 함수 - 인라인 onclick에서 호출)
        window.closeIW = function() {{
          if (currentIW) {{ currentIW.close(); currentIW = null; }}
        }};

        function buildContent(item) {{
          var LABELS = {{
            '사건번호':      '사건번호',
            '법원':          '법원',
            '물건번호':      '물건번호',
            '물건주소':      '주소',
            '소재지':        '주소',
            '주소':          '주소',
            '물건소재지':    '주소',
            '용도':          '용도',
            '감정평가액':    '감정가',
            '감정가':        '감정가',
            '최저입찰가_표시': '최저매각가',
            '최저입찰가':    '최저매각가',
            '최저매각가':    '최저매각가',
            '입찰기일':      '매각기일',
            '매각기일':      '매각기일',
            '진행상태':      '상태',
            '상태':          '상태',
            '유찰횟수':      '유찰횟수',
          }};
          // 중복 레이블 제거
          var seen = {{}};
          var rows = '';
          Object.keys(LABELS).forEach(function(key) {{
            var label = LABELS[key];
            if (item[key] && !seen[label]) {{
              seen[label] = true;
              rows += '<tr><th>' + label + '</th><td>' + item[key] + '</td></tr>';
            }}
          }});
          return '<div class="iw-wrap">'
               + '<button class="iw-close" onclick="closeIW()">✕</button>'
               + '<table class="iw-table">' + rows + '</table>'
               + '</div>';
        }}

        function addMarker(item, lat, lng) {{
          var pos    = new kakao.maps.LatLng(lat, lng);
          var marker = new kakao.maps.Marker({{ position: pos }});
          var iw     = new kakao.maps.InfoWindow({{
            content: buildContent(item),
            removable: false
          }});

          kakao.maps.event.addListener(marker, 'click', function() {{
            closeIW();
            iw.open(map, marker);
            currentIW = iw;
          }});

          markerList.push(marker);
          bounds.extend(pos);
          mappedCount++;
          document.getElementById('mapped-count').textContent = mappedCount;
        }}

        // 순차 geocoding (카카오 API 부하 분산)
        var idx = 0;
        function processNext() {{
          if (idx >= ITEMS.length) {{
            // 모두 완료 후 bounds 조정
            clusterer.addMarkers(markerList);
            if (markerList.length > 0) {{
              map.setBounds(bounds);
            }}
            return;
          }}
          var item = ITEMS[idx++];
          geocoder.addressSearch(item.addr, function(result, status) {{
            if (status === kakao.maps.services.Status.OK) {{
              addMarker(item, result[0].y, result[0].x);
            }}
            // 다음 아이템 처리 (300ms 간격으로 카카오 API 부하 분산)
            setTimeout(processNext, 300);
          }});
        }}

        processNext();
    }};
  </script>
</body>
</html>
"""


def generate_map(
    xlsx_path: str = None,
    output_path: str = None,
    use_sample: bool = False,
) -> str:
    """
    엑셀 파일을 읽어 카카오맵 HTML을 생성합니다.
    Geocoding은 Python에서 하지 않고 브라우저의 카카오맵 JS SDK가 처리합니다.

    Args:
        xlsx_path: 입력 엑셀 경로 (기본: output/ 최신 xlsx 자동 탐색)
        output_path: 출력 HTML 경로 (기본: output/auction_map.html)
        use_sample: True이면 엑셀 없이 샘플 더미 데이터로 HTML 생성
    Returns:
        생성된 HTML 파일 경로 (실패 시 빈 문자열)
    """
    if output_path is None:
        output_path = os.path.join(_get_output_dir(), "auction_map.html")

    if use_sample:
        print("[MapGen] 샘플 데이터로 지도 생성 중...")
        data = SAMPLE_DATA
        headers = list(data[0].keys())
        addr_col = _find_address_column(headers)
        items_json = _build_items_json(data, headers, addr_col)
        html_content = _build_html(items_json, len(data), " (샘플)")
        label = "샘플 "
    else:
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

        print(f"[MapGen] 주소 컬럼: '{addr_col}', {len(data)}건 데이터 삽입 (geocoding은 브라우저에서 처리)")
        items_json = _build_items_json(data, headers, addr_col)
        html_content = _build_html(items_json, len(data))
        label = ""

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"[MapGen] {label}지도 생성 완료: {output_path}")
    return output_path


def upload_to_github(
    filepath: str,
    token: str,
    owner: str = "jya1park",
    repo: str = "auction",
    branch: str = "main",
) -> bool:
    """GitHub REST API로 파일을 업로드(또는 갱신)합니다."""
    import base64
    import urllib.request
    import urllib.error

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

    sha = None
    req_get = urllib.request.Request(api_url, headers=req_headers, method="GET")
    try:
        with urllib.request.urlopen(req_get, timeout=10) as resp:
            sha = json.loads(resp.read().decode("utf-8")).get("sha")
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

    req_put = urllib.request.Request(
        api_url,
        data=json.dumps(payload).encode("utf-8"),
        headers=req_headers,
        method="PUT",
    )
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
