# 크로미움이 미리 설치된 공식 Playwright 이미지 (버전은 requirements.txt와 맞춤)
FROM mcr.microsoft.com/playwright/python:v1.46.0-jammy

WORKDIR /app

# playwright는 베이스 이미지에 이미 있으므로 나머지만 설치
RUN pip install --no-cache-dir \
      gspread==6.1.2 \
      google-auth==2.33.0 \
      requests==2.32.3

COPY *.py ./

# 상태 파일은 마운트된 /data 볼륨에 영속 저장
ENV WATCHER_STATE_PATH=/data/state.json

CMD ["python", "main.py"]
