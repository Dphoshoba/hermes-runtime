# M1 — Hosted Beta Threat Model

## Trust Boundaries

```
[Browser] ←HTTPS→ [CDN/Load Balancer] ←→ [EVOSIA FastAPI]
                                                      |
                                              [Tenant Auth Layer]
                                                      |
                                              [PostgreSQL]
                                                      |
                                              [Ephemeral Scan Workspace]
                                                      |
                                              [GitHub App (read-only)]
```

## Assets

- User credentials (hashed)
- Session tokens
- Tenant data (projects, scans, findings, context, missions, journal)
- GitHub App private key
- Database credentials
- Session secret

## Threats

| # | Threat | Mitigation |
|---|--------|------------|
| 1 | Unauthenticated API access | Require auth on all /api except /health and /auth/login/register |
| 2 | Cross-tenant data leak | Tenant-scoped queries enforced in backend service layer |
| 3 | Session hijacking | Secure cookies, HttpOnly, SameSite, expiration |
| 4 | Direct object ID guessing | Tenant-scoped authorization checks on every object lookup |
| 5 | CSRF | SameSite cookies, anti-CSRF tokens on state-changing ops |
| 6 | XSS | Output encoding, Content-Security-Policy headers |
| 7 | Secret leakage | Secrets only in Secret Manager; never in logs/journal/frontend |
| 8 | GitHub token exposure | Tokens in Secret Manager only; never logged |
| 9 | Privilege escalation | Admin endpoints require admin role; no user self-promotion |
| 10 | Rate limiting | Apply per-IP and per-user rate limits on auth and scan endpoints |
| 11 | Malformed auth | Validate all auth inputs; reject expired/invalid tokens cleanly |
| 12 | GitHub callback CSRF | Validate state parameter in OAuth callback |

## Data Classification

- **Sensitive:** credentials, session tokens, GitHub tokens, source code
- **Internal:** findings, missions, journal events, context
- **Public:** health check, login page

## Responsible Disclosure

This is a BETA threat model, not a certified security audit. Findings should
be reported to the operator.
