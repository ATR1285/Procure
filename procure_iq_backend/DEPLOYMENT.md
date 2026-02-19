# Procure-IQ v2.0 Deployment Guide

This guide covers the steps to deploy Procure-IQ v2.0 in production environments using Docker and traditional methods.

## 🐳 Docker Deployment (Recommended)

### 1. Building the Image
```bash
docker build -t procure-iq-backend:v2.0 .
```

### 2. Running with Docker Compose
Ensure your `.env` file is ready, then run:
```bash
docker-compose up -d
```
This will start:
- **FastAPI Backend**: On port 8000
- **Prometheus**: On port 9090 (if configured)
- **Grafana**: On port 3000 (if configured)

## ☁️ Cloud Deployment

### AWS / Heroku / Railway
1. **Set Environment Variables**: All variables in `.env.example` must be set in your cloud provider's secret management.
2. **Persistence**: Use a persistent volume for the `procure_iq.db` file or switch `DATABASE_URL` to a PostgreSQL instance.
3. **Internal URLs**: Update `BASE_URL` to your production domain (e.g., `https://api.procure-iq.com`).

## 🔑 Production Checklists

### Security
- [ ] Change the default `API_KEY` to a strong random string.
- [ ] Use HTTPS for all production traffic.
- [ ] Ensure `DATABASE_URL` is backed up regularly.
- [ ] Rotate OAuth2 secrets every 90 days.

### Monitoring
- [ ] Configure `SENTRY_DSN` in `.env` for production error tracking.
- [ ] Set up Prometheus alerts for high latency or error rates.
- [ ] Monitor the `worker` heartbeat via the analytics dashboard.

### AI Configuration
- [ ] Set `AI_MODEL_PRIMARY` to `gemini-1.5-pro` for best performance.
- [ ] Ensure `OPENAI_API_KEY` is set for fallback resilience.
- [ ] Review cost logs in the analytics dashboard weekly.

## 🛠 Troubleshooting

### Server Not Starting
- Check `server_startup.log` for port binding errors (WinError 10061/10048).
- Ensure `.env` is correctly formatted and all required fields are present.

### AI Calls Failing
- Verify API keys in the health check endpoint: `/api/ai-health`.
- Check network access to Google/OpenAI endpoints.

### Emails Not Processing
- Re-run the OAuth2 authentication flow to refresh the token.
- Check the `worker` logs for Gmail API quota errors.
