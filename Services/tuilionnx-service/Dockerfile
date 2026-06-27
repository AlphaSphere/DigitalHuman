FROM python:3.12-slim
WORKDIR /app
COPY Services/tuilionnx-service/app /app/app
RUN pip install --no-cache-dir fastapi uvicorn pydantic
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8004"]
