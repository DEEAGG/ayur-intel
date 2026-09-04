# AYUR-INTEL Deployment Guide

## Quick Start (Development)

```bash
cd ayur-intel
cp .env.example .env
# Edit .env as needed (defaults work for development)
python3 start_server.py
# → http://127.0.0.1:8000
```

## Production Deployment

### 1. Prerequisites

- Python 3.9+
- pip
- SQLite (default) or PostgreSQL
- Reverse proxy (nginx recommended)

### 2. Environment Setup

```bash
# Copy and configure environment
cp .env.example .env

# Required changes for production:
# - Set AYURINTEL_DEMO_MODE=false
# - Set AYURINTEL_DEBUG=false
# - Change AYURINTEL_SESSION_SECRET to a strong random value
# - Set AYURINTEL_CORS_ALLOW_ORIGINS to your domain
# - Configure database path or DATABASE_URL
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Database

```bash
# SQLite (automatic on first run)
# Data stored in: data/ayur_intel.db

# For PostgreSQL:
# Set DATABASE_URL in .env
# AYURINTEL_DB_PATH is ignored when DATABASE_URL is set
```

### 5. Run

```bash
# Production (without auto-reload)
AYURINTEL_DEBUG=false python3 -m api.main

# Or with uvicorn directly
uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 6. Reverse Proxy (nginx)

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # Redirect HTTP to HTTPS
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Request-ID $request_id;
    }

    # Static files with caching
    location /static/ {
        proxy_pass http://127.0.0.1:8000/static/;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }
}
```

## Health Checks

```bash
# Health check
curl http://localhost:8000/api/health
# → {"status": "ok", "version": "0.1.0", "database": "ok", ...}

# Readiness check
curl http://localhost:8000/api/ready
# → {"ready": true, "checks": {"database": true, "data_directory": true}}
```

## Rollback Procedure

1. Stop the new deployment
2. Restore previous version of code
3. Database is backward-compatible (no destructive migrations)
4. Restart with previous version
5. Verify health check returns "ok"

## Backup

### SQLite
```bash
# Backup
cp data/ayur_intel.db data/ayur_intel.db.backup.$(date +%Y%m%d)

# Restore
cp data/ayur_intel.db.backup.YYYYMMDD data/ayur_intel.db
```

### PostgreSQL
```bash
# Backup
pg_dump -U user ayur_intel > backup.sql

# Restore
psql -U user ayur_intel < backup.sql
```

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| AYURINTEL_DB_PATH | data/ayur_intel.db | SQLite database path |
| AYURINTEL_HOST | 127.0.0.1 | Server host |
| AYURINTEL_PORT | 8000 | Server port |
| AYURINTEL_DEBUG | true | Debug mode (false in production) |
| AYURINTEL_SESSION_SECRET | change-me-in-production | Auth secret |
| AYURINTEL_SESSION_TTL_SECONDS | 86400 | Session TTL |
| AYURINTEL_DEMO_MODE | true | Demo mode (false in production) |
| AYURINTEL_CORS_ALLOW_ORIGINS | http://127.0.0.1:8000 | CORS origins |
