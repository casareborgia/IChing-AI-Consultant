# Google Cloud Run 배포용 Dockerfile
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

WORKDIR /app

# 시스템 의존성 설치 (필요시)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 파이썬 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사
COPY . .

# Cloud Run 기본 포트 8080 노출
EXPOSE 8080

# ASGI 서버 실행 (앱 진입점에 맞춤 설정)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
