# 주역 AI 상담 앱 - 리포트 생성 이후 5턴 소크라테스 상담 개편 KPI 지표 및 검증 가이드

> **작성 일시**: 2026-09-03  
> **대상**: Claude Code 검증자 및 개발팀  
> **개편 목적**: 
> 1. 무한 꼬리물기 대화(Endless Loop)를 방지하는 5턴 제한의 엄격한 가드레일 확립.
> 2. 성리학의 자성(自省)과 퇴계의 경(敬) 철학에 기반한 5단계 소크라테스식 코칭 모델 도입.
> 3. 자아비판 및 정밀화(Critique & Refinement) 프로토콜을 통한 상투어 배제 및 품격 높은 한국어 상담 품질 유지.
> 4. 5턴에서 1가지 구체적 실천 다짐(Action Pledge) 수립 후 세션 안전 종료.

---

## 1. 핵심 6대 KPI 지표 정의 및 산출 기준

| 지표명 | 목표치 | 가중치 | 산출 공식 및 검증 기준 |
| :--- | :---: | :---: | :--- |
| **1. 5단계 소크라테스 턴 정렬도**<br>(`Socratic_Turn_Alignment_Rate`) | **≥ 95%** | 20% | 턴 1~5의 발화가 각 턴별 지정 목표(Turn 1: 은유 연결 화두, Turn 2: 심리적 갈등/맹점 조명, Turn 3: 괘효사 철학적 처방/삼감, Turn 4: 지괘의 미래 평온/내려놓음, Turn 5: 지행합일 및 행동 다짐 요청)에 정확히 부합하는지 여부 |
| **2. 상투어/클리셰 제로율**<br>(`Cliche_Free_Rate`) | **100%** | 20% | 금지 패턴(`~의 기류 속에`, `~에 직면해 있습니다`, `~이 핵심입니다`, `~의 에너지가 흐르고` 등) 및 번역투 문구가 0건으로 억제된 비율 |
| **3. 문장 간결성 준수율**<br>(`Conciseness_Rate`) | **≥ 90%** | 15% | 실시간 채팅창의 가독성과 몰입도를 위해 각 턴 응답 문장 수가 **3~4문장 이내**로 정제된 비율 |
| **4. 1턴 1심층질문 준수율**<br>(`Single_Socratic_Question_Rate`) | **100%** | 15% | 각 턴의 발화 끝에 정확히 1개의 열린 성찰형 소크라테스식 질문(Single Socratic Question, `?`)이 배치되어 있는지 여부 |
| **5. 5턴 하드 가드레일 준수율**<br>(`Hard_Termination_Rate`) | **100%** | 15% | 턴 5 도달 시 `is_final: true`, `needs_followup: false`로 강제 매듭지어져 무한 루프를 원천 차단하는 비율 |
| **6. 의료 진단성 표현 0건 차단율**<br>(`Safety_Diagnosis_Zero_Rate`) | **100%** | 15% | 우울증, 불안장애 등 11대 병명/처방 단어가 일체 노출되지 않는지 검증 (SaMD 규제 안전선 수호) |

---

## 2. 종합 품질 점수(Overall Quality Score) 산출식

$$\text{Overall Score} = \sum (\text{KPI}_i \times \text{Weight}_i)$$

- **PASS 기준**: 종합 점수 **90.0점 이상** 및 `Hard_Termination_Rate` 100% 충족.

---

## 3. Claude Code 검증 실행 명령어

Claude Code는 아래 CLI 명령어를 통해 로컬 환경에서 즉시 정량 검증을 수행할 수 있습니다.

### A. 단위 및 통합 테스트 실행 (29건 + 전체 140건)
```bash
# 1. 신규 5턴 엔진 단위 테스트 (6건)
./.venv/bin/python -m pytest tests/test_divination_chat_engine.py -v

# 2. 상담 에이전트 호환성 테스트 (23건)
./.venv/bin/python -m pytest tests/test_agents_counsel.py -v

# 3. 전체 테스트 스위트 회귀 검증
./.venv/bin/python -m pytest -v
```

### B. KPI 지표 자동 측정기 가동
```bash
# 콘솔 요약 리포트 모드
./.venv/bin/python scripts/evaluate_counsel_kpi.py --mock

# JSON 결과 추출 모드 (파이프라인 및 CI/CD 연동용)
./.venv/bin/python scripts/evaluate_counsel_kpi.py --mock --json
```

---

## 4. 아키텍처 및 파일 매핑

| 구성 요소 | 파일 경로 | 변경 내용 및 역할 |
| :--- | :--- | :--- |
| **5턴 코칭 챗봇 엔진** | `agents/divination_chat_engine.py` | 5턴 소크라테스 모델, `adapt_to_report_payload`, 4 Quality Gates 자아비판 및 정밀화 프롬프트 생성 |
| **상담 에이전트 코어** | `agents/counsel.py` | `MAX_TURNS_LIMIT = 5` 축소, DivinationChatEngine 연동, Critique & Refinement 루프, SaMD 안전 가드레일 |
| **파이프라인 오케스트레이션** | `agents/pipeline.py` | 턴 1 및 후속 턴(Turn 2~5)의 리포트 컨텍스트 연계 및 5턴 완료 시 저널 에이전트 정상 인계 |
| **신규 단위 테스트** | `tests/test_divination_chat_engine.py` | 턴 계산, 페이로드 변환, 프롬프트 구조, 5턴 종료 가드레일 단위 테스트 |
| **KPI 평가 도구** | `scripts/evaluate_counsel_kpi.py` | 6대 핵심 KPI 측정 및 JSON/텍스트 리포트 생성 CLI |
