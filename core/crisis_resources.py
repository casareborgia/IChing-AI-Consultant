"""한국 위기상담 및 긴급 지원 공공 리소스 DB 모듈.

보건복지부 및 여성가족부 기준(2024년 109 통합) 공식 위기상담 핫라인 정보를 구조화하여 제공합니다.
"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class CrisisResource(BaseModel):
    id: str = Field(..., description="리소스 식별자")
    name: str = Field(..., description="기관 및 상담 서비스명")
    tel: str = Field(..., description="전화번호 (단축번호 또는 일반번호)")
    hours: str = Field(..., description="운영 시간")
    categories: List[str] = Field(default_factory=list, description="지원 분야 태그")
    description: str = Field(..., description="간략 설명 및 지원 대상")
    online_url: Optional[str] = Field(None, description="온라인 상담/홈페이지 링크")


# 2024년 최신화된 대한민국 위기상담 대표 리소스 DB
KOREAN_CRISIS_RESOURCES: Dict[str, CrisisResource] = {
    "109": CrisisResource(
        id="109",
        name="자살예방 상담전화",
        tel="109",
        hours="24시간 연중무휴",
        categories=["자살예방", "극단선택", "위기상담", "정신건강"],
        description="전문 상담사가 24시간 위기 상담 및 응급 개입을 지원합니다.",
        online_url="https://www.109.go.kr",
    ),
    "1577-0199": CrisisResource(
        id="1577-0199",
        name="정신건강 상담전화",
        tel="1577-0199",
        hours="24시간 연중무휴",
        categories=["정신건강", "우울", "불안", "심리상담"],
        description="전국 정신건강복지센터와 연계하여 심리 상담을 제공합니다.",
        online_url="https://www.mentalhealth.go.kr",
    ),
    "1388": CrisisResource(
        id="1388",
        name="청소년 상담전화",
        tel="1388",
        hours="24시간 연중무휴",
        categories=["청소년", "학업/진로", "가족갈등", "친구관계", "위기청소년"],
        description="청소년 및 학부모를 위한 심리 상담 및 긴급 구조 연계를 지원합니다.",
        online_url="https://www.cyber1388.kr",
    ),
    "1366": CrisisResource(
        id="1366",
        name="여성긴급전화",
        tel="1366",
        hours="24시간 연중무휴",
        categories=["여성", "가정폭력", "데이트폭력", "성폭력", "긴급피신"],
        description="폭력 피해 여성을 위한 긴급 상담 및 쉼터 연계, 현장 출동을 지원합니다.",
        online_url="https://www.women1366.kr",
    ),
}


def get_all_crisis_resources() -> List[CrisisResource]:
    """전체 위기 상담 리소스 목록을 반환합니다."""
    return list(KOREAN_CRISIS_RESOURCES.values())


def get_crisis_resources_by_context(context: Optional[str] = None) -> List[CrisisResource]:
    """정황(context: minor, violence, general)에 따라 우선순위가 정렬된 리소스 목록을 반환합니다."""
    all_res = KOREAN_CRISIS_RESOURCES

    if context == "minor":
        # 청소년 우선: 1388 -> 109 -> 1577-0199 -> 1366
        order = ["1388", "109", "1577-0199", "1366"]
    elif context == "violence":
        # 폭력 피해 우선: 1366 -> 109 -> 1577-0199 -> 1388
        order = ["1366", "109", "1577-0199", "1388"]
    else:
        # 기본: 109 -> 1577-0199 -> 1388 -> 1366
        order = ["109", "1577-0199", "1388", "1366"]

    return [all_res[key] for key in order if key in all_res]
