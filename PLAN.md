# 대법원 경매 크롤러 구현 계획 (PLAN.md)

> **작성일**: 2026-04-06
> **대상 사이트**: https://www.courtauction.go.kr/
> **목표**: 수원지방법원 아파트 경매 정보 수집 + 낙찰 결과 조회

---

## 0. 사이트 구조 분석 (리서치 결과)

### 0.1 기술 스택 (대법원 경매 사이트)

대법원 경매 사이트는 **WebSquare(w2x)** 프레임워크 기반으로 동작한다. WebSquare는 국내 공공기관에서 자주 쓰이는 XML 기반 JavaScript UI 프레임워크로, 다음 특징이 있다:

- URL 패턴: `https://www.courtauction.go.kr/pgj/index.on?w2xPath=/pgj/ui/pgj100/[PAGE].xml`
- 서버 액션: `.laf` 확장자 엔드포인트 (예: `RetrieveRealEstDetailInqSaList.laf`)
- iframe 내에서 콘텐츠 렌더링 (`indexFrame` 또는 유사한 이름)
- 모든 화면 전환이 JavaScript 이벤트로 처리됨 → URL 직접 접근 불가

### 0.2 주요 URL 및 페이지 구조

| 페이지 | URL / w2xPath | 설명 |
|--------|--------------|------|
| 메인 | `/pgj/index.on?device=pc` | 진입점 |
| 물건일반검색 | `/pgj/ui/pgj100/PGJ151F00.xml` | 법원+물건종류 검색 |
| 물건상세검색 | `/pgj/ui/pgj100/PGJ153F00.xml` | 조건 세분화 검색 |
| 경매사건검색 | `/pgj/ui/pgj100/PGJ159M00.xml` | 사건번호로 조회 |
| 관심물건(찜) | `/pgj/ui/pgj100/PGJ193M01.xml` | 관심 등록 목록 |
| 낙찰결과 조회 | `RetrieveRealEstDetailInqSaList.laf` | 낙찰가/응찰자 수 조회 |

### 0.3 실제 확인된 DOM 요소

| 요소 | ID | 역할 |
|------|----|------|
| 법원 선택 드롭다운 | `mf_wfm_mainFrame_sbx_rletCortOfc` | 수원지방법원 선택 |
| 물건종류 대분류 | `mf_wfm_mainFrame_sbx_rletLclLst` | 건물/토지 선택 |
| 물건종류 중분류 | `mf_wfm_mainFrame_sbx_rletMclLst` | 아파트 선택 |
| 결과 테이블 | `tbody tr` | 경매 목록 (8셀+3셀 2행 구조) |

### 0.4 테이블 구조 (실제 분석 결과)

각 물건은 **2개 행**으로 구성됨:
- **8셀 메인 행**: [체크박스, 사건번호, 물건번호, 소재지/면적, 용도, 비고, 감정평가액, 최저입찰가/기일]
- **3셀 상세 행**: [진행상태, 최저입찰가(비율%), 유찰횟수]

### 0.5 수집 대상 필드

**경매 목록**: 사건번호, 법원, 물건번호, 물건주소, 용도, 비고, 감정평가액, 최저입찰가, 최저입찰가율, 입찰기일, 유찰횟수, 진행상태

**낙찰 결과 (찜한 물건)**: 낙찰가, 낙찰가율, 응찰자수

---

## 1. 요구사항 분석

### 1.1 핵심 기능 (Must-have)

| # | 기능 | 우선순위 |
|---|------|---------|
| F1 | 수원지방법원 + 아파트 조건으로 경매 목록 수집 | 필수 |
| F2 | 12개 필드 파싱 | 필수 |
| F3 | 사건번호 입력 → 낙찰가/낙찰가율/응찰자수 조회 | 필수 |
| F4 | CSV 저장 (utf-8-sig) | 필수 |
| F5 | Excel 저장 (openpyxl) | 필수 |
| F6 | CLI 인터페이스 | 필수 |
| F7 | 터미널 진행 상황 출력 | 필수 |

### 1.2 부가 기능 (Nice-to-have)

- N1: 감정가 대비 최저입찰가 비율 자동 계산
- N2: 복수 페이지 자동 순회 (`--pages N`)
- N3: 헤드리스/가시 모드 전환 (`--visible`)
- N4: 디버그 모드 (`--debug`)

### 1.3 사용자 스토리

```
US-1: 경매 투자자로서, 수원지방법원 아파트 경매 목록을 자동으로 수집하여
      Excel 파일로 저장하고 싶다.

US-2: 관심 물건(찜)의 사건번호를 입력하면, 낙찰가와 응찰자수를 확인하여
      향후 입찰 전략을 수립하고 싶다.

US-3: 크롤링 중에 터미널에서 진행 상황을 실시간으로 확인하고 싶다.
```

---

## 2. 기술 설계

### 2.1 기술 스택

