# 법원경매 크롤러 (Court Auction Crawler)

수원지방법원 아파트 경매 물건을 자동 수집하고 Excel, CSV, 카카오맵으로 시각화하는 Python 크롤러입니다.

---

## 주요 기능

### 크롤링
- **경매목록 수집** — 수원지방법원 아파트 경매 전체 페이지 자동 수집
- **매각결과 수집** — 낙찰가, 유찰 여부, 매각기일 포함
- **3단계 물건종류 선택** — 건물 → 주거용건물 → 아파트 (WebSquare AJAX 드롭다운 대응)
- **전체 페이지네이션** — 블록 단위 이동 (1–10 → 11–20 → ...)
- **Stale DOM 처리** — 페이지 이동 후 `staleness_of`로 DOM 갱신 확인

### 저장
마스터 저장소는 `courtauction_data.xlsx` 1개 파일이며, 시트별로 저장 정책이 다릅니다.

| 시트 | 정책 | 동작 |
|------|------|------|
| 시트1 **경매목록** (파란 헤더) | **전체 교체** | 매 실행 시 기존 데이터 삭제 → 새 크롤링 결과로 통째로 덮어씀 |
| 시트2 **매각결과** (보라 헤더) | **신규만 누적** | 기존 데이터 유지 + `(사건번호, 물건번호)` 기준 신규 행만 append |

- 두 시트 모두 모든 행에 **`업데이트일시`** 자동 기록
- 금액 컬럼은 `_원`(정수), `_만원`(파생) 형태로 추가 저장하여 정렬·필터 용이

### 백업 CSV (선택적)
실행할 때마다 별도로 CSV 백업 파일도 함께 떨어뜨립니다. **코드 내에서 다시 읽지 않으므로 외부 분석/이력용**입니다.

| 파일 | 정책 | 용도 |
|------|------|------|
| `courtauction_list.csv` | 매 실행 시 덮어쓰기 | 경매목록 그날 스냅샷 |
| `courtauction_result_YYYYMMDD.csv` | 매일 새 파일 생성 | 매각결과 일일 스냅샷 |

### 지도 시각화 (auction_map.html)
- **카카오맵 인터랙티브 HTML** — Kakao REST API로 Python 서버측 Geocoding 후 좌표 JSON 임베드
- **마커 색상 구분**

  | 마커 | 의미 |
  |------|------|
  | 용도별 색상 핀 (아파트=빨강, 근린=파랑 등) | 경매목록 (진행 중) |
  | 파란 핀 + 금색 ★ | 낙찰 완료 |
  | 주황 핀 + 흰색 ✕ | 유찰 |

- **멀티 토글 필터** — 전체 / 경매 / ★ 낙찰 / ✕ 유찰 각 독립 on/off (전체 버튼은 일괄 토글)
- **클러스터링** — 마커 밀집 시 자동 클러스터, 클릭으로 확대
- **법원경매 바로가기** — 팝업 버튼 클릭 시 법원경매 사이트 이동 + 사건번호 자동 입력
- **Geocode 캐시** — `output/geocode_cache.json`에 저장, 재실행 시 API 호출 최소화

---

## 프로젝트 구조

```
courtauction_crawler/
├── main.py                        # 메인 실행 (CLI 인자, --map 플래그 포함)
├── open_map.py                    # 더블클릭 지도 런처 (서버 시작 + 브라우저 오픈)
├── config.py                      # 설정값 (URL, 법원명, API 키, 딜레이 등)
├── diagnose_map.py                # 지도 생성 단계별 진단 스크립트
├── requirements.txt               # 의존성 목록
├── tampermonkey_auction.user.js   # 법원경매 사이트 자동검색 스크립트 (v4.0)
├── upload_to_github.py            # GitHub API 파일 업로드 유틸리티
├── crawler/
│   ├── driver.py                  # Chrome WebDriver 초기화
│   ├── navigator.py               # 경매목록 탐색 (법원·종류 선택, 페이지네이션)
│   ├── list_parser.py             # 경매목록 HTML 파싱
│   ├── result_navigator.py        # 매각결과 페이지 탐색
│   ├── result_parser.py           # 매각결과 HTML 파싱 (서브행 감지, 낙찰가 추출)
│   └── detail_parser.py           # 물건 상세 페이지 파싱
├── storage/
│   ├── exporter.py                # CSV/Excel 저장 (누적 upsert, 2시트)
│   └── map_generator.py           # 카카오맵 HTML 생성 (REST API Geocoding + 마커/필터)
└── output/
    ├── courtauction_data.xlsx              # 마스터 Excel (경매목록 + 매각결과 2시트)
    ├── courtauction_list.csv               # 경매목록 백업 CSV (매 실행 덮어쓰기)
    ├── courtauction_result_YYYYMMDD.csv    # 매각결과 백업 CSV (일자별 새 파일)
    ├── geocode_cache.json                  # 주소-좌표 캐시 (자동 생성)
    └── auction_map.html                    # 카카오맵 시각화 (자동 생성)
```

