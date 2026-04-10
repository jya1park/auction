# 법원경매 크롤러 (Court Auction Crawler)

수원지방법원 경매 물건(아파트)을 자동 수집하고 Excel, CSV, 카카오맵으로 시각화하는 Python 크롤러입니다.

## 프로젝트 개요

`courtauction.go.kr` (대법원 경매정보) 에서 수원지방법원 아파트 경매 물건을 자동 수집합니다.

- 수집 대상: 수원지방법원 아파트 경매 목록 (PGJ151F00) + 매각결과 (PGJ158F00)
- 저장 형식: CSV (`courtauction_list.csv`), Excel (`courtauction_data.xlsx`, 2시트 누적 upsert)
- 시각화: 카카오맵 인터랙티브 HTML (`auction_map.html`)

## 완성된 기능

### 크롤링
- **3단계 물건종류 선택** — 건물 → 주거용건물 → 아파트 (WebSquare AJAX 드롭다운 대응)
- **전체 페이지네이션** — 블록 단위 이동 (1-10페이지 → 다음 블록 → 11-13페이지 등)
- **Stale DOM 처리** — 페이지 이동 후 `staleness_of`로 DOM 갱신 확인
- **매각결과 수집** — PGJ158F00 URL에서 동일 조건(수원/아파트)으로 자동 검색
- **찜한 물건 낙찰 조회** — `--watchlist` 모드, 사건번호 직접 입력 (2023타경10883 형식)

### 저장
- **CSV 누적 upsert** — `사건번호 + 물건번호` 기준으로 기존 데이터 보존/갱신
- **Excel 2시트** — 시트1: 경매목록(파란 헤더), 시트2: 매각결과(보라 헤더), 업데이트일시 컬럼 포함
- **지도용 CSV 동기화** — `save_csv` 호출 시 `courtauction_list.csv`도 자동 갱신

### 지도 시각화
- **카카오맵 HTML** — 브라우저 JS SDK로 순차 Geocoding (300ms 간격, API 부하 분산)
- **주소 정제** — `[건물설명]`, `(괄호)` 제거로 Geocoding 성공률 향상
- **클러스터링** — 마커 밀집 지역 자동 클러스터, 클릭 시 상세 팝업
- **GitHub 업로드** — `map_generator.upload_to_github()` 함수로 `storage/auction_map.html` 자동 배포 지원

### 기타
- **Custom HTTP 서버** (`output/serve.py`) — 한국어 Windows hostname 디코딩 오류(`getfqdn`) 우회
- **WinError 193 수정** — `webdriver-manager`가 THIRD_PARTY_NOTICES를 반환하는 문제 → chromedriver.exe 직접 탐색
- **UnicodeDecodeError 수정** — PowerShell CP949 출력을 UTF-8로 잘못 디코딩하는 문제 → subprocess 디코딩 패치

## 프로젝트 구조

```
courtauction_crawler/
├── main.py                    # 메인 실행 파일 (CLI 인자 처리)
├── config.py                  # 설정값 (URL, 법원명, 용도, 딜레이 등)
├── crawler/
│   ├── driver.py              # Chrome WebDriver 초기화 (WinError 193/UnicodeDecodeError 패치)
│   ├── navigator.py           # 경매목록 탐색 (법원·종류 선택, 전체 페이지네이션)
│   ├── list_parser.py         # 경매목록 HTML 파싱 (8셀 메인행 + 3셀 상세행 쌍 구조)
│   ├── detail_parser.py       # 물건 상세 페이지 파싱 (--detail 옵션)
│   ├── result_navigator.py    # 매각결과 페이지 탐색
│   └── result_parser.py       # 매각결과 HTML 파싱 (헤더 자동 감지)
├── storage/
│   ├── exporter.py            # CSV/Excel 저장 (누적 upsert, 2시트)
│   └── map_generator.py       # 카카오맵 HTML 생성 + GitHub 업로드
└── output/
    ├── serve.py               # 커스텀 HTTP 서버 (Korean Windows hostname 우회)
    ├── courtauction_data.xlsx  # 누적 Excel (경매목록 + 매각결과)
    ├── courtauction_list.csv   # 지도 생성용 최신 CSV
    ├── courtauction_*.csv      # 실행별 타임스탬프 CSV
    └── auction_map.html        # 카카오맵 시각화
```

## 설치

Python 3.8 이상, Google Chrome 필요

```bash
pip install selenium webdriver-manager openpyxl beautifulsoup4
```

## 실행 방법

