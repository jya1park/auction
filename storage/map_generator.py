"""
경매 데이터 지도 시각화 모듈 (Leaflet.js + Kakao REST API)

Python에서 Kakao REST API로 geocoding 후 결과를 HTML에 임베드.
Leaflet.js + OpenStreetMap 타일로 file:// 프로토콜에서도 작동.
캐시: output/geocode_cache.json
"""
import os
import json
import glob
import time
import urllib.request
import urllib.error
import urllib.parse
from typing import List, Dict, Optional, Tuple

import config


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
        "진행상태": "유찰",
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
        "진행상태": "낙찰",
    },
]


# ─────────────────────────────────────────
# 내부 헬퍼
# ─────────────────────────────────────────

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


# ─────────────────────────────────────────
# Geocoding (Kakao REST API + 캐시)
# ─────────────────────────────────────────

def _get_cache_path() -> str:
    return os.path.join(_get_output_dir(), "geocode_cache.json")


def _load_geocode_cache() -> Dict:
    path = _get_cache_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save_geocode_cache(cache: Dict) -> None:
    path = _get_cache_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def _geocode_rest(address: str, api_key: str) -> Optional[Tuple[float, float]]:
    """
    Kakao REST API로 주소 → (위도, 경도) 반환. 실패 시 None.
    """
    encoded = urllib.parse.quote(address)
    url = f"https://dapi.kakao.com/v2/local/search/address.json?query={encoded}"
    req = urllib.request.Request(url, headers={"Authorization": f"KakaoAK {api_key}"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            docs = data.get("documents", [])
            if docs:
                return float(docs[0]["y"]), float(docs[0]["x"])  # (lat, lng)
    except Exception as e:
        print(f"[MapGen] geocode 실패: {address!r} → {e}")
    return None


def _geocode_all(data: List[Dict], addr_col: str, api_key: str) -> List[Dict]:
    """
    각 레코드에 lat/lng를 추가합니다. 캐시 활용, 실패 항목은 lat/lng=None.
    """
    cache = _load_geocode_cache()
    cache_dirty = False
    results = []

    for record in data:
        address = str(record.get(addr_col, "") or "").strip()
        if not address or address == "None":
            continue

        item: Dict = {"addr": address}
        for col in DATA_COLUMNS:
            val = record.get(col)
            if val is not None:
                s = str(val).strip()
                if s and s != "None":
                    item[col] = s

        if address in cache:
            coords = cache[address]
            item["lat"] = coords[0] if coords else None
            item["lng"] = coords[1] if coords else None
        else:
            coords = _geocode_rest(address, api_key)
            cache[address] = list(coords) if coords else None
            cache_dirty = True
            if coords:
                item["lat"], item["lng"] = coords
                print(f"[MapGen] geocode OK: {address}")
            else:
                item["lat"] = None
                item["lng"] = None
                print(f"[MapGen] geocode 실패 (마커 생략): {address}")
            time.sleep(0.2)  # API rate limit 방지

        results.append(item)

    if cache_dirty:
        _save_geocode_cache(cache)

    return results


# ─────────────────────────────────────────
# HTML 생성
# ─────────────────────────────────────────

def _build_html(items: List[Dict], total: int, title_suffix: str = "") -> str:
    title = f"경매 물건 지도{title_suffix}"

    mapped = [it for it in items if it.get("lat") and it.get("lng")]
    if mapped:
        avg_lat = sum(it["lat"] for it in mapped) / len(mapped)
        avg_lng = sum(it["lng"] for it in mapped) / len(mapped)
    else:
        avg_lat, avg_lng = DEFAULT_LAT, DEFAULT_LNG

    items_json = json.dumps(items, ensure_ascii=False)

    # ── JavaScript 코드 (f-string 이스케이프: {{ }} → { })
    js = r"""
    // ── 마커 색상 결정
    function getColor(item) {
      var s = (item['진행상태'] || item['상태'] || '').replace(/\s/g, '');
      if (s.indexOf('낙찰') >= 0 || s.indexOf('매각') >= 0) return '#43a047'; // 녹색
      if (s.indexOf('유찰') >= 0)                              return '#FB8C00'; // 주황
      if (s.indexOf('취하') >= 0 || s.indexOf('취소') >= 0 ||
          s.indexOf('기각') >= 0 || s.indexOf('변경') >= 0)   return '#e53935'; // 빨강
      return '#1E88E5'; // 파랑 (진행중)
    }

    // ── DivIcon 생성
    function makeIcon(color) {
      return L.divIcon({
        className: '',
        html: '<div class="pin" style="background:' + color + '"></div>',
        iconSize:   [16, 16],
        iconAnchor: [8,  8],
        popupAnchor:[0, -10]
      });
    }

    // ── 팝업 HTML 빌드
    var LABELS = {
      '사건번호':        '사건번호',
      '법원':            '법원',
      '물건번호':        '물건번호',
      '물건주소':        '주소',
      '소재지':          '주소',
      '주소':            '주소',
      '물건소재지':      '주소',
      '용도':            '용도',
      '감정평가액':      '감정가',
      '감정가':          '감정가',
      '최저입찰가_표시': '최저매각가',
      '최저입찰가':      '최저매각가',
      '최저매각가':      '최저매각가',
      '입찰기일':        '매각기일',
      '매각기일':        '매각기일',
      '진행상태':        '상태',
      '상태':            '상태',
      '유찰횟수':        '유찰횟수',
    };

    function statusBadge(item) {
      var s = item['진행상태'] || item['상태'] || '';
      if (!s) return '';
      var color = getColor(item);
      return '<span class="badge" style="background:' + color + '">' + s + '</span>';
    }

    function buildPopup(item) {
      var caseNo = item['사건번호'] || '';
      var addr   = item['addr'] || item['물건주소'] || item['소재지'] || item['주소'] || item['물건소재지'] || '';

      var header = caseNo
        ? '<div class="iw-case-link" onclick="openCase(\'' + caseNo.replace(/'/g,"\\'")+'\')">&#128196; ' + caseNo + '</div>'
        : '';
      header += statusBadge(item);

      var seen = {};
      var rows = '';
      Object.keys(LABELS).forEach(function(key) {
        var label = LABELS[key];
        if (item[key] && !seen[label]) {
          seen[label] = true;
          if (key === '사건번호') return; // 헤더에서 표시
          if (key === '진행상태' || key === '상태') return; // 배지로 표시
          rows += '<tr><th>' + label + '</th><td>' + escHtml(String(item[key])) + '</td></tr>';
        }
      });

      var addrRow = addr
        ? '<div class="iw-addr" onclick="copyAddr(\'' + addr.replace(/'/g,"\\'")+'\')">&#128205; ' + escHtml(addr) + '</div>'
        : '';

      return '<div class="iw-wrap">'
           + header
           + addrRow
           + (rows ? '<table class="iw-table">' + rows + '</table>' : '')
           + '</div>';
    }

    function escHtml(s) {
      return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }

    // ── 사건번호 클릭 → courtauction 자동검색 (Tampermonkey 연동)
    window.openCase = function(caseNo) {
      var base = 'https://www.courtauction.go.kr/pgj/index.on?w2xPath=/pgj/ui/pgj100/PGJ151F00.xml';
      window.open(base + '#' + encodeURIComponent(caseNo), '_blank');
    };

    // ── 주소 복사 + toast
    window.copyAddr = function(addr) {
      if (navigator.clipboard) {
        navigator.clipboard.writeText(addr).then(function() { showToast('주소 복사됨'); });
      } else {
        var el = document.createElement('textarea');
        el.value = addr;
        document.body.appendChild(el);
        el.select();
        document.execCommand('copy');
        document.body.removeChild(el);
        showToast('주소 복사됨');
      }
    };

    function showToast(msg) {
      var t = document.getElementById('toast');
      t.textContent = msg;
      t.className = 'show';
      clearTimeout(t._timer);
      t._timer = setTimeout(function() { t.className = ''; }, 2000);
    }

    // ── 마커 렌더링 + 필터
    var allMarkers = [];
    var markerLayer = L.layerGroup().addTo(map);

    function renderMarkers(items) {
      markerLayer.clearLayers();
      var bounds = [];
      items.forEach(function(item) {
        if (!item.lat || !item.lng) return;
        var m = L.marker([item.lat, item.lng], { icon: makeIcon(getColor(item)) });
        m.bindPopup(buildPopup(item), { maxWidth: 300, className: 'iw-popup' });
        m.addTo(markerLayer);
        bounds.push([item.lat, item.lng]);
      });
      document.getElementById('mapped-count').textContent = bounds.length;
      if (bounds.length > 0) { map.fitBounds(bounds, { padding: [30, 30] }); }
    }

    // ── 필터 옵션 초기화
    function populateFilter(id, items, key) {
      var sel = document.getElementById(id);
      var vals = {};
      items.forEach(function(it) { var v = it[key]; if (v) vals[v] = 1; });
      Object.keys(vals).sort().forEach(function(v) {
        var o = document.createElement('option');
        o.value = v; o.textContent = v;
        sel.appendChild(o);
      });
    }

    function applyFilters() {
      var fType   = document.getElementById('f-type').value;
      var fCourt  = document.getElementById('f-court').value;
      var fStatus = document.getElementById('f-status').value;
      var fMinRaw = document.getElementById('f-minprice').value.replace(/,/g,'');
      var fMin    = fMinRaw ? parseInt(fMinRaw, 10) : 0;

      var filtered = allMarkers.filter(function(item) {
        if (fType   && item['용도']   !== fType)   return false;
        if (fCourt  && item['법원']   !== fCourt)  return false;
        if (fStatus && (item['진행상태'] || item['상태'] || '') !== fStatus) return false;
        if (fMin) {
          var price = parseInt((item['최저입찰가_표시'] || item['최저입찰가'] || item['최저매각가'] || '0')
                       .replace(/[^0-9]/g,''), 10);
          if (price < fMin) return false;
        }
        return true;
      });
      renderMarkers(filtered);
    }

    // ── 초기화
    populateFilter('f-type',   allMarkers, '용도');
    populateFilter('f-court',  allMarkers, '법원');
    populateFilter('f-status', allMarkers, '진행상태');
    populateFilter('f-status', allMarkers, '상태');

    ['f-type','f-court','f-status','f-minprice'].forEach(function(id) {
      document.getElementById(id).addEventListener('change', applyFilters);
      document.getElementById(id).addEventListener('input',  applyFilters);
    });

    renderMarkers(allMarkers);
    """

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" crossorigin=""/>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: 'Malgun Gothic', sans-serif; }}
    #map {{ width: 100%; height: 100vh; }}

    /* 컨트롤 패널 */
    #panel {{
      position: absolute;
      top: 10px; left: 10px;
      z-index: 1000;
      background: rgba(255,255,255,0.96);
      padding: 8px 12px;
      border-radius: 8px;
      box-shadow: 0 2px 10px rgba(0,0,0,0.25);
      font-size: 12px;
      min-width: 220px;
    }}
    #panel .title {{
      font-size: 14px;
      font-weight: bold;
      color: #1F4E79;
      margin-bottom: 6px;
    }}
    #panel .stats {{
      color: #555;
      margin-bottom: 8px;
    }}
    #panel label {{
      display: block;
      margin-top: 5px;
      color: #444;
    }}
    #panel select, #panel input {{
      width: 100%;
      margin-top: 2px;
      padding: 3px 5px;
      border: 1px solid #ccc;
      border-radius: 4px;
      font-size: 12px;
    }}

    /* 커스텀 마커 핀 */
    .pin {{
      width: 16px; height: 16px;
      border-radius: 50%;
      border: 2px solid rgba(255,255,255,0.9);
      box-shadow: 0 1px 4px rgba(0,0,0,0.45);
    }}

    /* 팝업 */
    .iw-popup .leaflet-popup-content-wrapper {{
      border-radius: 8px;
      padding: 0;
      overflow: hidden;
    }}
    .iw-popup .leaflet-popup-content {{
      margin: 0;
      min-width: 200px;
      max-height: 320px;
      overflow-y: auto;
    }}
    .iw-wrap {{
      padding: 10px 12px;
      font-size: 13px;
    }}
    .iw-case-link {{
      font-weight: bold;
      color: #1565C0;
      cursor: pointer;
      margin-bottom: 4px;
    }}
    .iw-case-link:hover {{ text-decoration: underline; }}
    .iw-addr {{
      color: #555;
      font-size: 12px;
      cursor: pointer;
      margin-bottom: 6px;
      word-break: break-all;
    }}
    .iw-addr:hover {{ color: #1565C0; text-decoration: underline; }}
    .badge {{
      display: inline-block;
      padding: 1px 7px;
      border-radius: 10px;
      color: #fff;
      font-size: 11px;
      margin-bottom: 6px;
    }}
    .iw-table {{ border-collapse: collapse; width: 100%; margin-top: 2px; }}
    .iw-table th {{
      text-align: left;
      padding: 2px 10px 2px 0;
      color: #666;
      white-space: nowrap;
      vertical-align: top;
      font-weight: normal;
    }}
    .iw-table td {{ padding: 2px 0; color: #222; word-break: break-all; }}

    /* Toast */
    #toast {{
      position: fixed;
      bottom: 24px; left: 50%;
      transform: translateX(-50%);
      background: rgba(0,0,0,0.78);
      color: #fff;
      padding: 8px 20px;
      border-radius: 20px;
      font-size: 13px;
      opacity: 0;
      transition: opacity 0.3s;
      z-index: 9999;
      pointer-events: none;
    }}
    #toast.show {{ opacity: 1; }}

    /* 범례 */
    #legend {{
      position: absolute;
      bottom: 30px; right: 10px;
      z-index: 1000;
      background: rgba(255,255,255,0.93);
      padding: 8px 12px;
      border-radius: 6px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.2);
      font-size: 12px;
    }}
    .legend-item {{
      display: flex;
      align-items: center;
      gap: 6px;
      margin: 3px 0;
    }}
    .legend-dot {{
      width: 12px; height: 12px;
      border-radius: 50%;
      flex-shrink: 0;
    }}
  </style>
