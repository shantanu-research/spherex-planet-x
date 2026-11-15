FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY . /app
RUN python scripts/download_observations.py
ENV PORT=8080
EXPOSE 8080
CMD ["python", "-m", "backend.server"]
