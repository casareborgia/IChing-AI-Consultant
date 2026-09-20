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

# 빌드 커밋 SHA 주입
ARG BUILD_GIT_SHA=""
ENV BUILD_GIT_SHA=${BUILD_GIT_SHA}

# 애플리케이션 코드 복사 및 소유권 변경
COPY --chown=appuser:appuser . .
COPY --chown=appuser:appuser prompts/ /app/prompts/

# 릴리즈 인수 증거 (acceptance-manifest.json이 존재하면 /app/release/로 복사)
RUN mkdir -p /app/release && chown -R appuser:appuser /app/release
COPY --chown=appuser:appuser acceptance-manifest.jso[n] /app/release/

# 모든 런타임 프롬프트 존재 검증 (하나라도 누락되면 이미지를 만들지 않는다)
RUN for prompt in safety_screening intake interpret counsel journal report; do \
      test -f "/app/prompts/${prompt}.md" || exit 1; \
    done

USER appuser

# Cloud Run 기본 포트 8080 노출
EXPOSE 8080

# ASGI 서버 실행 (Cloud Run 공식 exec 패턴 + 프록시 헤더 신뢰 대역 전달)
CMD exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8080} --forwarded-allow-ips="${FORWARDED_ALLOW_IPS:-127.0.0.1,::1,169.254.0.0/16}"