| 라이브러리 | 선정 이유 |
|-----------|----------|
| `selenium` 4.x | JS 렌더링 + iframe 처리 필수 |
| `webdriver-manager` 4.x | ChromeDriver 자동 버전 관리 |
| `beautifulsoup4` 4.x | HTML 파싱 (page_source 활용) |
| `pandas` 2.x | 데이터 처리 + CSV/Excel 저장 |
| `openpyxl` 3.x | pandas Excel 저장 백엔드 |
| `argparse` stdlib | CLI 인터페이스 |

### 2.2 프로젝트 구조

```
courtauction_crawler/
├── main.py                  # CLI 진입점
├── config.py                # 상수 및 설정값
├── requirements.txt
├── crawler/
│   ├── __init__.py
│   ├── driver.py            # WebDriver 초기화/관리
│   ├── navigator.py         # 사이트 탐색 (iframe, 검색 조건)
│   ├── list_parser.py       # 경매 목록 파싱
│   └── detail_parser.py     # 낙찰 결과 파싱
└── storage/
    ├── __init__.py
    └── exporter.py          # CSV / Excel 저장
```

### 2.3 핵심 구현 패턴

```python
# iframe 전환
WebDriverWait(driver, 15).until(
    EC.frame_to_be_available_and_switch_to_it("indexFrame")
)

# 드롭다운 선택 (인코딩 안전한 JS 방식)
codes = [str(ord(c)) for c in "수원지방법원"]
js = f"""
var sel = document.getElementById('mf_wfm_mainFrame_sbx_rletCortOfc');
var target = String.fromCharCode.apply(null, [{','.join(codes)}]);
for(var i=0; i<sel.options.length; i++) {{
    if(sel.options[i].text.indexOf(target) >= 0) {{
        sel.selectedIndex = i;
        sel.dispatchEvent(new Event('change', {{bubbles:true}}));
        return 'ok:' + sel.options[i].text;
    }}
}}
"""
```

---

## 3. 구현 계획

### Phase 0: 환경 설정 (난이도: 쉬움)
- requirements.txt, config.py 작성

### Phase 1: 디버그 탐색 (난이도: 보통) ← 가장 중요
- 실제 DOM 구조 파악 (iframe명, 드롭다운 ID, 테이블 구조)
- **실제 확인 결과**: WebSquare 프레임워크, `mf_wfm_mainFrame_sbx_*` 패턴 ID

### Phase 2: WebDriver 모듈 (난이도: 쉬움)
- `crawler/driver.py`: headless/visible 옵션, automation 감지 우회

### Phase 3: Navigator 구현 (난이도: 어려움)
- `crawler/navigator.py`: iframe 전환, JS 기반 드롭다운 선택, 검색 실행

### Phase 4: Parser 구현 (난이도: 보통)
- `crawler/list_parser.py`: 8셀+3셀 쌍 파싱, 사건번호 정규화
- `crawler/detail_parser.py`: 낙찰 결과 파싱

### Phase 5: Exporter (난이도: 쉬움)
- `storage/exporter.py`: CSV(utf-8-sig) + Excel(컬럼 너비 자동 조정)

### Phase 6: CLI (난이도: 쉬움)
- `main.py`: argparse, 크롤링/찜조회 분기, 오류 시 부분 저장

---

## 4. CLI 인터페이스

```
python main.py              # 기본 실행 (headless, 전체 페이지)
python main.py --visible    # 브라우저 창 표시
python main.py --pages 5    # 5페이지만 수집
python main.py --watchlist  # 찜한 물건 낙찰 조회 (대화형 사건번호 입력)
python main.py --excel      # Excel도 저장
python main.py --debug      # 디버그 모드 (DOM 구조 출력)
python main.py --court "수원지방법원" --type "아파트"
```

---

## 5. 테스트 계획

| 테스트 항목 | 통과 기준 |
|------------|----------|
| 드라이버 초기화 | 타임아웃 없이 로딩 |
| 법원/물건종류 선택 | JS 방식으로 수원지방법원 + 건물/아파트 선택 성공 |
| 목록 파싱 | items > 0, 사건번호 정규화 정상 |
| 금액 파싱 | "350,000,000" → 350000000 |
| 사건번호 정규화 | "2022타경568612022타경2574" → "2022타경56861" |
| CSV 저장 | utf-8-sig, 컬럼 12개 |
| Excel 저장 | 한글 깨짐 없음, 컬럼 너비 조정 |

---

## 6. 주의사항

1. **WebSquare 프레임워크**: 일반 `Select` 클래스 미작동 → JavaScript 실행으로 대체
2. **iframe 중첩**: `switch_to.default_content()` → `switch_to.frame()` 순서 준수
3. **요청 간 딜레이**: 페이지 이동 후 최소 1.5~2초 대기
4. **사건번호 정규화**: non-greedy regex + lookahead로 중복 제거
5. **2행 테이블 구조**: 8셀(메인) + 3셀(상세) 쌍으로 파싱
