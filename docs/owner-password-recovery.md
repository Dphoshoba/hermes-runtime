# Controlled owner-password recovery

This is a database-administrator maintenance operation, not an HTTP endpoint or
login bypass. Deployment and execution against Production each require a separate
human checkpoint. Do not run this procedure during implementation or validation.
Do not change `EVOSIA_JWT_SECRET`, Railway variables, or local agent credentials.

## Command contract

In an approved maintenance environment with the Enterprise dependencies installed:

```console
python -m enterprise.admin reset-owner-password --email <existing-owner-email>
```

The command uses the existing database configuration and session factory:
`EVOSIA_DATABASE_URL`, then `HERMES_DATABASE_URL`, then the development SQLite
default. Independently verify the intended environment before an authorized run;
the command deliberately never prints its database URL. It does not create tables,
run migrations, seed accounts, start the server, or invoke the local agent.

There is no password argument, password environment variable, or non-interactive
confirmation flag. Two masked `getpass` prompts are mandatory; inability to disable
terminal echo aborts. Only the selected account ID and administrator status are
displayed. After both entries validate, type exactly `RESET` to authorize the write.
Every rejected/cancelled operation exits nonzero; success exits zero after commit.
Errors are sanitized rather than printing validation inputs, SQL parameters, or
database exceptions.

## Selection and password policy

Input email is validated using the existing `EmailStr` type, trimmed and lowercased.
Stored emails are compared using SQL `lower(trim(email))`, using the configured
database's lowercasing semantics. Exactly one existing account must match, including
case/space variants: zero or multiple matches abort, even if only one is an admin.

The selected account must have `User.is_admin` and `User.is_active` set. There is
no distinct global owner field; this is the existing global administrator
authority, also used by `require_admin`. A workspace `UserWorkspace.role == "admin"`
alone is insufficient. No account is created, activated, promoted, or renamed.

The existing registration schema `UserCreate` enforces 8-128 characters. Recovery
additionally rejects passwords longer than 72 UTF-8 bytes because the existing
bcrypt implementation would silently truncate them. Choose a password within both
limits. The existing production helper `enterprise.services.hash_password` is
reused unchanged, with `CryptContext(schemes=["bcrypt"], deprecated="auto")`.
Passlib's configured default bcrypt work factor is 12; dependencies pin Passlib
1.7.4 and bcrypt >=4.0.1,<5.0.0. Verification remains
`enterprise.services.verify_password`. No second password hashing implementation
is introduced.

## Atomicity, audit, and sessions

One `SessionLocal` transaction encompasses lookup, confirmation, password update,
and audit insertion. Lookup requests a row lock where supported. A conditional
update also checks the original password hash, active/admin flags, normalized
email, and unique match count; an observed concurrent change aborts. Database
errors, including journal insertion/commit failure, roll back the transaction.
An uncertain connection loss during commit must be investigated separately before
retrying; no client can guarantee whether a server committed after such a loss.

Only `User.hashed_password` changes. There is no password-specific timestamp or
version field. The generic `updated_at` is explicitly preserved, as are all other
user fields, devices, projects, memberships, and authorization records.

The existing `JournalEvent` table receives `security.owner_password_reset`, stage
`security`, actor `admin_cli`, with payload containing only the user ID and method
`admin_cli`. The existing canonical journal payload digest helper is reused.
Neither email, password, password hash, database URL, nor JWT is included.
Audit failure prevents password commit; rejected attempts do not write events.
The actor denotes the command, not an independently authenticated human identity.
Database access is the administrative trust boundary.

User JWTs contain a subject and expiration and are verified with the existing
signing secret (HS256, default lifetime 24 hours). Authorization also checks the
user still exists and is active. There is no token registry, password timestamp,
or token-version comparison. **Password recovery does not revoke existing user
JWTs.** Device credentials and project authorization tokens are also unchanged.
Do not rotate `EVOSIA_JWT_SECRET` as part of this procedure. Suspected stolen tokens
require a separate approved incident-response plan.

## Deployment boundary

The existing Docker image installs the Enterprise package and starts
`uvicorn enterprise.app:app`; it does not invoke maintenance commands. No start
command, deployment configuration, HTTP router, schema, or migration is changed.
Tests use synthetic credentials and disposable local databases only. A local
commit is not authorization to push, deploy, access Production, or run recovery.

## Local implementation validation

Validation used synthetic configuration and disposable local databases on Windows
with Python 3.14. No Production access, Railway operation, migration execution, or
real recovery was performed.

| Check | Result |
| --- | --- |
| Recovery contract tests | 31 passed |
| Enterprise authentication/backend | 77 passed |
| Device trust | 51 passed, 1 failed, 1 skipped |
| Local agent CLI | 33 passed, 1 failed |
| Project authorization | 22 passed, 2 failed, 1 skipped |
| Governed agent jobs | 58 passed, 1 skipped |
| Authority boundary | 10 passed |
| Security hardening | 10 passed |
| Database health | 11 passed |
| Disposable fixture/preparation | 8 passed, 7 failed |
| Safety | 10 passed |
| Ruff lint and formatting | Passed for the two added Python files |
| Mypy | Passed for the command (`--follow-imports=skip --ignore-missing-imports`) |
| Python wheel and source package | Built successfully with `python -m build --no-isolation` |
| Schema/migration/auth/deployment diff | No changes; migrations not executed |
| Independent security review | No vulnerabilities found |

The 11 failures were reproduced using the unchanged starting commit
`5f8a6e06604de66cd593db78aa7113269eb739c1`: unavailable Windows symlink
privileges, POSIX permission expectations, project path matching, missing nested
Git metadata for the disposable fixture, and default Windows text encoding.
They are not recovery regressions and were left unchanged. Suites were run in
separate processes because existing suites modify shared database environment
settings during collection. The VS Code test/syntax tools could not discover this
sibling repository; terminal pytest, Ruff, Mypy, and package build supplied the
validation evidence instead.
