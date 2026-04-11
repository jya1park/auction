# 법원경매 크롤러 (Court Auction Crawler)

수원지방법원 아파트 경매 물건을 자동 수집하고 Excel, CSV, 카카오맵으로 시각화하는 Python 크롤러입니다.

---

## 주요 기능

### 크롤링
- **경매목록 수집** — 수원지방법원 아파트 경매 전체 페이지 자동 수집
- **매각결과 수집** — 낙찰가, 유찰 여부, 입찰자 수 포함
- **3단계 물건종류 선택** — 건물 → 주거용건물 → 아파트 (WebSquare AJAX 드롭다운 대응)
- **전체 페이지네이션** — 블록 단위 이동 (1–10 → 11–20 → ...)
- **Stale DOM 처리** — 페이지 이동 후 `staleness_of`로 DOM 갱신 확인

### 저장
- **CSV 누적 upsert** — `사건번호 + 물건번호` 기준으로 기존 데이터 보존/갱신
- **Excel 2시트** — 시트1: 경매목록(파란 헤더), 시트2: 매각결과(보라 헤더), 업데이트일시 자동 기록

### 지도 시각화 (auction_map.html)
- **카카오맵 인터랙티브 HTML** — 브라우저 JS SDK로 순차 Geocoding (300ms 간격)
- **주소별 마커 그룹화** — 같은 주소의 여러 물건을 하나의 마커 + 스크롤 팝업으로 표시
- **마커 색상 구분**

  | 색상 | 의미 |
  |------|------|
  | 🟢 녹색 | 경매목록 (현재 진행 중) |
  | 🔵 파란색 | 매각 완료 |
  | 🔴 빨간색 | 유찰 |
  | 🟠 주황색 | 경매목록 + 매각결과 혼합 |

- **주소 복사** — 팝업 상단 주소 클릭 시 클립보드 자동 복사
- **사건번호 클릭 → 법원경매 자동검색** — Tampermonkey 스크립트 연동 (아래 참고)
- **주소 정제** — 층·호수·괄호 제거로 Geocoding 성공률 향상
- **클러스터링** — 마커 밀집 시 자동 클러스터, 클릭으로 확대

---

## 프로젝트 구조

```
courtauction_crawler/
├── main.py                      # 메인 실행 (CLI 인자 처리)
├── config.py                    # 설정값 (URL, 법원명, 딜레이 등)
├── crawler/
│   ├── driver.py                # Chrome WebDriver 초기화
│   ├── navigator.py             # 경매목록 탐색 (법원·종류 선택, 페이지네이션)
│   ├── list_parser.py           # 경매목록 HTML 파싱
│   ├── result_navigator.py      # 매각결과 페이지 탐색
│   └── result_parser.py         # 매각결과 HTML 파싱 (서브행 감지, 최저가·낙찰가 추출)
├── storage/
│   ├── exporter.py              # CSV/Excel 저장 (누적 upsert, 2시트)
│   └── map_generator.py         # 카카오맵 HTML 생성
├── output/
│   ├── serve.py                 # 커스텀 HTTP 서버 (Korean Windows hostname 우회)
│   ├── courtauction_data.xlsx   # 누적 Excel (경매목록 + 매각결과)
│   ├── courtauction_list.csv    # 지도 생성용 최신 CSV
│   └── auction_map.html         # 카카오맵 시각화
├── tampermonkey_auction.user.js # 법원경매 사이트 자동검색 스크립트
└── upload_to_github.py          # GitHub 파일 업로드 스크립트
```

---

## 설치

Python 3.8 이상, Google Chrome 필요

```bash
pip install selenium webdriver-manager openpyxl beautifulsoup4
```

---

## 실행 방법

```bash
# 기본 실행 (headless, 전체 페이지, 경매목록 + 매각결과 + 지도 자동 생성)
python main.py

# 브라우저 창 표시 (디버그 시)
python main.py --visible

# 최대 5페이지만 수집
python main.py --pages 5

# Excel 함께 저장
python main.py --excel

# 디버그 모드 (DOM 구조 상세 출력)
python main.py --debug

# 복합 옵션
python main.py --visible --debug --pages 3 --excel
```

---

## 지도 보는 방법