</head>
<body>
  <div id="map"></div>

  <!-- 컨트롤 패널 -->
  <div id="panel">
    <div class="title">경매 물건 지도</div>
    <div class="stats">총 {total}건 | 지도 표시: <span id="mapped-count">0</span>건</div>
    <label>물건종류
      <select id="f-type"><option value="">전체</option></select>
    </label>
    <label>법원
      <select id="f-court"><option value="">전체</option></select>
    </label>
    <label>진행상태
      <select id="f-status"><option value="">전체</option></select>
    </label>
    <label>최저매각가 이상 (원)
      <input id="f-minprice" type="text" placeholder="예: 300000000">
    </label>
  </div>

  <!-- 범례 -->
  <div id="legend">
    <div class="legend-item"><div class="legend-dot" style="background:#1E88E5"></div> 진행중</div>
    <div class="legend-item"><div class="legend-dot" style="background:#43a047"></div> 낙찰/매각</div>
    <div class="legend-item"><div class="legend-dot" style="background:#FB8C00"></div> 유찰</div>
    <div class="legend-item"><div class="legend-dot" style="background:#e53935"></div> 취하/취소</div>
  </div>

  <!-- Toast -->
  <div id="toast"></div>

  <!-- 데이터 -->
  <script>
    var ITEMS = {items_json};
  </script>

  <!-- Leaflet -->
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js" crossorigin=""></script>
  <script>
    var map = L.map('map').setView([{avg_lat}, {avg_lng}], 10);
    L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      maxZoom: 19
    }}).addTo(map);

    var allMarkers = ITEMS;
  </script>
  <script>
    {js}
  </script>
