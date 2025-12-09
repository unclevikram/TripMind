# Dockerfile for TripMind A2A Agent
# Designed for deployment on Google Cloud Run, Railway, Render, etc.

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for Playwright (headless browser)
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgbm1 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libwayland-client0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xdg-utils \
    libu2f-udev \
    libvulkan1 \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set Playwright browser path BEFORE installing
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Install Playwright browsers and dependencies
RUN python -m playwright install --with-deps chromium

# Copy application code
COPY . .

# Make run.sh executable
RUN chmod +x run.sh

# Create data directory
RUN mkdir -p /app/data

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# The port will be set by the cloud provider (usually via PORT env var)
# AgentBeats controller uses port 8080 by default
EXPOSE 8080

# Health check - check if the agent card endpoint is accessible
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import httpx; httpx.get('http://localhost:${PORT:-9002}/.well-known/agent-card.json', timeout=5)" || exit 1

# Run the A2A agent directly
# Use PORT env var if set (Railway/Render set this automatically)
CMD ["sh", "-c", "python -m src.a2a_agent --host 0.0.0.0 --port ${PORT:-9002}"]
