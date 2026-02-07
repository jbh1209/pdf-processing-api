FROM node:20-slim

# Install Ghostscript + wget
RUN apt-get update && \
    apt-get install -y --no-install-recommends ghostscript wget ca-certificates && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ICC profiles
RUN mkdir -p /app/profiles
RUN wget -O /app/profiles/GRACoL2013_CRPC6.icc \
    "https://www.colormanagement.org/downloads/GRACoL2013_CRPC6.icc" && \
    wget -O /app/profiles/ISOcoated_v2_eci.icc \
    "https://www.colormanagement.org/downloads/ISOcoated_v2_eci.icc"

# Copy package files
COPY package*.json ./

# Install dependencies (no lockfile required)
RUN npm install --omit=dev --no-audit --no-fund

# Copy app
COPY server.js ./

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:3000/health || exit 1

CMD ["node", "server.js"]