### 1단계 — 카카오 도메인 등록 (최초 1회)
1. [developers.kakao.com](https://developers.kakao.com) → 내 애플리케이션 → 앱 선택
2. 플랫폼 → Web → 사이트 도메인에 `http://127.0.0.1:8000` 추가

### 2단계 — 로컬 서버 실행
```bash
cd output
python serve.py
```
> `python -m http.server`는 한국어 Windows에서 hostname 디코딩 오류 발생 → `serve.py` 사용

### 3단계 — 브라우저 접속
```
http://127.0.0.1:8000/auction_map.html
```
> `file://`로 직접 열면 카카오 API 인증 거부로 지도 미표시

---

## 사건번호 클릭 → 법원경매 자동검색 (Tampermonkey)

지도 팝업에서 사건번호를 클릭하면 법원경매 사이트가 새 탭으로 열리고, 연도·종류·번호가 자동으로 입력된 후 검색까지 실행됩니다.

### 설치 방법 (최초 1회)

1. Chrome 웹스토어에서 **[Tampermonkey](https://chromewebstore.google.com/detail/tampermonkey/dhdgffkkebhmkfjojejmpbldmpobfkfo)** 설치
2. Tampermonkey 아이콘 → **새 스크립트 만들기**
3. `tampermonkey_auction.user.js` 전체 내용 붙여넣기 → 저장

### 동작 순서
```
사건번호 클릭
  → 법원경매 사이트 새 탭 오픈 (PGJ159M00 경매사건검색 페이지)
  → Tampermonkey 자동 실행:
      ① 법원 선택 (예: 수원지방법원)
      ② 연도 선택 (예: 2024)
      ③ 사건종류 선택 (예: 타경)
      ④ 번호 입력 (예: 10001)
      ⑤ 검색 버튼 클릭
```

### 연동된 DOM ID

| 필드 | Element ID |
|------|-----------|
| 법원 select | `mf_wfm_mainFrame_sbx_dspslRsltSrchCortOfc` |
| 연도 select | `mf_wfm_mainFrame_sbx_auctnCsSrchCsYear` |
| 번호 input | `mf_wfm_mainFrame_ibx_auctnCsSrchCsNo` |

---

## 설정 (config.py)

| 항목 | 기본값 | 설명 |
|------|--------|------|
| `TARGET_COURT` | 수원지방법원 | 대상 법원 |
| `TARGET_TYPE` | 아파트 | 물건 종류 |
| `WAIT_TIMEOUT` | 15 | 페이지 대기 시간(초) |
| `PAGE_DELAY` | 2.0 | 페이지 간 딜레이(초) |
| `SEARCH_URL` | `.../PGJ151F00` | 경매목록 URL |
| `RESULT_URL` | `.../PGJ158F00` | 매각결과 URL |
| `OUTPUT_DIR` | output | 저장 디렉토리 |

---

## 알려진 이슈 및 해결

| 오류 / 상황 | 원인 | 해결 |
|-------------|------|------|
| WinError 193 | webdriver-manager가 chromedriver.exe 대신 THIRD_PARTY_NOTICES 반환 | driver.py에서 .exe 직접 탐색 |
| UnicodeDecodeError | 한국어 Windows PowerShell CP949 출력을 UTF-8로 잘못 디코딩 | driver.py subprocess 디코딩 패치 |
| `python -m http.server` 실패 | `socket.getfqdn()`이 한국어 hostname 디코딩 실패 | output/serve.py의 getfqdn monkey-patch |
| 매각결과 최저가·낙찰가 누락 | rowspan 확장 후 서브행이 메인행으로 오인됨 | result_parser.py 서브행 감지 로직 (용도 컬럼 내용 기반) |
| 같은 주소 마커 겹침 | 주소별 개별 마커 생성 | 주소 기준 그룹화 → 스크롤 팝업 |

---

## 변경 이력

| 날짜 | 내용 |
|------|------|
| 2026-04 | 최초 구현 — 수원지방법원 아파트 경매목록 크롤링 |
| 2026-04 | 매각결과 수집 추가 (result_navigator, result_parser, Excel 시트2) |
| 2026-04 | 카카오맵 시각화 추가 (map_generator.py, 브라우저 사이드 geocoding) |
| 2026-04 | WinError 193 / UnicodeDecodeError / serve.py 수정 |
| 2026-04 | 페이지네이션 블록 경계 버그 수정, Stale DOM 처리 |
| 2026-04 | 매각결과 서브행 파싱 수정 — 최저매각가격·매각금액 정확히 추출 |
| 2026-04 | 지도 마커 색상 구분 (녹색/파란색/빨간색/주황색) |
| 2026-04 | 지도 팝업 주소별 그룹화 + 스크롤 팝업 |
| 2026-04 | 주소 클릭 시 클립보드 복사 기능 |
| 2026-04 | 사건번호 클릭 → Tampermonkey 연동 법원경매 자동검색 |
