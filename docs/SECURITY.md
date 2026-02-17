# Security Documentation

## Overview

ProcureIQ implements multiple layers of security to protect sensitive procurement data and ensure safe AI operations.

## Authentication & Authorization

### API Key Authentication
- **Requirement**: All API endpoints require `X-API-Key` header
- **Generation**: Auto-generated on first startup if not provided
- **Storage**: Must be stored in `.env` file
- **Best Practice**: Use a strong, random key (32+ characters)

```bash
# Generate a secure API key
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### OAuth2 for Gmail
- **Protocol**: OAuth 2.0 with refresh tokens
- **Scope**: Gmail read-only access
- **Storage**: Refresh token in `.env` (never commit)
- **Setup**: Run `gmail_auth_setup.py` to obtain tokens

## Environment Variables

### Required Variables
All sensitive data MUST be stored in `.env`:

```env
# API Keys
API_KEY=your_secret_api_key
GEMINI_API_KEY=your_gemini_key
OPENAI_API_KEY=your_openai_key

# Gmail OAuth2
GMAIL_CLIENT_ID=your_client_id
GMAIL_CLIENT_SECRET=your_client_secret
GMAIL_REFRESH_TOKEN=your_refresh_token

# Notifications
TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_token
```

### Validation
- Environment validation runs on startup
- Missing required variables trigger warnings
- Critical missing variables prevent startup

## Data Protection

### In Transit
- **Development**: HTTP (localhost only)
- **Production**: HTTPS mandatory (TLS 1.2+)
- **API Calls**: All external API calls use HTTPS

### At Rest  
- **Database**: SQLite file with proper file permissions
- **Credentials**: Never stored in database (only in `.env`)
- **Audit Trail**: All actions logged for compliance

### Access Control
- **API Authentication**: Required for all endpoints except health checks
- **Token-based Approvals**: Time-limited tokens for email approvals
- **No Public Data**: All endpoints require authentication

## AI Safety & Security

### Prompt Injection Prevention
- Input sanitization on all user-provided text
- Structured prompt templates (no direct user input)
- Response validation against expected schemas

### Output Validation
- All AI responses validated before use
- Confidence scores required (0-100%)
- Human review for medium confidence (75-94%)

### Audit Trail
- Every AI decision logged with:
  - Model used (gemini/openai/ollama)
  - Confidence score
  - Reasoning
  - Timestamp
  - Result

## Production Security Checklist

### Before Deployment
- [ ] Change default `API_KEY` to strong random value
- [ ] Enable HTTPS (configure reverse proxy or use platform TLS)
- [ ] Set up firewall rules (allow only necessary ports)
- [ ] Configure rate limiting
- [ ] Enable CORS restrictions (update `allow_origins` in `main.py`)

### Secrets Management
- [ ] All `.env` variables set in production environment
- [ ] `.env` file in `.gitignore` (verify with `git status`)
- [ ] Rotate OAuth2 tokens every 90 days
- [ ] Rotate API keys every 180 days

### Monitoring
- [ ] Configure Sentry for error tracking (`SENTRY_DSN` in `.env`)
- [ ] Set up Prometheus alerts for anomalies
- [ ] Monitor failed authentication attempts
- [ ] Review audit logs weekly

### Database Security
- [ ] Regular backups (daily minimum)
- [ ] Backup encryption enabled
- [ ] Test restore procedure monthly
- [ ] Limit database file permissions (owner read/write only)

## Incident Response

### Security Event Handling
1. **Detection**: Monitor logs and alerts
2. **Isolation**: Rotate compromised credentials immediately
3. **Investigation**: Review audit trail
4. **Recovery**: Restore from backup if needed
5. **Prevention**: Update security measures

### Emergency Contacts
- Document security team contact information
- Establish escalation procedures
- Maintain incident response runbook

## Compliance

### Data Handling
- **PII**: Minimal collection (only emails and phone numbers)
- **Retention**: Invoices and events stored indefinitely (configurable)
- **Deletion**: Manual purge process available
- **Export**: JSON export capability for all data

### Audit Requirements
- All actions logged to database (`events` table)
- Logs include: timestamp, user, action, result
- Logs retained for compliance period (configurable)

## Common Security Issues

### Issue: API Key Exposed
**Symptoms**: Unauthorized API access
**Solution**:
1. Generate new API key
2. Update `.env` file
3. Restart application
4. Review access logs for suspicious activity

### Issue: OAuth Token Expired
**Symptoms**: Gmail email processing fails
**Solution**:
1. Re-run `gmail_auth_setup.py`
2. Copy new refresh token to `.env`
3. Restart application

### Issue: Database File Permissions
**Symptoms**: Unauthorized access to database
**Solution**:
```bash
# Linux/Mac
chmod 600 procure_iq.db

# Windows (PowerShell)
icacls procure_iq.db /inheritance:r /grant:r "$env:USERNAME:F"
```

## References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [Google OAuth 2.0](https://developers.google.com/identity/protocols/oauth2)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