</body>
</html>"""

    return html


# ─────────────────────────────────────────
# 공개 API
# ─────────────────────────────────────────

def generate_map(
    xlsx_path: str = None,
    output_path: str = None,
    use_sample: bool = False,
) -> str:
    """
    엑셀 파일을 읽어 Leaflet.js 지도 HTML을 생성합니다.
    Geocoding은 Python에서 Kakao REST API로 처리하며 결과를 HTML에 임베드합니다.

    Args:
        xlsx_path:   입력 엑셀 경로 (기본: output/ 최신 xlsx 자동 탐색)
        output_path: 출력 HTML 경로 (기본: output/auction_map.html)
        use_sample:  True이면 엑셀 없이 샘플 더미 데이터로 HTML 생성
    Returns:
        생성된 HTML 파일 경로 (실패 시 빈 문자열)
    """
    if output_path is None:
        output_path = os.path.join(_get_output_dir(), "auction_map.html")

    api_key = getattr(config, "KAKAO_REST_API_KEY", "")

    if use_sample:
        print("[MapGen] 샘플 데이터로 지도 생성 중...")
        raw_data = SAMPLE_DATA
        addr_col = _find_address_column(list(raw_data[0].keys()))
        label = " (샘플)"
    else:
        if xlsx_path is None:
            xlsx_path = _find_latest_xlsx()

        print(f"[MapGen] 엑셀 읽기: {xlsx_path}")
        if not os.path.exists(xlsx_path):
            print(f"[MapGen] 파일 없음: {xlsx_path}")
            return ""

        headers, raw_data = _read_excel(xlsx_path)
        if not raw_data:
            print("[MapGen] 데이터가 없습니다.")
            return ""

        addr_col = _find_address_column(headers)
        if not addr_col:
            print(f"[MapGen] 주소 컬럼을 찾을 수 없습니다. (헤더: {headers})")
            return ""

        label = ""

    print(f"[MapGen] geocoding 시작: {len(raw_data)}건 (Kakao REST API)")
    items = _geocode_all(raw_data, addr_col, api_key)

    mapped_count = sum(1 for it in items if it.get("lat") and it.get("lng"))
    print(f"[MapGen] geocoding 완료: {mapped_count}/{len(items)}건 성공")

    html_content = _build_html(items, len(raw_data), label)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"[MapGen] 지도 생성 완료: {output_path}")
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
