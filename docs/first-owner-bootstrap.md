# Controlled first-owner bootstrap

This is an explicit database-administrator maintenance command for initial owner
creation only. It is not a public registration endpoint, password reset, role
promotion, login bypass, or incident-response session revocation mechanism.
Implementation and local certification do not authorize execution in Production.

```console
python -m enterprise.admin bootstrap-first-owner --email <new-owner-email>
```

## Preconditions and input

- Use only in a separately approved maintenance environment with Enterprise
  dependencies installed. The command uses the unchanged `SessionLocal` and
  existing database configuration precedence: `EVOSIA_DATABASE_URL`, then
  `HERMES_DATABASE_URL`, then the development SQLite default. It never displays
  a database URL or reads Railway configuration.
- Email is required, validated with the existing `EmailStr` type, trimmed and
  lowercased. The normalized email must not match any account, including stored
  case/space variants compared with SQL `lower(trim(email))`.
- There must be **zero global administrators**, including inactive ones.
  Workspace administrators do not count as global administrators.
- `m8-participant@example.com` is explicitly forbidden, even when absent.
  No existing account is modified, promoted, activated, reset, or deleted.
- Enter the password twice through masked `getpass` prompts. An echo fallback
  aborts rather than accepting an unmasked password. There is no password
  argument, password environment variable, confirmation flag, or non-interactive
  mode.
- The existing `UserCreate` registration policy requires 8-128 characters.
  Recovery's additional 72-byte UTF-8 limit also applies to bootstrap to avoid
  bcrypt truncation. The existing `enterprise.services.hash_password` helper is
  reused unchanged (Passlib bcrypt, default work factor 12); no second hashing
  implementation is introduced.
- Only exact confirmation `BOOTSTRAP` authorizes creation.

## Creation, preservation, and audit

Success creates exactly one user with the normalized email, display name
`EVOSIA Owner`, `is_active=True`, and `is_admin=True`. Model defaults generate its
UUID and timestamps. No JWT is issued. Existing user JWTs, device credentials,
pairing requests, project authorizations, workspaces, repositories, fixture data,
and journal events remain unchanged.

The user and one `security.first_owner_bootstrapped` journal event commit in the
same transaction. The event has stage `security`, actor `admin_cli`, and payload
containing only the new user ID and method `admin_cli`. It uses the existing
canonical journal payload digest helper. Its UTC timestamp uses millisecond
precision to fit the existing 30-character column.

Any user insert, audit insert, or commit failure rolls back both records. The
command returns nonzero on rejected input, cancellation, unsupported database,
lock failure, or database error, with sanitized output rather than validation
inputs, SQL parameters, database URLs, passwords, hashes, or exception details.
As with any database client, a connection loss during commit may leave the commit
outcome uncertain; obtain a separately approved read-only investigation before
retrying. A committed first owner causes subsequent invocations to fail closed.

## Two phases and concurrency without a schema change

**Phase 1: no database session, transaction, lock, or write.** Parse and normalize
the email and reject the reserved fixture identity, collect both masked password
entries, validate the existing password policy and bcrypt byte limit, require
exact `BOOTSTRAP` confirmation, then hash with the existing helper. Every input,
validation, confirmation, or hashing failure exits before opening a database
session. No informational precheck is used: input and hashing finish even if the
later database checks refuse creation.

**Phase 2: a fresh, short locked transaction.** Only after hashing completes does
the command open a session and transaction, acquire a native database lock, then
authoritatively recheck fixture exclusion, zero global administrators (including
inactive ones), and unused normalized email. It creates the user and journal
event atomically and holds the lock only until commit or rollback:

- **PostgreSQL:** `SET TRANSACTION ISOLATION LEVEL READ COMMITTED`, then a
  transaction-local five-second lock timeout, then
  `LOCK TABLE users IN EXCLUSIVE MODE`. This serializes bootstrap attempts and
  blocks all other user-table writers and locking reads, not just cooperating
  commands. Ordinary reads remain possible. The explicitly selected isolation
  ensures checks see a fresh committed snapshot after waiting, even when the
  engine default is REPEATABLE READ.
- **SQLite:** `BEGIN IMMEDIATE` reserves the database writer before the checks,
  including when the administrator set is empty. A competing connection either
  waits for the lock and then sees the administrator or fails closed on its
  configured busy timeout.
- Other dialects are refused; there is no unlocked fallback.

Exactly one concurrent valid invocation can commit. A waiting invocation observes
the new administrator and refuses without writing; a timeout also refuses without
writing. Both invocations have already completed their interactive input and
hashing before attempting the lock. Competing administrators or email collisions
created during Phase 1 are rejected by Phase 2's checks under the lock, not an
earlier snapshot. If the first transaction aborts, the next can become the first
owner. Locks are transaction-scoped and leave no persistent recovery state.

