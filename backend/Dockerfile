# --- builder stage ---
FROM python:3.12-slim as builder

WORKDIR /app

# System deps for psycopg2 and pandas/openpyxl builds
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# --- runtime stage ---
FROM python:3.12-slim

WORKDIR /app

# Copy only Python site-packages from builder
COPY --from=builder /root/.local /root/.local

# Set PATH to use user-installed packages
ENV PATH=/root/.local/bin:$PATH

# Copy app code
COPY . .

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/ready').read()" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
