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

