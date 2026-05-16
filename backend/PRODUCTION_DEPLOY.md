# Backend Production Deployment

## Purpose
The Android Play Store app is a client. The FastAPI backend must be hosted over HTTPS.

## Minimum viable hosts
- Render
- Railway
- Fly.io
- Google Cloud Run
- Azure App Service
- AWS Lightsail/EC2

## Required environment variables
```text
OPENAI_API_KEY=your_server_side_key
SIMLAY_CORS_ORIGINS=https://your-frontend-domain.com
```

## Start command
```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## Persistent storage warning
SQLite + local filesystem is acceptable for MVP/private beta. For public multi-user production, upgrade to:

- PostgreSQL for database
- S3/R2/GCS for upload/export files
- User accounts + tenant isolation

Do not store multiple customers' media in one local filesystem without authentication and tenant separation.
