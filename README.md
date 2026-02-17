# PDF Processing API

Professional PDF processing API for print production, built with FastAPI.

## Features

- **Imposition**: N-up, step-and-repeat, booklet layouts
- **Color Management**: RGB to CMYK conversion with ICC profiles
- **Preflight**: Image resolution, font embedding, bleed checks
- **Manipulation**: Merge, split, rotate, metadata

## Quick Start

### Docker (Recommended)

```bash
cp .env.example .env
# Edit .env with your API key

docker-compose up -d



## Ops: overload protection & admin monitoring

This service can be CPU/RAM heavy (imposition). To avoid "all workers busy" failures, it includes an in-process capacity limiter and an optional memory watchdog.

### Environment variables

- `MAX_CONCURRENT_JOBS` (default `1`): how many heavy jobs can run at once **per process**.
- `MAX_JOB_QUEUE` (default `10`): how many extra requests can wait before rejecting with `503`.
- `JOB_ACQUIRE_TIMEOUT_SECONDS` (default `0`): if `0`, reject immediately when busy; if `>0`, wait up to this many seconds for a slot.
- `JOB_TIMEOUT_SECONDS` (default `300`): soft timeout for heavy processing sections.
- `MAX_RSS_MB` (default `0`): if set to `>0`, the process exits when RSS exceeds this many MB so the platform restarts it.
- `ADMIN_KEY` (no default): enables `/admin` endpoints when set.

### Admin endpoints

- `GET /admin?key=ADMIN_KEY` – simple HTML dashboard
- `GET /admin/status?key=ADMIN_KEY` – JSON status

> Note: Docker resource limits (CPU/RAM) are enforced by the runtime (Coolify/Docker), not by the image. Use Coolify's Resource Limits where possible.
