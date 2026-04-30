# 빨간우체통 (RedMailbox)

같은 LAN 안의 윈도우 PC끼리 **메모**와 **대용량 파일**을 빠르게 주고받는
윈도우 트레이 앱.

## 특징

- 🔴 윈도우 시스템 트레이에 빨간 우체통 아이콘 상주
- ✉️ **메모 보내기** — 짧은 텍스트를 즉시 전송
- 📦 **대용량 파일 보내기** — 청크 스트림으로 메모리 부담 없이 전송, 진행률 표시
- 📥 받으면 트레이 아이콘이 깜빡여 알림 (10초). 클릭하면 받은 목록 창
- 🌐 IP 주소를 직접 입력하거나 최근 IP 드롭다운에서 선택
- 📁 받은 파일 저장 폴더는 트레이 메뉴 → 설정에서 변경 가능
- 🇰🇷 한글 메모/한글 파일명 지원 (CP949 환경 회피 처리)

## 동작 방식

```
┌─ PC A (송신) ─────────────────┐         ┌─ PC B (수신) ─────────────────┐
│ 트레이 우클릭 → "메모 보내기"   │  HTTP   │ HTTP 서버 0.0.0.0:8765        │
│   IP 192.168.0.42 입력         │  POST   │   /memo, /file, /ping         │
│   → POST /memo                 │ ──────▶ │ → DB 기록 + 트레이 깜빡임 시작 │
└────────────────────────────────┘         └────────────────────────────────┘
```

- 수신측은 백그라운드 HTTP 서버 (`0.0.0.0:8765`, 변경 가능)
- 인증 없음 — **LAN 전용**. 외부 노출된 PC에선 사용 금지
- Windows 방화벽이 1차 차단. 첫 실행 시 OS 다이얼로그에서 "허용" 클릭

## 설치 / 실행

### 개발 모드

```cmd
cd redmailbox
python -m pip install -r requirements.txt
python redmailbox.py
```

### .exe 배포 빌드

```cmd
cd redmailbox
build.bat
```

결과: `dist\RedMailbox.exe` (단일 파일, Python 미설치 PC에서도 실행).

## 사용법

1. 양쪽 PC에서 `RedMailbox.exe` 실행 → 트레이에 빨간 우체통 아이콘 표시
2. 트레이 아이콘에 마우스 올리면 **자기 IP**가 툴팁으로 보임 — 상대방에게 알려줌
3. 우클릭 → **메모 보내기** 또는 **대용량 파일 보내기**
4. 받는 사람의 IP 입력 (`192.168.0.42` 또는 `192.168.0.42:8765`)
5. 보내기. 상대방 트레이 아이콘이 깜빡임 → 클릭 → 받은 목록에서 확인

## 트레이 메뉴

| 항목 | 동작 |
|------|------|
| 내 IP: `x.x.x.x:port` | 표시만 (클릭 불가) |
| 메모 보내기 | 텍스트 전송 다이얼로그 |
| 대용량 파일 보내기 | 파일 선택 + 진행률 다이얼로그 |
| 받은 목록 (n) | 받은 항목 리스트. 메모 더블클릭=본문, 파일 더블클릭=열기 |
| 설정 | 저장 폴더 / 포트 변경 |
| 종료 | 앱 완전 종료 |

좌클릭 = "받은 목록" 단축.

## 환경변수 (개발 편의)

| 변수 | 용도 | 기본값 |
|------|------|--------|
| `REDMAIL_PORT` | HTTP 포트 오버라이드 | `8765` |
| `REDMAIL_SAVE` | 저장 폴더 오버라이드 | `~/Downloads/RedMailbox` |
| `REDMAIL_DEBUG` | 콘솔 + 파일 디버그 로그 | (off) |

## 단일 PC 듀얼 프로세스 테스트

```cmd
:: 인스턴스 A
set REDMAIL_PORT=8765 && set REDMAIL_SAVE=%USERPROFILE%\Desktop\inbox_A && python redmailbox.py

:: 다른 cmd 창 — 인스턴스 B
set REDMAIL_PORT=8766 && set REDMAIL_SAVE=%USERPROFILE%\Desktop\inbox_B && python redmailbox.py
```

A → 메모 보내기 → IP `127.0.0.1`, 포트 `8766` → B 트레이 깜빡임 확인.

자동화된 라운드트립 테스트:

```cmd
cd redmailbox
python tests/test_roundtrip.py
```

## 데이터 위치

| 항목 | 경로 |
|------|------|
| 받은 파일 | 설정에서 지정 (기본 `~/Downloads/RedMailbox/`) |
| 설정 | `%LOCALAPPDATA%\RedMailbox\settings.json` |
| 받은 항목 DB | `%LOCALAPPDATA%\RedMailbox\history.db` |
| 로그 | `%LOCALAPPDATA%\RedMailbox\redmailbox.log` |

## 폴더 구조

```
redmailbox/
├── redmailbox.py            # 진입점
├── requirements.txt
├── build.bat                # PyInstaller 빌드
├── generate_assets.py       # 아이콘 PNG/ICO 생성
├── core/                    # 설정, 영속화, 경로 헬퍼, CP949 패치
├── server/                  # HTTP 서버 (handler, http_server, storage)
├── client/                  # urllib 송신 (sender)
├── tray/                    # pystray 트레이 + 깜빡임
├── ui/                      # tkinter 다이얼로그
├── assets/                  # PNG / ICO (build 시 생성)
└── tests/                   # 라운드트립 테스트
```

## 보안 주의

- 같은 LAN 내부 사용 전제. 인증 없음.
- 외부 인터넷에 직접 노출된 PC(공유기 DMZ, 클라우드 VM)에서 사용 금지.
- Windows 방화벽 "허용" 다이얼로그가 처음 뜨면 **개인 네트워크만** 체크 권장.
