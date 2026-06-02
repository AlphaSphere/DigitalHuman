FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
  && apt-get install -y --no-install-recommends curl ffmpeg git \
  && rm -rf /var/lib/apt/lists/*

COPY Services/cosyvoice-service /app
RUN pip install --no-cache-dir .

EXPOSE 8002

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