```bash
# 기본 실행 (headless, 전체 페이지, 경매목록 + 매각결과 + 지도 자동 생성)
python main.py

# 브라우저 창 표시 (디버그 시 유용)
python main.py --visible

# 최대 5페이지만 수집
python main.py --pages 5

# 각 물건 상세 정보(낙찰가 등)도 수집
python main.py --detail

# Excel도 함께 저장
python main.py --excel

# 디버그 모드 (DOM 구조 상세 출력)
python main.py --debug

# 찜한 물건 낙찰 조회
python main.py --watchlist

# 복합 옵션
python main.py --visible --debug --pages 3 --excel
```

## 카카오맵 보는 방법

### 1단계 — 카카오 개발자 콘솔 도메인 등록 (최초 1회)
1. [developers.kakao.com](https://developers.kakao.com) → 내 애플리케이션 → 앱 선택
2. 플랫폼 → Web → 사이트 도메인에 `http://127.0.0.1:8000` 추가

### 2단계 — 로컬 서버 실행 (Korean Windows 전용)
```bash
cd output
python serve.py
```
> `python -m http.server` 는 한국어 Windows에서 hostname 디코딩 오류 발생 → `serve.py` 사용

### 3단계 — 브라우저 접속
```
http://127.0.0.1:8000/auction_map.html
```

> `file://` 로 직접 열면 카카오 API 인증 거부로 지도가 표시되지 않습니다.

## 설정 (config.py)

| 항목 | 기본값 | 설명 |
|------|--------|------|
| TARGET_COURT | 수원지방법원 | 대상 법원 |
| TARGET_TYPE | 아파트 | 물건 종류 |
| WAIT_TIMEOUT | 15 | 페이지 대기 시간(초) |
| PAGE_DELAY | 2.0 | 페이지 간 딜레이(초) |
| SEARCH_URL | `.../PGJ151F00` | 경매목록 URL |
| RESULT_URL | `.../PGJ158F00` | 매각결과 URL |
| OUTPUT_DIR | output | 저장 디렉토리 |

## 알려진 이슈

| 오류/상황 | 원인 | 해결 |
|-----------|------|------|
| WinError 193 | webdriver-manager가 chromedriver.exe 대신 THIRD_PARTY_NOTICES 반환 | driver.py에서 .exe 직접 탐색 |
| UnicodeDecodeError (0xb6) | 한국어 Windows PowerShell CP949 출력을 UTF-8로 잘못 디코딩 | driver.py에서 subprocess 디코딩 패치 |
| `python -m http.server` 실패 | `socket.getfqdn()`이 한국어 hostname을 CP949로 디코딩 실패 | output/serve.py의 getfqdn monkey-patch 사용 |
| 매각결과 빈 데이터 | PGJ158F00 페이지의 실제 select ID가 경매목록과 다를 수 있음 | `--debug` 모드로 실행 후 result_debug_*.html 확인 |
| 매각결과 페이지 이동 불안정 | result_navigator의 `go_to_next_page`는 "다음" 버튼만 클릭 (staleness_of 대기 없음) | 페이지 이동 후 데이터 검증 로직 추가 예정 |

## 변경 이력

| 날짜 | 내용 |
|------|------|
| 2026-04 | 최초 구현 — 수원지방법원 아파트 경매목록 크롤링 |
| 2026-04 | lxml → html.parser 변경 (파서 오류 수정) |
| 2026-04 | 물건종류 선택 2단계 → 3단계 (건물 → 주거용건물 → 아파트) |
| 2026-04 | Excel 누적 저장 + 업데이트일시 컬럼 추가 |
| 2026-04 | 매각결과 수집 추가 (result_navigator.py, result_parser.py, 시트2) |
| 2026-04 | 찜한 물건 낙찰조회 3필드 입력 방식 |
| 2026-04 | 카카오맵 시각화 추가 (map_generator.py, 브라우저 사이드 geocoding) |
| 2026-04 | WinError 193 수정 (chromedriver.exe 직접 탐색) |
| 2026-04 | UnicodeDecodeError 수정 (webdriver-manager subprocess 패치) |
| 2026-04 | serve.py 추가 (Korean Windows hostname 우회) |
| 2026-04 | CSV 2파일 저장 방식으로 전환 (courtauction_list.csv + 타임스탬프) |
| 2026-04 | 카카오맵 window.onload 타이밍 수정 |
| 2026-04 | 페이지네이션 1→11 점프 버그 수정 (블록 경계 처리) |
| 2026-04 | staleness_of 대기로 Stale DOM 오류 수정 |
| 2026-04 | go_to_next_page 단순화 (current_page 인자로 불필요한 DOM 재탐색 제거) |