---

## 데이터 흐름

```
대법원 경매 사이트
   ├─ 경매목록 페이지  ──→  list_parser   ──┐
   └─ 매각결과 페이지  ──→  result_parser ──┤
                                             │
                                             ▼
                              ┌─────────────────────────────┐
                              │       exporter.py           │
                              │                             │
                              │  save_csv()        →  courtauction_list.csv         (덮어쓰기)
                              │  save_result_csv() →  courtauction_result_YYYYMMDD.csv  (일자별)
                              │  update_excel()    →  courtauction_data.xlsx        (마스터)
                              │       ├─ 경매목록 시트: 전체 교체
                              │       └─ 매각결과 시트: (사건번호+물건번호) 기준 누적
                              └─────────────────────────────┘
                                             │
                                             ▼
                              ┌─────────────────────────────┐
                              │     map_generator.py        │
                              │                             │
                              │  courtauction_data.xlsx 만 읽음
                              │   ├─ 경매목록 시트  → 용도별 색상 마커
                              │   └─ 매각결과 시트  → ★낙찰 / ✕유찰 마커
                              │                             │
                              │  Kakao REST Geocoding (캐시: geocode_cache.json)
                              │                             │
                              │  → output/auction_map.html
                              └─────────────────────────────┘
```

> CSV 파일들은 마스터 xlsx에 이미 동일 내용이 저장되어 있어 **현재 코드에서 소비되지 않습니다**.
> 외부 도구(Excel 직접 열람 외) 백업/분석 목적으로만 의미 있습니다.

---

## 설치

Python 3.8 이상, Google Chrome 필요

```bash
pip install -r requirements.txt
# 또는
pip install selenium webdriver-manager openpyxl beautifulsoup4
```

---

## 실행 방법

### 크롤링

```bash
# 기본 실행 (headless, 전체 페이지, 경매목록 + 매각결과 + 지도 자동 생성)
python main.py

# 브라우저 창 표시 (디버그 시)
python main.py --visible

# 최대 5페이지만 수집
python main.py --pages 5

# Excel 함께 저장
python main.py --excel

# 디버그 모드
python main.py --debug

# 지도만 생성 (크롤링 없이, 기존 Excel 데이터 사용)
python main.py --map
```

### 지도 보기

```bash
python open_map.py
# → localhost:8080 서버 시작 후 브라우저 자동 오픈
```

---

## 카카오맵 최초 설정 (1회)

카카오 JS SDK는 등록된 도메인에서만 동작합니다.

