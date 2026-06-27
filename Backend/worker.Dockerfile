FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
  && apt-get install -y --no-install-recommends ffmpeg curl fonts-dejavu-core \
  && pip install --no-cache-dir yt-dlp \
  && rm -rf /var/lib/apt/lists/*

COPY Backend /app
RUN pip install --no-cache-dir .

CMD ["celery", "-A", "app.workers.celery_app.celery_app", "worker", "--loglevel=INFO"]
