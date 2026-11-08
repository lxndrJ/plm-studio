FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# shared backend code (models + preview service) + image tooling
COPY backend/pyproject.toml ./backend/pyproject.toml
RUN pip install --no-cache-dir ./backend pillow

COPY backend/app ./backend/app
COPY previews/worker.py ./worker.py

CMD ["python", "worker.py"]
