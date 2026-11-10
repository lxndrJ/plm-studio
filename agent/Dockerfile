FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# package source must be present BEFORE pip install, otherwise the wheel is empty
COPY agent/pyproject.toml ./agent/pyproject.toml
COPY agent/plm_agent ./agent/plm_agent
COPY agent/prompts ./agent/prompts
RUN pip install --no-cache-dir ./agent

EXPOSE 8001

CMD ["uvicorn", "plm_agent.server:app", "--host", "0.0.0.0", "--port", "8001"]
