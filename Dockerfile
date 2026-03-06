FROM python:3.12-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files first (layer cache)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy source
COPY briefd/ ./briefd/

# Run with uvicorn
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8080

CMD ["uvicorn", "briefd.web.app:app", "--host", "0.0.0.0", "--port", "8080"]