1. [developers.kakao.com](https://developers.kakao.com) → 내 애플리케이션 → 앱 선택
2. 플랫폼 → Web → 사이트 도메인에 `http://localhost:8080` 추가 → 저장

> `python -m http.server`는 한국어 Windows에서 `socket.getfqdn()` 인코딩 오류 발생 →
> `open_map.py`가 monkey-patch로 우회 처리함

---

## 법원경매 바로가기 — Tampermonkey 자동입력

지도 팝업에서 **법원경매 바로가기** 버튼을 클릭하면 법원경매 사이트가 새 탭으로 열리고
사건번호가 자동으로 입력된 후 검색이 실행됩니다.

### 설치 (최초 1회)

1. Chrome 웹스토어에서 **[Tampermonkey](https://chromewebstore.google.com/detail/tampermonkey/dhdgffkkebhmkfjojejmpbldmpobfkfo)** 설치
2. Tampermonkey 아이콘 → 대시보드 → 새 스크립트
3. `tampermonkey_auction.user.js` 전체 내용 붙여넣기 → 저장

### 동작 방식

```
버튼 클릭
  → URL hash로 사건번호 + 법원명 전달
     예: ...PGJ159M00.xml#caseNo=2023타경9145&court=수원지방법원
  → 법원경매 사이트 새 탭 오픈
  → Tampermonkey v4.0 자동 실행 (@run-in-frame — iframe 내부에서도 동작):
      ① 법원 select 선택
      ② 연도 select 선택
      ③ 사건종류 select 선택 (타경 등)
      ④ 번호 input 입력
      ⑤ 검색 버튼 클릭
```

---

## 설정 (config.py)

| 항목 | 기본값 | 설명 |
|------|--------|------|
| `TARGET_COURT` | 수원지방법원 | 대상 법원 |
| `TARGET_TYPE` | 아파트 | 물건 종류 |
| `WAIT_TIMEOUT` | 15 | 페이지 대기 시간(초) |
| `PAGE_DELAY` | 2.0 | 페이지 간 딜레이(초) |
| `SEARCH_URL` | `.../PGJ151F00.xml` | 경매목록 URL |
| `RESULT_URL` | `.../PGJ158M00.xml` | 매각결과 URL |
| `KAKAO_REST_API_KEY` | (설정 필요) | Geocoding용 REST API 키 |
| `OUTPUT_DIR` | output | 저장 디렉토리 |

---

## 시트별 헤더 구성

두 시트는 **다른 페이지를 다른 파서로 긁기 때문에 헤더가 서로 다릅니다.**

### 경매목록 시트
```
업데이트일시 | 사건번호 | 법원 | 물건번호 | 물건주소 | 용도 | 비고 |
감정평가액 | 감정가_원 | 입찰기일 | 유찰횟수_입찰란 | 링크 | 진행상태 |
최저입찰가_표시 | 최저입찰가_원 | 최저입찰가율 | 유찰횟수 | 유찰횟수_원문
```

### 매각결과 시트
```
업데이트일시 | 사건번호 | 물건번호 | 소재지 및 내역 | 비고 |
감정평가액 | 감정평가액_원 | 담당계매각기일(입찰기간) |
용도 | 매각결과 | 매각금액 | 매각금액_원
```

> 매각결과 시트는 **메인행 → `finalize()`(`_원` 추가) → `merge_subrow()`(용도/매각결과/매각금액)** 순으로 dict key가 채워져 컬럼 순서가 정해집니다.

---

## 알려진 이슈 및 해결

| 오류 / 상황 | 원인 | 해결 |
|-------------|------|------|
| `UnicodeDecodeError (CP949)` | 한국어 Windows `socket.getfqdn()` 실패 | `open_map.py` monkey-patch 적용 |
| `kakao is not defined` | localhost 도메인 미등록 | Kakao 개발자 콘솔에서 `http://localhost:8080` 등록 |
| geocode 캐시 손상 | 인코딩 불일치 또는 비정상 종료 | UTF-8/CP949 자동 시도 후 손상 시 캐시 자동 삭제 |
| `--map` 인식 불가 | argparse 미등록 (구버전) | `main.py`에 `--map` 추가, 크롤러 import lazy 처리 |
| WinError 193 | webdriver-manager 잘못된 파일 반환 | driver.py에서 .exe 직접 탐색 |
| Tampermonkey 미동작 | 법원경매 사이트 iframe 내 form 접근 불가 | v4.0 `@run-in-frame` + `window.top.location.hash` |

---

## 변경 이력

| 날짜 | 내용 |
|------|------|
| 2026-04 | 최초 구현 — 수원지방법원 아파트 경매목록 크롤링 |
| 2026-04 | 매각결과 수집 추가 (result_navigator, result_parser, Excel 시트2) |
| 2026-04 | 카카오맵 시각화 추가 (Python 서버측 REST API Geocoding) |
| 2026-04 | `open_map.py` 런처 추가, CP949 hostname 우회 처리 |
| 2026-04 | 매각결과 파란★ / 유찰 주황✕ 마커 분리 표시 |
| 2026-04 | 필터 전체/경매/낙찰/유찰 멀티 토글 전환 |
| 2026-04 | 법원경매 바로가기 + Tampermonkey v4.0 (@run-in-frame) |
| 2026-04 | README 정리 — 시트별 저장 정책(경매목록=전체교체 / 매각결과=누적), CSV 백업 역할, 데이터 흐름 명확화 |
