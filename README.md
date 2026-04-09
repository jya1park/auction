# 법원경매 크롤러 (Court Auction Crawler)

수원지방법원 경매 물건(아파트 등)을 자동 수집하고 Excel 및 카카오맵으로 시각화하는 Python 크롤러입니다.

## 주요 기능

- **경매 목록 수집** - 수원지방법원 아파트 물건 자동 크롤링 (3단계 용도 선택: 건물 > 주거용건물 > 아파트)
- **매각결과 수집** - 동일 조건으로 매각결과 페이지 크롤링 (RESULT_URL: PGJ158)
- **Excel 누적 저장** - 단일 파일(`courtauction_data.xlsx`)에 누적 저장, 실행마다 upsert
  - 시트1: 경매목록 (파란 헤더)
  - 시트2: 매각결과 (보라 헤더)
  - 업데이트일시 컬럼 포함
- **카카오맵 시각화** - `auction_map.html` 자동 생성, 마커 클릭 시 상세정보 팝업
- **찜한 물건 낙찰 조회** - 사건번호를 연도/유형/번호로 분리해서 3개 필드에 입력

## 프로젝트 구조

```
courtauction_crawler/
├── main.py                    # 메인 실행 파일
├── config.py                  # 설정값 (URL, 법원명, 용도 등)
├── crawler/
│   ├── driver.py              # Chrome WebDriver 초기화 (WinError 193, UnicodeError 패치 포함)
│   ├── navigator.py           # 경매 목록 페이지 탐색 (3단계 용도 선택)
│   ├── list_parser.py         # 경매 목록 HTML 파싱
│   ├── result_navigator.py    # 매각결과 페이지 탐색
│   └── result_parser.py       # 매각결과 HTML 파싱
├── storage/
│   ├── exporter.py            # Excel/CSV 저장 (누적 upsert)
│   └── map_generator.py       # 카카오맵 HTML 생성
└── output/
    ├── courtauction_data.xlsx  # 누적 Excel 파일
    ├── courtauction_*.csv      # 실행별 CSV
    └── auction_map.html        # 카카오맵 시각화
```

## 설치 방법

**필요 환경**
- Python 3.8 이상
- Google Chrome 브라우저

**패키지 설치**
```bash
pip install selenium webdriver-manager openpyxl beautifulsoup4
```

## 실행 방법

```bash
cd courtauction_crawler
python main.py
```

실행 순서:
1. 경매 목록 크롤링 → Excel 시트1 저장
2. 매각결과 크롤링 → Excel 시트2 저장
3. 카카오맵 HTML 생성 (`output/auction_map.html`)

## 설정 (config.py)

| 항목 | 기본값 | 설명 |
|------|--------|------|
| TARGET_COURT | 수원지방법원 | 대상 법원 |
| TARGET_TYPE | 아파트 | 물건 종류 |
| WAIT_TIMEOUT | 15 | 페이지 대기 시간(초) |
| PAGE_DELAY | 2.0 | 페이지 간 딜레이(초) |
| SEARCH_URL | PGJ151F00 | 경매 목록 URL |
| RESULT_URL | PGJ158F00 | 매각결과 URL |

용도 변경 예시 (`navigator.py` CATEGORY_MAP):
- 아파트: 건물 > 주거용건물 > 아파트
- 다세대: 건물 > 주거용건물 > 다세대주택
- 오피스텔: 건물 > 주거용건물 > 오피스텔

## 카카오맵 지도 보는 방법

### 1단계 - 카카오 개발자 콘솔 도메인 등록 (최초 1회)
1. [developers.kakao.com](https://developers.kakao.com) 접속
2. 내 애플리케이션 → 앱 선택 → 플랫폼 → Web
3. 사이트 도메인에 `http://localhost:8000` 추가 후 저장

### 2단계 - 로컬 서버 실행
```bash
cd output
python -m http.server 8000
```

### 3단계 - 브라우저에서 접속
```
http://localhost:8000/auction_map.html
```

> ⚠️ `file://`로 직접 열면 카카오 API 인증 거부로 지도가 표시되지 않습니다.

## 알려진 이슈 및 해결법

### WinError 193 - 올바른 Win32 응용 프로그램이 아닙니다
- **원인**: `webdriver-manager`의 `install()`이 `chromedriver.exe` 대신 `THIRD_PARTY_NOTICES.chromedriver` 파일 경로를 반환
- **해결**: `crawler/driver.py`에서 반환 경로 디렉터리에서 `chromedriver.exe` 직접 탐색

### UnicodeDecodeError - utf-8 codec can't decode byte 0xb6
- **원인**: 한국어 Windows에서 PowerShell 출력이 CP949 인코딩으로 나오는데 webdriver-manager가 UTF-8로 디코딩 시도
- **해결**: `crawler/driver.py`에서 `webdriver_manager.core.utils`의 디코딩 함수를 `errors='ignore'` 패치로 교체

### 매각결과 데이터 없음
- **확인사항**: `config.py`의 `RESULT_URL`이 PGJ158인지 확인
- 검색 조건(법원, 용도)이 실제 데이터와 일치하는지 확인 필요

## 변경 이력

| 날짜 | 내용 |
|------|------|
| 2026-04 | 최초 구현 - 수원지방법원 아파트 경매 목록 크롤링 |
| 2026-04 | lxml → html.parser 변경 (파서 오류 수정) |
| 2026-04 | 용도 선택 2단계 → 3단계 (건물 > 주거용건물 > 아파트) |
| 2026-04 | Excel 누적 저장 방식으로 변경 + 업데이트일시 컬럼 추가 |
| 2026-04 | 매각결과 수집 기능 추가 (시트2, result_navigator.py) |
| 2026-04 | 찜한 물건 낙찰조회 3필드 입력 방식으로 수정 |
| 2026-04 | 카카오맵 시각화 추가 (map_generator.py) |
| 2026-04 | WinError 193 수정 (chromedriver 직접 탐색) |
| 2026-04 | UnicodeDecodeError 수정 (subprocess 패치) |
