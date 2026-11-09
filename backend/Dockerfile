FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Report engine (M6): pinned Typst binary (static musl build, multi-arch).
# Bump TYPST_VERSION deliberately together with a Typst release.
ARG TYPST_VERSION=0.13.1
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates curl xz-utils; \
    arch="$(dpkg --print-architecture)"; \
    case "$arch" in \
      amd64) tarch="x86_64-unknown-linux-musl" ;; \
      arm64) tarch="aarch64-unknown-linux-musl" ;; \
      *) echo "unsupported architecture: $arch" >&2; exit 1 ;; \
    esac; \
    curl -fsSL "https://github.com/typst/typst/releases/download/v${TYPST_VERSION}/typst-${tarch}.tar.xz" -o /tmp/typst.tar.xz; \
    tar -xJf /tmp/typst.tar.xz -C /usr/local/bin --strip-components=1 "typst-${tarch}/typst"; \
    rm -f /tmp/typst.tar.xz; \
    rm -rf /var/lib/apt/lists/*; \
    typst --version

RUN pip install --no-cache-dir --upgrade pip

COPY pyproject.toml ./
RUN pip install --no-cache-dir .

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
