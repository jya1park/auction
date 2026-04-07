# CLAUDE.md — Sub-Agent 파이프라인 설정

## 워크플로우 개요

```
[사용자 요청]
      ↓
project-planner   → PLAN.md 생성
      ↓
code-developer    → 코드 구현
      ↓
code-reviewer     → 품질 검토 (읽기 전용)
      ↓
tester            → 테스트 실행 및 판정
```

---

## Sub-Agent 라우팅 규칙

### 순차 실행 (항상 이 순서 유지)
기획 → 개발 → 리뷰 → 테스트는 반드시 순서대로 실행.
앞 단계 산출물이 다음 단계의 입력이 되므로 병렬 실행 금지.

### 재작업 루프
- code-reviewer에서 🔴 Critical 발견 → code-developer로 복귀
- tester에서 FAIL 발생 → code-developer로 복귀 (리뷰 재생략 가능)

### 단계 건너뛰기 규칙
- 사용자가 명시적으로 요청한 경우에만 단계 생략 가능
- 예: "리뷰 없이 바로 테스트해줘" → code-reviewer 생략

---

## 각 Agent 역할 요약

| Agent | 모델 | 권한 | 산출물 |
|-------|------|------|--------|
| project-planner | Opus | 읽기 + 웹검색 | PLAN.md |
| code-developer | Sonnet | 읽기/쓰기/실행 | 소스 코드 |
| code-reviewer | Opus | 읽기 전용 | 리뷰 보고서 |
| tester | Sonnet | 읽기/쓰기/실행 | 테스트 결과 |

---

## 프로젝트 컨벤션

- 테스트 파일 위치: `tests/`
- 기획 문서 위치: `PLAN.md` (루트)
- 언어별 컨벤션: 프로젝트 언어에 맞게 자동 적용
