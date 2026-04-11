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
ADDRESS_COLUMNS = ["물건주소", "소재지", "주소", "물건소재지", "소재지 및 내역"]

# HTML에 포함할 데이터 컬럼 후보 (경매목록)
DATA_COLUMNS = [
    "사건번호", "법원", "물건번호",
    "물건주소", "소재지", "주소", "물건소재지",
    "용도", "감정평가액", "감정가",
    "최저입찰가_표시", "최저입찰가", "최저매각가",
    "입찰기일", "매각기일", "진행상태", "상태",
    "유찰횟수", "입찰방법",
]

# HTML에 포함할 데이터 컬럼 후보 (매각결과)
RESULT_DATA_COLUMNS = [
    "사건번호", "법원", "물건번호",
    "소재지", "물건주소", "주소", "소재지 및 내역",
    "용도",
    "매각결과",
    "감정평가액", "최저매각가격", "매각금액",
    "매각일자", "매각기일",
    "입찰자수",
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


def _read_csv(filepath: str) -> Tuple[List[str], List[Dict]]:
    """CSV 파일을 읽어 (headers, data) 반환합니다. 인코딩 자동 감지."""
    import csv as csv_module
    if not os.path.exists(filepath):
        return [], []
    for enc in ["utf-8-sig", "utf-8", "cp949"]:
        try:
            with open(filepath, newline="", encoding=enc) as f:
                reader = csv_module.DictReader(f)
                data = list(reader)
                headers = list(reader.fieldnames or [])
            return headers, data
        except (UnicodeDecodeError, UnicodeError):
            continue
        except Exception as e:
            print(f"[MapGen] CSV 읽기 오류: {e}")
            return [], []
    return [], []


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


def _clean_address(addr: str) -> str:
    """
    주소에서 괄호·대괄호 내용, 층·호수 정보를 제거하여 지오코딩용 도로명/지번 주소를 반환합니다.

    처리 순서:
    1. 괄호 [ ] ( ) 등 내용 제거  → 아파트 명칭, 건물 정보 제거
    2. 층·호수 패턴 제거           → "6층604호", "B1층", "지하1층" 등 제거
    3. 최종 건물번호(동) 이후 불필요한 텍스트 제거

    예) '만석로 29 715동 6층604호 (천천동,현대아파트)[집합건물...]'
      → '만석로 29 715동'
    """
    import re
    # 1. 괄호 내용 제거 (중첩 없는 단순 괄호 → 아파트 명칭, 동명, 건물 정보)
    addr = re.sub(r'[\[\(〔（【][^\]\)\）】〕]*[\]\)）】〕]', '', addr)
    # 괄호가 닫히지 않고 끝까지 이어지는 경우
    addr = re.sub(r'[\[\(〔（【].*', '', addr, flags=re.DOTALL)
    # 2. 층·호수 패턴 제거
    #    예: 6층604호, B1층301호, 지하2층, 제1층, B201호, 301호
    addr = re.sub(r'\s*(?:지하|제)?[A-Z]?\d+층[A-Z]?\d*호?', '', addr)
    addr = re.sub(r'\s*[A-Z]?\d+호\b', '', addr)
    # 3. 면적 정보 제거 (예: 128.118㎡)
    addr = re.sub(r'\s*[\d.]+㎡.*', '', addr)
    # 4. 집합건물 등 부가 설명 제거
    addr = re.sub(r'\s*(?:집합건물|철근콘크리트|철골|조적|목조).*', '', addr)
    # 5. 연속 공백 정리
    addr = re.sub(r'\s{2,}', ' ', addr)
    return addr.strip()


def _build_result_items_json(data: List[Dict], headers: List[str], addr_col: str) -> str:
    """매각결과 데이터를 HTML 인라인 JS 배열 문자열로 반환합니다."""
    import re
    all_keys = set(headers) if headers else set()
    items = []
    for record in data:
        raw_addr = str(record.get(addr_col, "") or "").strip()
        if not raw_addr or raw_addr == "None":
            continue
        address = _clean_address(raw_addr)
        if not address:
            continue
        item: Dict = {"addr": address}
        record_keys = all_keys or set(record.keys())
        for col in RESULT_DATA_COLUMNS:
            if col in record_keys and record.get(col) is not None:
                val = str(record[col]).strip()
                if val and val != "None":
                    item[col] = val
        items.append(item)
    return json.dumps(items, ensure_ascii=False)


def _build_html(items_json: str, total: int, title_suffix: str = "",
                result_items_json: str = "[]", result_total: int = 0) -> str:
    title = f"경매 물건 지도{title_suffix}"
    panel_sold   = f" <span style='color:#1976D2'>●</span>매각 <span style='color:#E53935'>●</span>유찰" if result_total > 0 else ""
    panel_result = f" | 매각결과 {result_total}건{panel_sold}" if result_total > 0 else ""

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
    /* ── 복사 토스트 ── */
    #copy-toast {{
      display: none;
      position: fixed;
      bottom: 60px;
      left: 50%;
      transform: translateX(-50%);
      background: rgba(0,0,0,0.75);
      color: #fff;
      padding: 7px 18px;
      border-radius: 20px;
      font-size: 13px;
      z-index: 9999;
      pointer-events: none;
      white-space: nowrap;
    }}
    /* ── 팝업 전체 래퍼 ── */
    .iw-wrap {{
      font-family: 'Malgun Gothic', sans-serif;
      font-size: 13px;
      width: 290px;
      position: relative;
      background: #fff;
      border-radius: 8px;
      overflow: hidden;
    }}
    /* ── 헤더 (주소 + 총 건수 + 닫기) ── */
    .iw-header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      background: #f0f4fa;
      padding: 7px 10px;
      border-bottom: 1px solid #dde3ee;
    }}
    .iw-header-addr {{
      font-size: 11px;
      color: #1565C0;
      flex: 1;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      margin-right: 8px;
      cursor: pointer;
      text-decoration: underline dotted;
      user-select: none;
    }}
    .iw-header-addr:hover {{ color: #0d47a1; }}
    .iw-copy-icon {{ font-size: 11px; opacity: 0.6; margin-left: 3px; }}
    .iw-header-count {{
      font-size: 11px;
      font-weight: bold;
      color: #1F4E79;
      white-space: nowrap;
    }}
    .iw-close {{
      background: none;
      border: none;
      font-size: 16px;
      cursor: pointer;
      color: #999;
      line-height: 1;
      padding: 0 0 0 8px;
      flex-shrink: 0;
    }}
    .iw-close:hover {{ color: #333; }}
    /* ── 스크롤 영역 ── */
    .iw-scroll {{
      max-height: 300px;
      overflow-y: auto;
      padding: 0;
    }}
    .iw-scroll::-webkit-scrollbar {{ width: 4px; }}
    .iw-scroll::-webkit-scrollbar-thumb {{ background: #c5cfe0; border-radius: 2px; }}
    /* ── 개별 물건 카드 ── */
    .iw-card {{
      padding: 9px 12px;
      border-bottom: 1px solid #eef0f5;
    }}
    .iw-card:last-child {{ border-bottom: none; }}
    .iw-badge {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: 10px;
      font-size: 10px;
      font-weight: bold;
      color: white;
      margin-bottom: 6px;
    }}
    /* 경매목록 → 녹색, 매각 → 파란색, 유찰 → 빨간색 */
    .iw-badge-list   {{ background: #2e7d32; }}
    .iw-badge-sold   {{ background: #1565C0; }}
    .iw-badge-fail   {{ background: #c62828; }}
    .iw-badge-result {{ background: #1565C0; }}
    .iw-table {{ border-collapse: collapse; width: 100%; }}
    .iw-table th {{
      text-align: left;
      padding: 2px 8px 2px 0;
      color: #777;
      white-space: nowrap;
      vertical-align: top;
      font-weight: normal;
      font-size: 12px;
      width: 72px;
    }}
    .iw-table td {{
      padding: 2px 0;
      color: #111;
      font-size: 12px;
      word-break: break-all;
    }}
    /* 금액 강조 */
    .iw-money      {{ font-weight: bold; color: #2e7d32; }}
    .iw-money-sale {{ font-weight: bold; color: #1565C0; }}
    /* 사건번호 클릭 링크 */
    .iw-case-link {{
      color: #1565C0;
      cursor: pointer;
      text-decoration: underline dotted;
    }}
    .iw-case-link:hover {{ color: #0d47a1; text-decoration: underline; }}
  </style>
</head>
<body>
  <div id="map"></div>
  <div id="copy-toast"></div>
  <div id="panel">
    <span style="color:#2e7d32">●</span> 경매목록 {total}건{panel_result}
    &nbsp;|&nbsp; <span style="color:#F57C00">●</span> 혼합
    &nbsp;|&nbsp; 지도: <span id="mapped-count">0</span>건 / <span id="addr-count">0</span>개 주소
  </div>

  <script>
    var ITEMS        = {items_json};
    var RESULT_ITEMS = {result_items_json};
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

        var geocoder = new kakao.maps.services.Geocoder();

        // 클러스터러 (전체 마커용)
        var clusterer = new kakao.maps.MarkerClusterer({{
          map: map, averageCenter: true, minLevel: 4,
          disableClickZoom: false
        }});

        function makeSvg(fill, stroke) {{
          return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 36" width="24" height="36">'
            + '<path fill="' + fill + '" stroke="' + stroke + '" stroke-width="1.5" d="M12 1C6.477 1 2 5.477 2 11c0 3.85 2.088 7.202 5.19 9.015L12 35l4.81-14.985C19.912 18.202 22 14.85 22 11c0-5.523-4.477-10-10-10z"/>'
            + '<circle fill="white" cx="12" cy="11" r="4.5"/>'
            + '</svg>';
        }}
        function makeMarkerImage(svg) {{
          return new kakao.maps.MarkerImage(
            'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg),
            new kakao.maps.Size(24, 36),
            {{offset: new kakao.maps.Point(12, 36)}}
          );
        }}
        // 녹색: 경매목록만  파란색: 매각됨  빨간색: 유찰  주황색: 혼합
        var imgGreen  = makeMarkerImage(makeSvg('#2E7D32', '#1B5E20'));
        var imgBlue   = makeMarkerImage(makeSvg('#1976D2', '#0D47A1'));
        var imgRed    = makeMarkerImage(makeSvg('#E53935', '#B71C1C'));
        var imgOrange = makeMarkerImage(makeSvg('#F57C00', '#E65100'));

        var currentIW   = null;
        var mappedItems = 0;
        var addrCount   = 0;
        var bounds      = new kakao.maps.LatLngBounds();
        var allMarkers  = [];

        window.closeIW = function() {{
          if (currentIW) {{ currentIW.close(); currentIW = null; }}
        }};

        /* ── 토스트 공통 표시 ── */
        function showToast(msg) {{
          var toast = document.getElementById('copy-toast');
          toast.textContent = msg;
          toast.style.display = 'block';
          setTimeout(function() {{ toast.style.display = 'none'; }}, 2200);
        }}
        function fallbackCopy(text) {{
          var el = document.createElement('textarea');
          el.value = text;
          el.style.position = 'fixed';
          el.style.opacity  = '0';
          document.body.appendChild(el);
          el.select();
          try {{ document.execCommand('copy'); }} catch(e) {{}}
          document.body.removeChild(el);
        }}

        /* ── 주소 클립보드 복사 ── */
        window.copyAddr = function(addr) {{
          if (navigator.clipboard && navigator.clipboard.writeText) {{
            navigator.clipboard.writeText(addr)
              .then(function()  {{ showToast('주소 복사됨 ✓'); }})
              .catch(function() {{ fallbackCopy(addr); showToast('주소 복사됨 ✓'); }});
          }} else {{
            fallbackCopy(addr); showToast('주소 복사됨 ✓');
          }}
        }};

        /* ── 사건번호 클릭 → 법원경매 검색 ── */
        window.openCase = function(caseNo) {{
          var searchUrl = 'https://www.courtauction.go.kr/pgj/index.on?w2xPath=/pgj/ui/pgj100/PGJ151F00.xml';
          if (navigator.clipboard && navigator.clipboard.writeText) {{
            navigator.clipboard.writeText(caseNo)
              .then(function()  {{ showToast('사건번호 복사됨 — 새 탭 검색창에 붙여넣기 후 검색 (Ctrl+V)'); }})
              .catch(function() {{ fallbackCopy(caseNo); showToast('사건번호 복사됨 — 새 탭 검색창에 붙여넣기 후 검색 (Ctrl+V)'); }});
          }} else {{
            fallbackCopy(caseNo); showToast('사건번호 복사됨 — 새 탭 검색창에 붙여넣기 후 검색 (Ctrl+V)');
          }}
          window.open(searchUrl, '_blank');
        }};

        /* ── 라벨 정의 ── */
        var LABELS_RESULT = {{
          '사건번호': '사건번호', '법원': '법원', '물건번호': '물건번호',
          '소재지': '주소', '물건주소': '주소', '주소': '주소', '소재지 및 내역': '주소',
          '용도': '용도', '매각결과': '매각결과', '감정평가액': '감정가',
          '최저매각가격': '최저매각가', '매각금액': '매각금액',
          '매각일자': '매각일자', '매각기일': '매각일자', '입찰자수': '입찰자수'
        }};
        var LABELS_LIST = {{
          '사건번호': '사건번호', '법원': '법원', '물건번호': '물건번호',
          '물건주소': '주소', '소재지': '주소', '주소': '주소', '물건소재지': '주소',
          '용도': '용도', '감정평가액': '감정가', '감정가': '감정가',
          '최저입찰가_표시': '최저매각가', '최저입찰가': '최저매각가', '최저매각가': '최저매각가',
          '입찰기일': '매각기일', '매각기일': '매각기일',
          '진행상태': '상태', '상태': '상태', '유찰횟수': '유찰횟수'
        }};
        var MONEY_LABELS = new Set(['감정가', '최저매각가', '매각금액']);

        /* ── 카드 한 장 HTML 생성 ── */
        function buildCard(item, type) {{
          var isResult  = (type === 'result');
          var LABELS    = isResult ? LABELS_RESULT : LABELS_LIST;
          var seen = {{}};
          var rows = '';
          Object.keys(LABELS).forEach(function(key) {{
            var label = LABELS[key];
            if (item[key] && !seen[label]) {{
              seen[label] = true;
              var val = item[key];
              var valClass = MONEY_LABELS.has(label)
                ? (label === '매각금액' ? ' class="iw-money-sale"' : ' class="iw-money"')
                : '';
              /* 사건번호는 클릭 가능하게 */
              if (key === '사건번호') {{
                var safeCaseNo = val.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
                val = '<span class="iw-case-link" title="클릭하면 법원경매 사이트 검색" onclick="openCase(\'' + safeCaseNo + '\')">' + val + '</span>';
                valClass = '';
              }}
              rows += '<tr><th>' + label + '</th><td' + valClass + '>' + val + '</td></tr>';
            }}
          }});
          /* 배지 결정 */
          var badgeClass, badgeText;
          if (!isResult) {{
            badgeClass = 'iw-badge-list';  badgeText = '경매목록';
          }} else if (item['매각결과'] === '매각') {{
            badgeClass = 'iw-badge-sold';  badgeText = '매각';
          }} else if (item['매각결과'] === '유찰') {{
            badgeClass = 'iw-badge-fail';  badgeText = '유찰';
          }} else {{
            badgeClass = 'iw-badge-result'; badgeText = '매각결과';
          }}
          return '<div class="iw-card">'
               + '<span class="iw-badge ' + badgeClass + '">' + badgeText + '</span>'
               + '<table class="iw-table">' + rows + '</table>'
               + '</div>';
        }}

        /* ── 그룹 팝업 전체 HTML 생성 ── */
        function buildGroupContent(entries, addr) {{
          var shortAddr = addr.length > 28 ? addr.slice(0, 26) + '…' : addr;
          var countText = entries.length > 1 ? entries.length + '건' : '';
          var safeAddr  = addr.replace(/\\/g, '\\\\').replace(/'/g, "\\'");
          var cards = entries.map(function(e) {{ return buildCard(e.item, e.type); }}).join('');
          return '<div class="iw-wrap">'
               + '<div class="iw-header">'
               +   '<span class="iw-header-addr" title="클릭하면 주소 복사&#10;' + addr + '" onclick="copyAddr(\'' + safeAddr + '\')">'
               +     shortAddr + '<span class="iw-copy-icon">⎘</span>'
               +   '</span>'
               +   (countText ? '<span class="iw-header-count">' + countText + '</span>' : '')
               +   '<button class="iw-close" onclick="closeIW()">✕</button>'
               + '</div>'
               + '<div class="iw-scroll">' + cards + '</div>'
               + '</div>';
        }}

        /* ── 주소별 그룹화 ── */
        var addrGroups = {{}};   // addr → [{{item, type}}, ...]
        function addToGroup(item, type) {{
          var key = item.addr;
          if (!addrGroups[key]) addrGroups[key] = [];
          addrGroups[key].push({{item: item, type: type}});
        }}
        ITEMS.forEach(function(item)        {{ addToGroup(item, 'list'); }});
        RESULT_ITEMS.forEach(function(item) {{ addToGroup(item, 'result'); }});

        /* ── 마커 생성 ── */
        function addGroupMarker(addr, entries, lat, lng) {{
          var hasList = entries.some(function(e) {{ return e.type === 'list'; }});
          var hasSold = entries.some(function(e) {{ return e.type === 'result' && e.item['매각결과'] === '매각'; }});
          var hasFail = entries.some(function(e) {{ return e.type === 'result' && e.item['매각결과'] === '유찰'; }});
          var hasResult = hasSold || hasFail;
          /* 색상 우선순위: 혼합→주황 / 매각→파랑 / 유찰→빨강 / 경매목록→녹색 */
          var img = (hasList && hasResult) ? imgOrange
                  : hasSold                ? imgBlue
                  : hasFail                ? imgRed
                  :                          imgGreen;

          var pos    = new kakao.maps.LatLng(lat, lng);
          var marker = new kakao.maps.Marker({{ position: pos, image: img }});
          var iw     = new kakao.maps.InfoWindow({{
            content: buildGroupContent(entries, addr),
            removable: false
          }});
          kakao.maps.event.addListener(marker, 'click', function() {{
            closeIW();
            iw.open(map, marker);
            currentIW = iw;
          }});
          allMarkers.push(marker);
          bounds.extend(pos);

          mappedItems += entries.length;
          addrCount++;
          document.getElementById('mapped-count').textContent = mappedItems;
          document.getElementById('addr-count').textContent   = addrCount;
        }}

        /* ── 순차 지오코딩 (주소 단위, 300ms 간격) ── */
        var addrQueue = Object.keys(addrGroups);
        var qIdx = 0;

        function processNext() {{
          if (qIdx >= addrQueue.length) {{
            clusterer.addMarkers(allMarkers);
            if (allMarkers.length > 0) map.setBounds(bounds);
            return;
          }}
          var addr    = addrQueue[qIdx++];
          var entries = addrGroups[addr];
          geocoder.addressSearch(addr, function(result, status) {{
            if (status === kakao.maps.services.Status.OK) {{
              addGroupMarker(addr, entries, result[0].y, result[0].x);
            }}
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

        # 매각결과 CSV 로드
        result_csv_path = os.path.join(_get_output_dir(), "courtauction_result.csv")
        result_headers, result_data_rows = _read_csv(result_csv_path)
        result_items_json = "[]"
        result_total = 0
        if result_data_rows:
            result_addr_col = _find_address_column(result_headers) or "소재지"
            result_items_json = _build_result_items_json(result_data_rows, result_headers, result_addr_col)
            result_total = len(result_data_rows)
            print(f"[MapGen] 매각결과 {result_total}건 추가 (파란색 마커)")

        html_content = _build_html(items_json, len(data),
                                   result_items_json=result_items_json,
                                   result_total=result_total)
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
