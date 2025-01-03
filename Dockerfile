FROM python:3.11-slim

WORKDIR /app

# 필수 패키지 설치
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
COPY commands ./commands
COPY services ./services
COPY main.py ./
COPY .env ./


RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "main.py"]
