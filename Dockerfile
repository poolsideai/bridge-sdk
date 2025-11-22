<<<<<<< HEAD
FROM python:3.12-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
=======
FROM python:3.11-slim

# Install git and curl (for uv installation)
RUN apt-get update && \
    apt-get install -y --no-install-recommends git curl && \
    rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --no-cache-dir uv
>>>>>>> agoddijn/sdk-analysis-image

# Set working directory
WORKDIR /app

<<<<<<< HEAD
# Copy dependency files
COPY pyproject.toml uv.lock ./
=======
# Copy project files
COPY pyproject.toml uv.lock ./
COPY lib/ ./lib/
COPY proto/ ./proto/
COPY main.py ./
>>>>>>> agoddijn/sdk-analysis-image

# Install dependencies
RUN uv sync --frozen

<<<<<<< HEAD
# Copy application code
COPY lib/ ./lib/
COPY proto/ ./proto/
COPY examples/ ./examples/
COPY main.py ./

# Set entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
=======
# Copy entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Keep container running so entrypoint can be executed via kubectl exec
CMD ["sleep", "infinity"]
>>>>>>> agoddijn/sdk-analysis-image

