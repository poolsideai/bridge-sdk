FROM python:3.11-slim

# Install git and curl (for uv installation)
RUN apt-get update && \
    apt-get install -y --no-install-recommends git curl && \
    rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --no-cache-dir uv

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml uv.lock ./
COPY lib/ ./lib/
COPY proto/ ./proto/
COPY main.py ./

# Install dependencies
RUN uv sync --frozen

# Copy entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Keep container running so entrypoint can be executed via kubectl exec
CMD ["sleep", "infinity"]

