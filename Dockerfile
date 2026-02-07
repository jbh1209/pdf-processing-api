FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ghostscript \
    wget \
    curl \
    xz-utils \
    && rm -rf /var/lib/apt/lists/*

# Install pdfcpu
RUN wget -q https://github.com/pdfcpu/pdfcpu/releases/download/v0.6.0/pdfcpu_0.6.0_Linux_x86_64.tar.xz \
    && tar -xf pdfcpu_0.6.0_Linux_x86_64.tar.xz \
    && mv pdfcpu /usr/local/bin/ \
    && rm pdfcpu_0.6.0_Linux_x86_64.tar.xz

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY icc_profiles/ /app/icc_profiles/
COPY app/ /app/app/
RUN mkdir -p /app/temp && chmod 777 /app/temp

ENV PYTHONUNBUFFERED=1
ENV ICC_PROFILES_DIR=/app/icc_profiles
ENV TEMP_DIR=/app/temp

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
