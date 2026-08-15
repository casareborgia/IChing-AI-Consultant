"""마크다운 파일에서 시스템 프롬프트를 일관되게 추출하는 로더.

- prompts/<name>.md 파일 내의 '## 시스템 프롬프트' 아래 첫 코드펜스(```...```)를 추출
- 채점기, 에이전트, 데모가 모두 동일한 프롬프트 파일을 바라보도록 보장
"""

from pathlib import Path
import re

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def load_system_prompt(name: str) -> str:
    """prompts/<name>.md 파일에서 시스템 프롬프트 본문을 추출합니다.

    Args:
        name: 프롬프트 파일명 (확장자 .md 생략 가능)
              예: "safety_screening", "intake", "interpret", "counsel", "journal"

    Returns:
        추출된 시스템 프롬프트 문자열 (앞뒤 공백 정제)
    """
    file_name = name if name.endswith(".md") else f"{name}.md"
    file_path = PROMPTS_DIR / file_name

    if not file_path.exists():
        raise FileNotFoundError(f"프롬프트 파일을 찾을 수 없습니다: {file_path}")

    md = file_path.read_text(encoding="utf-8")
    header_idx = md.find("## 시스템 프롬프트")
    if header_idx == -1:
        raise ValueError(f"'{file_name}'에서 '## 시스템 프롬프트' 섹션을 찾지 못했습니다.")

    match = re.search(r"```[^\n]*\n(.*?)```", md[header_idx:], re.DOTALL)
    if not match:
        raise ValueError(f"'{file_name}'의 '## 시스템 프롬프트' 아래 코드펜스(```)를 찾지 못했습니다.")

    return match.group(1).rstrip("\n")
