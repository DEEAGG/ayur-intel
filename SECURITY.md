# AYUR-INTEL Security Review

## Security Architecture

### Authentication
- **Demo Mode**: Single demo user, no real auth
- **Production**: Session-based authentication (Phase 19+)
- **Secrets**: All loaded from environment variables, never hardcoded

### Authorization
- Product Case ownership verified on every request
- IDOR protection: unauthorized access returns 404
- Cross-user data isolation via database-level filters

### Input Validation
- Pydantic schemas enforce min/max length, required fields
- HTML escaping on user inputs
- ID validation (alphanumeric + hyphen only)
- Jurisdiction code validation (2-letter uppercase)

### Security Headers
All responses include:
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `X-XSS-Protection: 1; mode=block`
- `Content-Security-Policy`: Restrictive policy

### Audit Logging
- All security-critical actions logged to `audit_logs` table
- Actions: CREATE, UPDATE, DELETE, ACCESS, LOGIN, DENIED, ASSIGN, DECISION
- Metadata automatically stripped of secrets (password, token, api_key, etc.)

### Rate Limiting
- In-memory rate limiter available for expensive endpoints
- Configurable per-endpoint limits

### Error Handling
- Safe error responses hide internal details
- Technical details logged server-side only
- No stack traces or database errors exposed to clients

## Data Classification

| Classification | Examples | Protection |
|---------------|----------|------------|
| PUBLIC | App name, version | No restriction |
| INTERNAL | System metrics, health | Server-side only |
| USER_PRIVATE | Product data, evidence, risks | Owner-only access |
| SYSTEM_SECRET | API keys, passwords | Never exposed |

## API Security

### Protected Endpoints
All `/api/cases/*`, `/api/reviews/*`, `/api/analytics/*` endpoints require authentication.

### Authorization Pattern
```python
# Every case-scoped query filters by owner
case = db.query(ProductCase).filter(
    ProductCase.public_id == case_id,
    ProductCase.owner_id == user.id,
).first()
```

### IDOR Prevention
- Returns 404 (not 403) to avoid leaking resource existence
- All resource access verified against case ownership

## Logging Security

### What IS Logged
- User actions (CREATE, UPDATE, DELETE, ACCESS)
- Resource types and IDs
- Timestamps and status
- Correlation IDs

### What is NOT Logged
- Passwords
- API keys
- Authentication tokens
- Full product formulations
- Private user content

## AI Safety

### No Fabrication
- All findings grounded in stored evidence
- Sources are real, not invented
- No fake patent numbers or regulation references
- Clear uncertainty markers (UNKNOWN, REVIEW_REQUIRED)

### No Legal Guarantees
- System explicitly states: "Decision-support only"
- No "approved", "safe", "patentable" conclusions
- Human review required for high-risk findings

## Recommendations for Production

1. **Change session secret** to a strong random value
2. **Disable demo mode** (`AYURINTEL_DEMO_MODE=false`)
3. **Set debug to false** (`AYURINTEL_DEBUG=false`)
4. **Configure CORS** for your domain only
5. **Enable HTTPS** via reverse proxy
6. **Set up database backups** on a schedule
7. **Monitor logs** for security events
8. **Review rate limiting** for your traffic patterns
