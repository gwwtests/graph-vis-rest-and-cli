FROM python:3.12-slim

# Install Chromium and dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        chromium \
        chromium-driver \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt selenium

# Copy application code
COPY server.py .
COPY static/ static/
COPY e2e/test_e2e.py e2e/

ENV GRAPH_VIS_PORT=7849
ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "pytest", "e2e/test_e2e.py", "-v", "--tb=short"]
