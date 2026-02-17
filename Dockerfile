FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ghostscript \
    dumb-init \
    wget \
    curl \
    xz-utils \
    && rm -rf /var/lib/apt/lists/*

# Install pdfcpu (robust)
RUN wget -q https://github.com/pdfcpu/pdfcpu/releases/download/v0.6.0/pdfcpu_0.6.0_Linux_x86_64.tar.xz -O /tmp/pdfcpu.tar.xz \
    && mkdir -p /tmp/pdfcpu \
    && tar -xJf /tmp/pdfcpu.tar.xz -C /tmp/pdfcpu \
    && install -m 0755 "$(find /tmp/pdfcpu -type f -name pdfcpu | head -n 1)" /usr/local/bin/pdfcpu \
    && rm -rf /tmp/pdfcpu /tmp/pdfcpu.tar.xz \
    && pdfcpu version


WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY icc_profiles/ /app/icc_profiles/
COPY app/ /app/app/
RUN mkdir -p /app/temp && chmod 777 /app/temp

ENV PYTHONUNBUFFERED=1
ENV UVICORN_WORKERS=1
ENV UVICORN_HOST=0.0.0.0
ENV UVICORN_PORT=8000
ENV UVICORN_KEEPALIVE=10
ENV MAX_CONCURRENT_JOBS=1
ENV MAX_JOB_QUEUE=10
ENV JOB_ACQUIRE_TIMEOUT_SECONDS=0
ENV JOB_TIMEOUT_SECONDS=300
ENV MAX_RSS_MB=0
ENV ADMIN_KEY=

ENV ICC_PROFILES_DIR=/app/icc_profiles
ENV TEMP_DIR=/app/temp

EXPOSE 8000

ENTRYPOINT ["dumb-init", "--"]
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["sh", "-c", "uvicorn app.main:app --host ${UVICORN_HOST} --port ${UVICORN_PORT} --workers ${UVICORN_WORKERS} --timeout-keep-alive ${UVICORN_KEEPALIVE}"]
