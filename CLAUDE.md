# CLAUDE.md — 프로젝트 컨텍스트 & 작업 가이드

## 프로젝트 개요

수원지방법원 아파트 경매 물건을 자동 수집하고 카카오맵으로 시각화하는 Python 크롤러.
Selenium + BeautifulSoup4 기반 크롤링, openpyxl Excel 저장, 카카오맵 JS + REST API 지도 생성.

---

## 핵심 파일 역할

| 파일 | 역할 |
|------|------|
| `main.py` | CLI 진입점. `--map` 플래그 있으면 크롤러 import 없이 지도만 생성 |
| `open_map.py` | `socket.getfqdn` monkey-patch 후 localhost:8080 서버 시작, 브라우저 오픈 |
| `config.py` | URL, API 키, 법원명, 딜레이 설정. `KAKAO_REST_API_KEY` 포함 |
| `storage/map_generator.py` | 카카오맵 HTML 생성. Geocoding, 캐시, HTML 빌더 모두 여기 |
| `storage/exporter.py` | CSV/Excel upsert. 경매목록(시트1) + 매각결과(시트2) |
| `crawler/navigator.py` | 경매목록 페이지네이션 탐색 |
| `crawler/result_navigator.py` | 매각결과 페이지 탐색 |
| `tampermonkey_auction.user.js` | 법원경매 사이트 사건번호 자동입력 (v4.0, @run-in-frame) |

---

## 아키텍처 — 지도 생성 흐름

```
courtauction_data.xlsx
  ├── 경매목록 시트  ──→ _read_excel()
  └── 매각결과 시트  ──→ _read_result_excel()
          ↓
  _geocode_items()        ← Kakao REST API (캐시: geocode_cache.json)
          ↓
  _build_items_json()     경매목록 → ITEMS JS 배열
  _build_result_items_json()  매각결과 → RESULT_ITEMS JS 배열
          ↓
  _build_html()           단일 HTML 파일 생성 (카카오 JS SDK 임베드)
          ↓
  output/auction_map.html
```

---

## 지도 마커 체계

- **경매목록**: 용도별 색상 핀 (아파트=빨강, 근린시설=파랑, 토지=녹색 등)
- **낙찰**: 파란 핀 + 금색 ★ (`makeResultMarkerImage('낙찰')`)
- **유찰**: 주황 핀 + 흰색 ✕ (`makeResultMarkerImage('유찰')`)

필터 버튼: **전체 / 경매 / ★ 낙찰 / ✕ 유찰** (멀티 토글, 독립 on/off)
- 전체 버튼: 셋 모두 켜진 상태면 전부 끄기, 아니면 전부 켜기
- `vis = { auction, nakchul, yuchal }` 객체로 상태 관리

---

## 중요 패턴 & 주의사항

### GitHub 파일 업로드
`git push`는 이 환경에서 자주 hanging됨. 반드시 GitHub REST API (`urllib`) 사용.
`upload_to_github()` 함수가 `storage/map_generator.py` 하단에 내장되어 있음.
토큰은 `git remote get-url origin`에서 추출 가능.

### 한국어 Windows CP949 인코딩
`socket.getfqdn()` → `gethostbyaddr()` → CP949 hostname → UTF-8 decode 실패.
`open_map.py`의 monkey-patch로 해결. 새 서버 코드 작성 시 동일 패턴 적용.

### Python f-string 내 JS 템플릿
`_build_html()`은 거대한 f-string. JS 중괄호는 모두 `{{`, `}}`으로 이스케이프.
JS 문자열 내 따옴표 충돌 방지: `data-*` 속성 방식 사용 (`dataset.case`).

### Geocode 캐시
`output/geocode_cache.json` — 성공한 좌표만 저장 (None 저장 안 함).
손상 시 자동 삭제 후 빈 캐시로 재시작. CP949/UTF-8 인코딩 자동 시도.

### Lazy Import (`main.py`)
`--map` 플래그 사용 시 Selenium/webdriver_manager import 스킵.
CP949 환경에서 `webdriver_manager` import 자체가 UnicodeDecodeError 유발하기 때문.

### Tampermonkey
법원경매 사이트는 frameset 구조 → form이 iframe 안에 있음.
`@run-in-frame` 필수. `window.top.location.hash`로 부모 URL에서 사건번호 읽음.
`searchAllFrames()` 함수로 2단계 중첩 프레임까지 DOM 탐색.

---

## Sub-Agent 파이프라인 (코드 변경 시)

```
[사용자 요청]
      ↓
project-planner   → PLAN.md 생성 (Opus, 읽기 + 웹검색)
      ↓
code-developer    → 코드 구현 (Sonnet, 읽기/쓰기/실행)
      ↓
code-reviewer     → 품질 검토 (Opus, 읽기 전용)
      ↓
tester            → 테스트 실행 및 판정 (Sonnet, 읽기/쓰기/실행)
```

재작업 루프:
- code-reviewer 🔴 Critical → code-developer 복귀
- tester FAIL → code-developer 복귀 (리뷰 재생략 가능)

---

## 컨벤션

- 테스트 파일: `tests/`
- 기획 문서: `PLAN.md` (루트)
- 모든 Python 파일 첫 줄: `# -*- coding: utf-8 -*-`
- Excel 파일명: `courtauction_data.xlsx` (고정)
- 지도 출력: `output/auction_map.html` (고정)
- 포트: `localhost:8080` (open_map.py)
