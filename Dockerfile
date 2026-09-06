# Google Cloud Run 배포용 Dockerfile
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

WORKDIR /app

# 시스템 의존성 설치
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 파이썬 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 비루트 사용자 생성 및 소유권 설정
RUN useradd -u 1000 -m appuser

# 애플리케이션 코드 복사 및 소유권 변경
COPY --chown=appuser:appuser . .
COPY --chown=appuser:appuser prompts/ /app/prompts/

# 프롬프트 파일 존재 검증 (빌드 타임 안전망)
RUN test -f /app/prompts/safety_screening.md && ls -la /app/prompts/

USER appuser

# Cloud Run 기본 포트 8080 노출
EXPOSE 8080

# ASGI 서버 실행 (Cloud Run 공식 exec 패턴)
CMD exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8080}
