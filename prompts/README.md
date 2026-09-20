# IChing-AI-Consultant 에이전트 프롬프트

메인 저장소 [casareborgia/IChing-AI-Consultant](https://github.com/casareborgia/IChing-AI-Consultant)가 쓰는 에이전트 프롬프트를 담는다. 메인 저장소는 공개이고 이 파일들은 공개 대상이 아니므로 거기서는 `.gitignore`로 빠져 있다. 이 저장소가 프롬프트의 유일한 원격 사본이다.

## 배치

메인 저장소의 `prompts/` 디렉터리가 곧 이 저장소의 작업 디렉터리다. 파일을 옮기지 않으므로 백엔드 코드(`core/prompts.py`)와 배포 경로(`.gcloudignore`의 `!prompts/**`)가 그대로 동작한다.

```
IChing-AI-Consultant/        <- 공개 저장소
  prompts/                   <- 이 저장소 (중첩)
    counsel.md
    ...
```

메인 저장소는 `prompts/*.md`를 무시하고 `prompts/.gitkeep`만 추적한다. Git은 어느 위치에서든 `.git` 디렉터리를 무시하므로 중첩되어도 메인 저장소가 더러워지지 않는다.

## 새 머신에서 복원

메인 저장소를 클론한 뒤, 비어 있는 `prompts/`를 이 저장소로 채운다.

```bash
git clone https://github.com/casareborgia/IChing-AI-Consultant.git
cd IChing-AI-Consultant
rm -rf prompts
git clone https://github.com/casareborgia/iching-prompts.git prompts
```

프롬프트 없이는 백엔드가 임포트 단계에서 죽는다(`core/prompts.py`가 `FileNotFoundError`를 낸다). 배포용 이미지를 빌드하기 전에 반드시 이 단계를 거쳐야 한다.

## 수정

`prompts/`에서 바로 고치고 이 저장소에 커밋한다. 메인 저장소에는 잡히지 않는다.

```bash
cd prompts
git add -A && git commit -m "..." && git push
```

## 파일

| 파일 | 용도 |
| --- | --- |
| `counsel.md` | 상담 대화 에이전트 |
| `duplicate_response.md` | 재삼독(중복 질문) 응답 |
| `intake.md` | 최초 질문 정제 |
| `interpret.md` | 괘 해석 |
| `journal.md` | 최종 저널 발급 |
| `rag_translation.md` | 고전 원문 번역 |
| `report.md` | 4단계 컨설팅 리포트 |
| `safety_response.md` | 위기 대응 응답 |
| `safety_screening.md` | 위기 판정 |

## 이력

`report.md`는 2026-09-07에 메인 저장소에 `git add -f`로 잘못 추가되어 공개 노출됐다. 히스토리 재작성으로 제거했으나 옛 커밋 SHA로는 아직 읽힌다. 경위는 메인 저장소의 `docs/HANDOFF_2026-09-07_REPORT_CONTEXT.md` "공개 히스토리 정리" 절에 있다.
