FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# shared backend package (source must be present BEFORE pip install, otherwise
# the wheel contains no 'app' package) + image tooling
COPY backend/pyproject.toml ./backend/pyproject.toml
COPY backend/app ./backend/app
RUN pip install --no-cache-dir ./backend pillow

COPY previews/worker.py ./worker.py

CMD ["python", "worker.py"]