**Operational impact:** human input and password hashing never hold a database
transaction or lock. Normal registration and other user writes can block only
during the short creation transaction. Another bootstrap waiting more than five
seconds on PostgreSQL returns failure and must not be treated as successful. No
schema constraint, migration, table creation, server startup, or HTTP route is
added. The existing reset command implementation is unchanged.

## Local verification

Tests use only synthetic data, disposable SQLite databases, and an explicitly
enabled PostgreSQL cluster bound to `127.0.0.1:55483`. The opt-in test switch
`EVOSIA_TEST_LOCAL_POSTGRES=1` enables a fixed loopback test target; tests never
accept an arbitrary Production database URL.

Coverage includes no-admin creation, existing/inactive-admin rejection, normalized
email collisions, fixture-address exclusion, double-entry and policy failures,
exact confirmation, sanitized errors, user/audit/commit rollback, sequential
refusal, full-record preservation, unchanged reset implementation, and absence of
public bootstrap/recovery routes. Concurrency tests use independent connections,
threads, and spawned processes against SQLite and PostgreSQL. PostgreSQL tests
also exercise READ COMMITTED and REPEATABLE READ defaults, native database errors,
noncooperating writers, ordinary reads, and lock timeouts. Tests assert that neither
password prompt, confirmation, nor hashing opens a session; input and hashing
failures never open one. Competing active/inactive administrators and normalized
email collisions committed after confirmation and before the locked transaction
are rejected on every supported database/isolation variant.

The existing recovery preservation fixtures populate devices, projects,
workspaces, memberships, pairing and authorization requests, repository data,
and journal events. Bootstrap preservation tests compare all existing rows
logically unchanged, allowing only the new owner and sanitized event.

No Production access, real bootstrap/reset execution, Railway variable changes,
JWT secret rotation, local-agent logout, push, or deployment is part of this
implementation.

### Certification results

Starting/deployed baseline: `5a7849d4ec3f9de97813e40b86cfa017e807fb16`.
Validation ran on Windows with Python 3.14 and a disposable PostgreSQL 18.6
instance, never the Production database.

| Check | Result |
| --- | --- |
| Bootstrap and existing recovery tests together | 105 passed, 2 skipped |
| Enterprise authentication/backend | 77 passed |
| Device trust | 51 passed, 1 failed, 1 skipped |
| Local agent CLI | 33 passed, 1 failed |
| Project authorization | 22 passed, 2 failed, 1 skipped |
| Governed agent jobs | 63 passed, 1 skipped |
| Authority boundary / security hardening / database health / safety | 41 passed |
| Disposable fixture/preparation | 8 passed, 7 failed |
| P3a authority / smoke | 37 passed |
| P3b installer | 20 passed, 8 skipped |
| P3c pairing / P3d project authorization / P3e desktop-tray | 78 passed (P3d class-isolated) |
| Total across isolated suite runs | 535 passed, 11 failed, 13 skipped |
| Ruff lint and formatting | Passed for command and new tests |
| Targeted Mypy | Passed (`--follow-imports=skip --ignore-missing-imports`) |
| Source package and wheel build | Passed; wheel contains the exact command source |
| Python 3.10 syntax compatibility | Passed for command and new tests |
| Existing reset function | Exact source fingerprint preserved; 31 existing tests pass unchanged |
| Schema, migration, auth-helper, route, deployment diffs | No changes |
| Independent read-only security review | No vulnerabilities found in corrected candidate |

The two focused skips are PostgreSQL-only assertions on the SQLite parameter;
all local PostgreSQL concurrency and rollback variants executed successfully.
The 11 broader failures are the same previously baseline-reproduced Windows
symlink/permission/path and disposable-fixture Git-metadata/encoding failures.
They were left unchanged. Regression suites ran in separate processes to avoid
the existing cross-suite database environment mutations. All 11 failures were
reproduced on the unchanged `5a7849d` parent during this certification.

The initial P3d whole-file run produced 17 passes and three setup/teardown errors
from leaked fixture sessions exhausting the connection pool, followed by a
duplicate synthetic email. The parent whole-file run also reproduced the same
connection-pool exhaustion (18 passes, one error). All 19 P3d tests passed when
each test class ran in a fresh process; those results are included in the
aggregate above rather than counting retries twice. No unrelated fixtures were
changed.

The VS Code test/syntax tools could not discover this sibling repository;
terminal pytest, Ruff, Mypy, AST parsing, and package build provided the evidence.
The temporary PostgreSQL server was stopped and its disposable cluster and
downloaded binaries removed after validation. No migrations were executed.
