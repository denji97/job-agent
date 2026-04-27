FROM python:3.13-slim

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends nodejs npm \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir uv
COPY pyproject.toml /app
COPY uv.lock /app
RUN uv sync --frozen
COPY . /app

CMD ["uv", "run", "main.py"]