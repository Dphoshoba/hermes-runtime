# Hermes Enterprise — Architecture Specification v1.0

**Status:** Architecture Proposal
**Date:** 2026-08-09
**Scope:** Platform architecture for Hermes Enterprise
**Classification:** Internal — Engineering

---

## Table of Contents

1. [Vision](#1-vision)
2. [Product Philosophy](#2-product-philosophy)
3. [Product Editions](#3-product-editions)
4. [System Architecture](#4-system-architecture)
5. [Service Boundaries](#5-service-boundaries)
6. [Database Model](#6-database-model)
7. [Event Architecture](#7-event-architecture)
8. [API](#8-api)
9. [Web Dashboard](#9-web-dashboard)
10. [Multi-tenancy](#10-multi-tenancy)
11. [Security](#11-security)
12. [GitHub Integration](#12-github-integration)
13. [AI Provider Layer](#13-ai-provider-layer)
14. [Policy Engine](#14-policy-engine)
15. [Deployment](#15-deployment)
16. [Scalability](#16-scalability)
17. [Disaster Recovery](#17-disaster-recovery)
18. [Licensing](#18-licensing)
19. [Five-Year Vision](#19-five-year-vision)
20. [Architectural Principles](#20-architectural-principles)

---

## 1. Vision

### What is Hermes Enterprise?

Hermes Enterprise is a self-hosted, multi-tenant engineering intelligence platform that enables organizations to autonomously monitor, analyze, and improve their software repositories through evidence-driven governance and mission execution.

It is the commercial evolution of Hermes Core — an autonomous engineering runtime that executes missions through a pipeline of evidence collection, independent review, and health monitoring.

### Who is it for?

- **Engineering Leaders** who need visibility across hundreds of repositories
- **Platform Engineering Teams** who need to enforce standards at scale
- **Compliance Officers** who need audit trails for regulatory requirements
- **DevOps Teams** who need to automate repository maintenance and remediation
- **Security Teams** who need continuous governance across codebases

### What problems does it solve?

| Problem | Solution |
|---------|----------|
| Fragmented visibility across repositories | Unified repository intelligence dashboard |
| Manual compliance checking at scale | Automated policy engine with evidence trails |
| Inconsistent engineering standards | Organization-wide governance policies |
| Lack of auditability for code changes | Immutable evidence store with full lineage |
| Manual remediation of known issues | Autonomous mission execution with human approval |
| No centralized view of engineering risk | Risk scoring with trend analysis |

---

## 2. Product Philosophy

### Relationship to Hermes Core

Hermes Enterprise preserves every architectural principle from Hermes Core:

| Core Principle | Enterprise Preservation |
|----------------|------------------------|
| Determinism over speed | Same inputs → same outputs at any scale |
| Durability over convenience | All state persisted with atomic writes |
| Immutability for evidence | Evidence store is append-only, cryptographically verifiable |
| Composability over monolith | Microservice boundaries match Core module boundaries |
| No hidden state | All state queryable through API and dashboard |

### Enterprise Extensions

Enterprise capabilities extend Core principles, never override them:

```
Hermes Core (Foundation)
├── Evidence Collection     → Evidence Store (distributed, searchable)
├── Independent Review      → Review Service (multi-reviewer, weighted)
├── Health Monitoring       → Health Dashboard (real-time, alerting)
├── Mission Execution       → Mission Scheduler (cron, event, API)
├── Repository Intelligence → Repository Service (multi-repo, trending)
├── Engineering Governance  → Policy Engine (RBAC, approval chains)
└── GitHub Integration      → GitHub Service (multi-org, webhooks)
```

### Non-Negotiables

1. **Human approval is never bypassed.** Missions require explicit approval regardless of risk score.
2. **Evidence is never mutated.** Published evidence is append-only with cryptographic integrity.
3. **Audit trails are complete.** Every action is logged with actor, timestamp, and reasoning.
4. **Safety is not configurable.** Worktree isolation and diff scope validation cannot be disabled.
5. **Determinism is preserved.** Same repository + same mission + same policy = same outcome.

---

## 3. Product Editions

### Community (Open Source)

```
Hermes Core Runtime
├── Repository Readiness Assessment
├── Repository Intelligence (single repo)
├── Engineering Intelligence (single repo)
├── Engineering Governance (single repo)
├── Mission Planning & Execution
├── Evidence Collection & Review
├── Health Monitoring
├── GitHub Provider (read-only)
├── All CLI commands
├── Local filesystem repositories
└── Community support (GitHub Issues)
```

**Limits:** Single repository, no multi-tenancy, no web UI, no API server.

### Professional

```
Everything in Community, plus:
├── Web Dashboard (single-user)
├── REST API
├── Multi-repository management (up to 50)
├── Scheduled missions (cron)
├── Notification service (email, Slack webhook)
├── GitHub integration (branch creation, draft PR)
├── AI-assisted mission generation
├── Trend analysis and reporting
└── Email support
```

**Limits:** Single tenant, single-user dashboard, 50 repositories.

### Enterprise

```
Everything in Professional, plus:
├── Multi-tenant architecture
├── Organization & project hierarchy
├── Role-based access control (RBAC)
├── SSO integration (SAML, OIDC)
├── Unlimited repositories
├── Policy engine (custom rules)
├── Approval workflows (multi-stage)
├── Compliance reporting (SOC 2, ISO 27001)
├── High availability deployment
├── Kubernetes orchestration
├── Custom AI model integration
├── Audit log export
├── SLA-backed support
└── Professional services
```

### Feature Comparison

| Capability | Community | Professional | Enterprise |
|------------|-----------|--------------|------------|
| Repository count | 1 | 50 | Unlimited |
| Users | 1 | 1 | Unlimited |
| Tenants | 1 | 1 | Unlimited |
| Web UI | No | Single-user | Multi-user |
| API | No | REST | REST + Webhooks |
| RBAC | No | Basic | Full |
| SSO | No | No | Yes |
| Policy Engine | No | Basic | Full |
| Approval Workflow | CLI only | Single-stage | Multi-stage |
| Compliance Reports | No | No | Yes |
| HA Deployment | No | No | Yes |
| SLA Support | No | Email | 24/7 |

---

## 4. System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          CLIENT LAYER                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │
│  │ Web UI   │  │ REST API │  │ Webhooks │  │ CLI (hermes-*)   │   │
│  │ (React)  │  │ (OpenAPI)│  │ (Out)    │  │ (Community)      │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┬─────────┘   │
│       │              │              │                  │             │
└───────┼──────────────┼──────────────┼──────────────────┼─────────────┘
        │              │              │                  │
┌───────▼──────────────▼──────────────▼──────────────────▼─────────────┐
│                         API GATEWAY                                  │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Rate Limiting  │  Authentication  │  Authorization  │ Logs │   │
│  └──────────────────────────────────────────────────────────────┘   │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────────┐
│                       SERVICE LAYER                                  │
│                                                                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────┐ │
│  │  Mission     │  │ Repository  │  │  GitHub     │  │  Policy   │ │
│  │  Service     │  │ Service     │  │  Service    │  │  Engine   │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └─────┬─────┘ │
│         │                │                │                │        │
│  ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐  ┌─────▼─────┐ │
│  │  Evidence   │  │  Review     │  │  Scheduler  │  │  Notify   │ │
│  │  Store      │  │  Service    │  │  Service    │  │  Service  │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └─────┬─────┘ │
│         │                │                │                │        │
│  ┌──────▼──────┐  ┌──────▼──────┐  ┌──────▼──────┐  ┌─────▼─────┐ │
│  │  AI Provider│  │  Search     │  │  Metrics    │  │  Auth     │ │
│  │  Layer      │  │  Service    │  │  Service    │  │  Service  │ │
│  └─────────────┘  └─────────────┘  └─────────────┘  └───────────┘ │
│                                                                      │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────────┐
│                     HERMES CORE ENGINE                               │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Readiness │ Scanner Registry │ Mission Runner │ Safety      │   │
│  │  Assessment│ (Python, JS, TS) │ (Sequential/  │ (Worktree,  │   │
│  │            │                  │  Concurrent)   │  Diff Scope)│   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────────┐
│                       DATA LAYER                                     │
│                                                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐           │
│  │PostgreSQL│  │  Redis   │  │   S3 /   │  │  Elastic │           │
│  │(Primary) │  │ (Cache)  │  │  MinIO   │  │  Search  │           │
│  │          │  │          │  │ (Object) │  │  (Search)│           │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘           │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

### Data Flow Diagram

```
Repository Event (Push, PR, Schedule)
        │
        ▼
┌─────────────────┐
│  GitHub Service  │◄── Webhook
│  (Receive Event) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Policy Engine   │◄── Organization Policies
│  (Evaluate)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Mission Service  │
│ (Create Mission) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│  Approval Gate   │────►│  Notification    │
│  (Human Required)│     │  Service         │
└────────┬────────┘     └─────────────────┘
         │ (Approved)
         ▼
┌─────────────────┐
│  Scheduler       │
│  (Dispatch)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Hermes Core     │
│  (Execute)       │
│  ├── Readiness   │
│  ├── Scan        │
│  ├── Analyze     │
│  ├── Evidence    │
│  └── Review      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐     ┌─────────────────┐
│  Evidence Store  │────►│  Search Service  │
│  (Persist)       │     │  (Index)         │
└────────┬────────┘     └─────────────────┘
         │
         ▼
┌─────────────────┐
│  Mission Report  │
│  (Generate)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Webhooks Out    │
│  (Notify)        │
└─────────────────┘
```

---

## 5. Service Boundaries

### 5.1 Mission Service

**Responsibility:** Mission lifecycle management — creation, approval, execution, reporting.

**Inputs:**
- Mission creation requests (API, scheduler, recommendation engine)
- Approval/rejection decisions
- Execution status updates

**Outputs:**
- Mission state transitions
- Execution evidence
- Mission reports

**Failure Modes:**
- Service unavailable → Missions queued, retried on recovery
- Database unavailable → In-memory queue, persisted on recovery
- Core engine crash → Mission resumed from last checkpoint

**SLO:** 99.9% availability, < 100ms state transition latency.

### 5.2 Repository Service

**Responsibility:** Repository registration, metadata management, intelligence aggregation.

**Inputs:**
- Repository registration requests
- GitHub API metadata
- Scanner results

**Outputs:**
- Repository metadata
- Intelligence reports
- Health scores

**Failure Modes:**
- GitHub API unavailable → Cached metadata served, refresh on recovery
- Scanner failure → Partial intelligence, marked as incomplete
- Database unavailable → Read-only mode, writes queued

**SLO:** 99.9% availability, < 500ms metadata retrieval.

### 5.3 GitHub Service

**Responsibility:** GitHub API integration, webhook processing, repository operations.

**Inputs:**
- GitHub webhooks (push, PR, issues, actions)
- API requests for metadata, file content
- Materialization requests

**Outputs:**
- Webhook events (normalized)
- Repository metadata
- Branch/PR status updates

**Failure Modes:**
- Webhook delivery failed → Retry with exponential backoff
- Rate limit exceeded → Queue requests, process on recovery
- Authentication expired → Alert operator, degrade to public API

**SLO:** 99.95% webhook processing, < 5s webhook delivery.

### 5.4 Policy Engine

**Responsibility:** Policy evaluation, compliance checking, risk assessment.

**Inputs:**
- Repository events
- Mission requests
- Configuration changes

**Outputs:**
- Policy decisions (allow, deny, require approval)
- Risk scores
- Compliance status

**Failure Modes:**
- Policy evaluation failure → Deny by default (safe)
- Configuration error → Reject changes, alert operator
- Performance degradation → Cache recent decisions

**SLO:** 99.99% availability, < 10ms evaluation latency.

### 5.5 Evidence Store

**Responsibility:** Immutable evidence recording, integrity verification, retrieval.

**Inputs:**
- Evidence records from missions
- Review outcomes
- Audit log entries

**Outputs:**
- Evidence records (immutable)
- Integrity verification results
- Evidence queries

**Failure Modes:**
- Storage unavailable → Evidence buffered locally, synced on recovery
- Integrity check failure → Alert, quarantine affected evidence
- Retention policy violation → Automated archival

**SLO:** 100% durability, 99.999% availability for writes.

### 5.6 Review Service

**Responsibility:** Independent review of execution records, quality scoring.

**Inputs:**
- Evidence records
- Review configuration
- Historical review patterns

**Outputs:**
- Review outcomes (PASSED, FAILED, INCOMPLETE)
- Quality scores
- Review explanations

**Failure Modes:**
- Review timeout → Mark as INCOMPLETE, retry
- Reviewer unavailability → Queue for retry
- Conflicting reviews → Escalate to human

**SLO:** 99.9% availability, < 30s review completion.

### 5.7 Scheduler Service

**Responsibility:** Mission scheduling, cron management, event-driven triggers.

**Inputs:**
- Schedule definitions (cron expressions)
- Event triggers (webhook, webhook)
- API-triggered missions

**Outputs:**
- Mission creation events
- Schedule status
- Execution history

**Failure Modes:**
- Scheduler unavailable → Missions delayed, executed on recovery
- Cron misfire → Alert, execute missed missions
- Event loss → Dead letter queue, manual replay

**SLO:** 99.9% availability, < 1s scheduling latency.

### 5.8 Notification Service

**Responsibility:** Alerting, notifications, webhook delivery.

**Inputs:**
- Event subscriptions
- Alert rules
- Notification preferences

**Outputs:**
- Email notifications
- Slack/Teams messages
- Webhook deliveries

**Failure Modes:**
- Email delivery failed → Retry, queue for batch
- Slack unavailable → Fallback to email
- Webhook timeout → Retry with backoff

**SLO:** 99.9% delivery, < 30s notification latency.

### 5.9 AI Provider Layer

**Responsibility:** AI model abstraction, prompt management, response routing.

**Inputs:**
- Analysis requests
- Mission generation requests
- Review enhancement requests

**Outputs:**
- Analysis results
- Mission recommendations
- Review explanations

**Failure Modes:**
- Provider unavailable → Fallback to next provider
- Rate limit exceeded → Queue, process on recovery
- Response invalid → Retry, fallback to deterministic

**SLO:** 99.5% availability, < 30s response time.

### 5.10 Search Service

**Responsibility:** Full-text search, filtering, aggregation across all entities.

**Inputs:**
- Search queries
- Index updates
- Filter definitions

**Outputs:**
- Search results
- Aggregations
- Suggestions

**Failure Modes:**
- Search unavailable → Fallback to database queries
- Index stale → Background reindexing
- Query timeout → Partial results with warning

**SLO:** 99.9% availability, < 200ms query latency.

### 5.11 Metrics Service

**Responsibility:** Metrics collection, aggregation, export.

**Inputs:**
- Metric events from all services
- Prometheus scrape requests
- Custom metric queries

**Outputs:**
- Prometheus metrics
- Dashboard data
- Alerting rules

**Failure Modes:**
- Metrics unavailable → Services continue, metrics lost
- Aggregation lag → eventual consistency
- Storage full → Rotate old metrics

**SLO:** 99.9% availability, < 1s metric freshness.

### 5.12 Auth Service

**Responsibility:** Authentication, authorization, session management.

**Inputs:**
- Login requests (SSO, API key)
- Token validation
- Permission checks

**Outputs:**
- Authentication tokens
- Permission decisions
- Session state

**Failure Modes:**
- SSO unavailable → Fallback to local auth
- Token expired → Refresh or re-authenticate
- Database unavailable → Cache-only mode

**SLO:** 99.99% availability, < 50ms auth check.

---

## 6. Database Model

### Entity Relationship Diagram

```
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│ Organization│──────►│   Project   │──────►│ Repository  │
│             │  1:N  │             │  1:N  │             │
└─────────────┘       └─────────────┘       └─────────────┘
       │                     │                     │
       │                     │                     │
       ▼                     ▼                     ▼
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│    Team     │       │   Mission   │       │ Intelligence│
│             │       │             │       │   Report    │
└─────────────┘       └─────────────┘       └─────────────┘
       │                     │                     │
       │                     │                     │
       ▼                     ▼                     ▼
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│    User     │       │   Evidence  │       │   Review    │
│             │       │   Record    │       │   Record    │
└─────────────┘       └─────────────┘       └─────────────┘
       │                     │                     │
       │                     │                     │
       ▼                     ▼                     ▼
┌─────────────┐       ┌─────────────┐       ┌─────────────┐
│Permission   │       │   Policy    │       │  Webhook    │
│   Grant     │       │   Rule      │       │   Event     │
└─────────────┘       └─────────────┘       └─────────────┘
```

### Core Entities

#### Organization

```sql
CREATE TABLE organizations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(255) NOT NULL UNIQUE,
    slug            VARCHAR(255) NOT NULL UNIQUE,
    settings        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);

CREATE INDEX idx_organizations_slug ON organizations(slug);
```

#### Project

```sql
CREATE TABLE projects (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    name            VARCHAR(255) NOT NULL,
    slug            VARCHAR(255) NOT NULL,
    settings        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ,
    UNIQUE(organization_id, slug)
);

CREATE INDEX idx_projects_org ON projects(organization_id);
```

#### Repository

```sql
CREATE TABLE repositories (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id      UUID NOT NULL REFERENCES projects(id),
    github_url      VARCHAR(512) NOT NULL,
    github_owner    VARCHAR(255) NOT NULL,
    github_name     VARCHAR(255) NOT NULL,
    default_branch  VARCHAR(255) DEFAULT 'main',
    visibility      VARCHAR(50),
    language        VARCHAR(100),
    status          VARCHAR(50) DEFAULT 'active',
    settings        JSONB DEFAULT '{}',
    last_scanned_at TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ,
    UNIQUE(project_id, github_owner, github_name)
);

CREATE INDEX idx_repositories_project ON repositories(project_id);
CREATE INDEX idx_repositories_github ON repositories(github_owner, github_name);
CREATE INDEX idx_repositories_status ON repositories(status);
```

#### Mission

```sql
CREATE TABLE missions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_id   UUID REFERENCES repositories(id),
    project_id      UUID NOT NULL REFERENCES projects(id),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    name            VARCHAR(255) NOT NULL,
    mission_type    VARCHAR(100) NOT NULL,
    status          VARCHAR(50) NOT NULL DEFAULT 'draft',
    priority        INTEGER DEFAULT 0,
    configuration   JSONB DEFAULT '{}',
    metadata        JSONB DEFAULT '{}',
    created_by      UUID REFERENCES users(id),
    approved_by     UUID REFERENCES users(id),
    approved_at     TIMESTAMPTZ,
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_missions_org ON missions(organization_id);
CREATE INDEX idx_missions_project ON missions(project_id);
CREATE INDEX idx_missions_repository ON missions(repository_id);
CREATE INDEX idx_missions_status ON missions(status);
CREATE INDEX idx_missions_created ON missions(created_at DESC);
```

#### Evidence Record

```sql
CREATE TABLE evidence_records (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mission_id      UUID NOT NULL REFERENCES missions(id),
    repository_id   UUID NOT NULL REFERENCES repositories(id),
    evidence_type   VARCHAR(100) NOT NULL,
    content_hash    VARCHAR(64) NOT NULL,
    storage_path    VARCHAR(1024) NOT NULL,
    size_bytes      BIGINT,
    metadata        JSONB DEFAULT '{}',
    immutable       BOOLEAN DEFAULT true,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_evidence_mission ON evidence_records(mission_id);
CREATE INDEX idx_evidence_repository ON evidence_records(repository_id);
CREATE INDEX idx_evidence_type ON evidence_records(evidence_type);
CREATE INDEX idx_evidence_created ON evidence_records(created_at DESC);
```

#### Review Record

```sql
CREATE TABLE review_records (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    evidence_id     UUID NOT NULL REFERENCES evidence_records(id),
    mission_id      UUID NOT NULL REFERENCES missions(id),
    reviewer_type   VARCHAR(100) NOT NULL,
    outcome         VARCHAR(50) NOT NULL,
    confidence      DECIMAL(3,2),
    explanation     TEXT,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_reviews_mission ON review_records(mission_id);
CREATE INDEX idx_reviews_evidence ON review_records(evidence_id);
CREATE INDEX idx_reviews_outcome ON review_records(outcome);
```

#### Policy Rule

```sql
CREATE TABLE policy_rules (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    name            VARCHAR(255) NOT NULL,
    description     TEXT,
    rule_type       VARCHAR(100) NOT NULL,
    condition       JSONB NOT NULL,
    action          JSONB NOT NULL,
    enabled         BOOLEAN DEFAULT true,
    priority        INTEGER DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_policies_org ON policy_rules(organization_id);
CREATE INDEX idx_policies_type ON policy_rules(rule_type);
CREATE INDEX idx_policies_enabled ON policy_rules(enabled);
```

#### User

```sql
CREATE TABLE users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID REFERENCES organizations(id),
    email           VARCHAR(255) NOT NULL UNIQUE,
    name            VARCHAR(255),
    avatar_url      VARCHAR(512),
    auth_provider   VARCHAR(50),
    auth_provider_id VARCHAR(255),
    role            VARCHAR(50) DEFAULT 'member',
    settings        JSONB DEFAULT '{}',
    last_login_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    deleted_at      TIMESTAMPTZ
);

CREATE INDEX idx_users_org ON users(organization_id);
CREATE INDEX idx_users_email ON users(email);
```

#### Team

```sql
CREATE TABLE teams (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    name            VARCHAR(255) NOT NULL,
    slug            VARCHAR(255) NOT NULL,
    description     TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(organization_id, slug)
);

CREATE TABLE team_members (
    team_id         UUID NOT NULL REFERENCES teams(id),
    user_id         UUID NOT NULL REFERENCES users(id),
    role            VARCHAR(50) DEFAULT 'member',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (team_id, user_id)
);

CREATE INDEX idx_teams_org ON teams(organization_id);
```

#### Webhook Event

```sql
CREATE TABLE webhook_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    repository_id   UUID REFERENCES repositories(id),
    event_type      VARCHAR(100) NOT NULL,
    payload         JSONB NOT NULL,
    status          VARCHAR(50) DEFAULT 'pending',
    processed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_webhooks_org ON webhook_events(organization_id);
CREATE INDEX idx_webhooks_status ON webhook_events(status);
CREATE INDEX idx_webhooks_created ON webhook_events(created_at DESC);
```

### Audit Strategy

All tables include:
- `created_at` — when the record was created
- `updated_at` — when the record was last modified
- `deleted_at` — soft delete timestamp (NULL = active)

Audit log table:

```sql
CREATE TABLE audit_log (
    id              BIGSERIAL PRIMARY KEY,
    organization_id UUID REFERENCES organizations(id),
    user_id         UUID REFERENCES users(id),
    action          VARCHAR(100) NOT NULL,
    entity_type     VARCHAR(100) NOT NULL,
    entity_id       UUID NOT NULL,
    changes         JSONB,
    ip_address      INET,
    user_agent      TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_audit_org ON audit_log(organization_id);
CREATE INDEX idx_audit_entity ON audit_log(entity_type, entity_id);
CREATE INDEX idx_audit_user ON audit_log(user_id);
CREATE INDEX idx_audit_created ON audit_log(created_at DESC);
```

### Versioning

All entities support optimistic locking via `updated_at`:

```python
# Update with version check
UPDATE missions
SET status = 'running', updated_at = NOW()
WHERE id = $1 AND updated_at = $2
RETURNING *;
```

Conflict detection: If `rows_affected == 0`, the entity was modified concurrently.

---

## 7. Event Architecture

### Event Types

| Event | Trigger | Consumers |
|-------|---------|-----------|
| `mission.created` | Mission created via API or scheduler | Policy Engine, Notification Service |
| `mission.approved` | Human approves mission | Scheduler, Notification Service |
| `mission.rejected` | Human rejects mission | Notification Service |
| `mission.started` | Mission begins execution | Metrics, Notification Service |
| `mission.completed` | Mission finishes successfully | Evidence Store, Metrics, Notification Service |
| `mission.failed` | Mission execution fails | Metrics, Notification Service, Alerting |
| `evidence.recorded` | Evidence persisted | Search Service, Review Service |
| `review.completed` | Review outcome determined | Mission Service, Metrics |
| `repository.scanned` | Repository scan complete | Intelligence Store, Metrics |
| `governance.decision` | Policy engine decision | Mission Service, Audit Log |
| `webhook.received` | GitHub webhook arrived | GitHub Service, Event Router |
| `policy.violated` | Policy rule triggered | Notification Service, Audit Log |

### Event Schema

```json
{
  "event_id": "uuid-v4",
  "event_type": "mission.completed",
  "timestamp": "2026-08-09T12:00:00Z",
  "organization_id": "uuid",
  "actor": {
    "type": "system",
    "id": "scheduler-01"
  },
  "subject": {
    "type": "mission",
    "id": "mission-uuid"
  },
  "data": {
    "mission_type": "remediation",
    "repository": "owner/repo",
    "duration_ms": 45000,
    "tasks_completed": 5,
    "tasks_failed": 0
  },
  "metadata": {
    "trace_id": "trace-uuid",
    "correlation_id": "correlation-uuid"
  }
}
```

### Event Delivery

```
Event Producer
      │
      ▼
┌─────────────────┐
│  Event Bus      │  (Redis Streams / Kafka)
│  (Durable)      │
└────────┬────────┘
         │
    ┌────┼────┬────┐
    │    │    │    │
    ▼    ▼    ▼    ▼
┌─────┐┌─────┐┌─────┐┌─────┐
│Consumer││Consumer││Consumer││Consumer│
│  A   ││  B   ││  C   ││  D   │
└─────┘└─────┘└─────┘└─────┘
```

**Guarantees:**
- At-least-once delivery
- Ordering within partition (by organization_id)
- Durable storage (7-day retention)
- Dead letter queue for failed deliveries

---

## 8. API

### REST API

Base URL: `https://api.hermes.example.com/v1`

### Authentication

```
Authorization: Bearer <jwt-token>
```

Or API key:

```
X-API-Key: <api-key>
```

### Core Endpoints

#### Organizations

```
GET    /v1/organizations                    # List organizations
POST   /v1/organizations                    # Create organization
GET    /v1/organizations/:id                # Get organization
PATCH  /v1/organizations/:id                # Update organization
DELETE /v1/organizations/:id                # Delete organization
```

#### Projects

```
GET    /v1/organizations/:org/projects      # List projects
POST   /v1/organizations/:org/projects      # Create project
GET    /v1/projects/:id                     # Get project
PATCH  /v1/projects/:id                     # Update project
DELETE /v1/projects/:id                     # Delete project
```

#### Repositories

```
GET    /v1/projects/:project/repositories   # List repositories
POST   /v1/projects/:project/repositories   # Add repository
GET    /v1/repositories/:id                 # Get repository
DELETE /v1/repositories/:id                 # Remove repository
POST   /v1/repositories/:id/scan            # Trigger scan
GET    /v1/repositories/:id/intelligence    # Get intelligence report
GET    /v1/repositories/:id/health          # Get health score
```

#### Missions

```
GET    /v1/projects/:project/missions       # List missions
POST   /v1/projects/:project/missions       # Create mission
GET    /v1/missions/:id                     # Get mission
PATCH  /v1/missions/:id                     # Update mission
POST   /v1/missions/:id/approve             # Approve mission
POST   /v1/missions/:id/reject              # Reject mission
POST   /v1/missions/:id/cancel              # Cancel mission
POST   /v1/missions/:id/abort               # Abort mission
GET    /v1/missions/:id/evidence            # List evidence
GET    /v1/missions/:id/reviews             # List reviews
GET    /v1/missions/:id/report              # Get report
```

#### Evidence

```
GET    /v1/evidence/:id                     # Get evidence record
GET    /v1/evidence/:id/content             # Get evidence content
GET    /v1/evidence/:id/integrity           # Verify integrity
```

#### Policies

```
GET    /v1/organizations/:org/policies      # List policies
POST   /v1/organizations/:org/policies      # Create policy
GET    /v1/policies/:id                     # Get policy
PATCH  /v1/policies/:id                     # Update policy
DELETE /v1/policies/:id                     # Delete policy
POST   /v1/policies/:id/test               # Test policy against scenario
```

#### Users & Teams

```
GET    /v1/organizations/:org/users         # List users
POST   /v1/organizations/:org/users         # Invite user
GET    /v1/users/:id                        # Get user
PATCH  /v1/users/:id                        # Update user
DELETE /v1/users/:id                        # Remove user
GET    /v1/organizations/:org/teams         # List teams
POST   /v1/organizations/:org/teams         # Create team
GET    /v1/teams/:id                        # Get team
PATCH  /v1/teams/:id                        # Update team
DELETE /v1/teams/:id                        # Delete team
POST   /v1/teams/:id/members                # Add member
DELETE /v1/teams/:id/members/:user          # Remove member
```

#### Search

```
GET    /v1/search?q=...&type=...            # Full-text search
GET    /v1/search/repositories              # Search repositories
GET    /v1/search/missions                  # Search missions
GET    /v1/search/evidence                  # Search evidence
```

### Pagination

```
GET /v1/repositories?page=2&per_page=50

Response:
{
  "data": [...],
  "pagination": {
    "page": 2,
    "per_page": 50,
    "total": 237,
    "total_pages": 5
  }
}
```

### Filtering

```
GET /v1/missions?status=completed&mission_type=remediation&repository=owner/repo
GET /v1/evidence?mission_id=...&evidence_type=scan_result&after=2026-01-01
```

### Webhooks (Outbound)

Configure webhook endpoints to receive events:

```
POST /v1/organizations/:org/webhooks
{
  "url": "https://your-app.com/webhooks/hermes",
  "events": ["mission.completed", "governance.decision"],
  "secret": "webhook-secret"
}
```

Payload signed with HMAC-SHA256:

```
X-Hermes-Signature: sha256=...
```

### API Versioning

- URL path versioning: `/v1/`, `/v2/`
- Breaking changes require new major version
- Deprecated endpoints return `Sunset` header
- Minimum 12-month deprecation period

---

## 9. Web Dashboard

### 9.1 Engineering Command Center

The default view. Provides organization-wide visibility.

```
┌─────────────────────────────────────────────────────────────────────┐
│  HERMES ENTERPRISE                                    [Search] [⚙] │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ │
│  │ Repositories│ │  Missions   │ │  Findings   │ │  Risk Score │ │
│  │    247      │ │   12 active │ │   89 open   │ │    72/100   │ │
│  │  ↑ 3 this wk│ │  5 pending  │ │  ↓ 12 fixed │ │  ↑ +5 pts   │ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │  Risk Trend (30 days)                                         │ │
│  │  ┌─────────────────────────────────────────────────────────┐  │ │
│  │  │  80─┐                                                   │  │ │
│  │  │     │     ┌──┐                                          │  │ │
│  │  │  70─┤  ┌──┘  └──┐     ┌───┐                            │  │ │
│  │  │     │  │        └─────┘   └──┐                          │  │ │
│  │  │  60─┤                        └──┐                       │  │ │
│  │  │     │                           └──                     │  │ │
│  │  │  50─┘                                                     │  │ │
│  │  └─────────────────────────────────────────────────────────┘  │ │
│  │    1    5    10   15   20   25   30                           │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  Recent Activity                                                    │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │  12:04  mission completed  remediation  owner/repo-a  ✓     │ │
│  │  11:58  governance denied  policy-violation  owner/repo-b   │ │
│  │  11:45  scan complete  owner/repo-c  3 findings             │ │
│  │  11:30  mission approved  security-patch  owner/repo-d      │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 9.2 Repository View

Detailed view of a single repository.

```
┌─────────────────────────────────────────────────────────────────────┐
│  ← Back to Command Center                                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  owner/repo-a                                      [Scan] [Mission]│
│  ─────────────                                                           │
│  Python  │  2,847 files  │  Last scanned: 2h ago  │  Health: 85   │
│                                                                     │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ │
│  │  Modules    │ │  Coverage   │ │  Debt       │ │  Findings   │ │
│  │    142      │ │    78%      │ │   23 items  │ │   12 open   │ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ │
│                                                                     │
│  Intelligence Report                                                │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │  Complexity Distribution                                      │ │
│  │  Low: 89 (63%)  Medium: 38 (27%)  High: 12 (8%)  Critical: 3│ │
│  │                                                               │ │
│  │  Top Findings                                                 │ │
│  │  1. [HIGH] auth.py — Cyclomatic complexity 47                │ │
│  │  2. [MED]  models.py — Missing type hints (12 functions)    │ │
│  │  3. [MED]  utils.py — God module (1,200 lines)              │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  Mission History                                                    │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │  #127  remediation  completed  2026-08-08  ✓                 │ │
│  │  #124  security-scan  completed  2026-08-07  ✓               │ │
│  │  #121  dependency-update  failed  2026-08-06  ✗              │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 9.3 Mission View

Detail view of a single mission.

```
┌─────────────────────────────────────────────────────────────────────┐
│  ← Back to Missions                                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Mission #127 — Remediation                     Status: COMPLETED  │
│  ───────────────────────────────────────────────────────              │
│  Repository: owner/repo-a     Type: remediation                     │
│  Created: 2026-08-08 10:00    Completed: 2026-08-08 10:45          │
│  Approved by: admin@company.com                                     │
│                                                                     │
│  Tasks (5/5 completed)                                              │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │  ✓  Update requirements.txt (pin cryptography)               │ │
│  │  ✓  Add type hints to auth.py                                │ │
│  │  ✓  Fix SQL injection in users.py                            │ │
│  │  ✓  Remove hardcoded secrets from config.py                  │ │
│  │  ✓  Add missing __init__.py                                  │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  Evidence (3 records)                                               │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │  📋 scan_result     sha256:a1b2c3...  2.4 KB   [View]       │ │
│  │  📋 execution_log   sha256:d4e5f6...  12.1 KB  [View]       │ │
│  │  📋 test_results    sha256:g7h8i9...  8.7 KB   [View]       │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  Reviews (2 records)                                                │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │  ✓ PASSED  automated-review  confidence: 0.95                │ │
│  │  ✓ PASSED  security-review   confidence: 0.88                │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 9.4 Governance Queue

Pending approval decisions.

```
┌─────────────────────────────────────────────────────────────────────┐
│  Governance Queue                                      [Filter ▼]  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Pending Approvals (7)                                              │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │  Mission #128  security-patch  owner/repo-b                  │ │
│  │  Risk: HIGH  │  Policy: requires-security-approval           │ │
│  │  Requested by: dev@company.com  │  Waiting: 2h               │ │
│  │                                           [Approve] [Reject] │ │
│  ├───────────────────────────────────────────────────────────────┤ │
│  │  Mission #129  dependency-update  owner/repo-c               │ │
│  │  Risk: MEDIUM  │  Policy: standard-approval                  │ │
│  │  Requested by: ci@company.com  │  Waiting: 45m               │ │
│  │                                           [Approve] [Reject] │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  Recently Decided                                                   │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │  ✓ #127  remediation  owner/repo-a  APPROVED  admin@company  │ │
│  │  ✗ #126  feature-branch  owner/repo-d  REJECTED  reason: ... │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 9.5 Evidence Explorer

Browse and search evidence records.

```
┌─────────────────────────────────────────────────────────────────────┐
│  Evidence Explorer                              [Search...] [Filter]│
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Filters:                                                           │
│  Type: [All Types ▼]  Mission: [All ▼]  Date: [Range ▼]           │
│                                                                     │
│  Results (2,847 records)                                            │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │  Type          Mission    Repository      Date       Size     │ │
│  │  ───────────────────────────────────────────────────────────  │ │
│  │  scan_result   #127       owner/repo-a    Aug 08    2.4 KB  │ │
│  │  execution_log #127       owner/repo-a    Aug 08    12.1 KB │ │
│  │  test_results  #127       owner/repo-a    Aug 08    8.7 KB  │ │
│  │  scan_result   #124       owner/repo-a    Aug 07    2.3 KB  │ │
│  │  review        #124       owner/repo-a    Aug 07    1.1 KB  │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  Selected: scan_result #127                                         │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │  SHA-256: a1b2c3d4e5f6...                                    │ │
│  │  Integrity: ✓ Verified                                       │ │
│  │  Immutable: Yes                                              │ │
│  │                                                               │ │
│  │  Content Preview:                                             │ │
│  │  {                                                             │ │
│  │    "modules": 142,                                            │ │
│  │    "files_scanned": 2847,                                     │ │
│  │    "findings": [...]                                          │ │
│  │  }                                                             │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 9.6 Health Dashboard

Repository and system health monitoring.

```
┌─────────────────────────────────────────────────────────────────────┐
│  Health Dashboard                                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  System Health                                                      │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ │
│  │  API        │ │  Scheduler  │ │  Evidence   │ │  Search     │ │
│  │  ● Healthy  │ │  ● Healthy  │ │  ● Healthy  │ │  ● Degraded │ │
│  │  99.97%     │ │  99.99%     │ │  100%       │ │  99.2%      │ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ │
│                                                                     │
│  Repository Health Distribution                                     │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │  Healthy (>80):  189 (77%)  ████████████████████             │ │
│  │  Warning (60-80): 42 (17%)  ████                              │ │
│  │  Critical (<60):  16 (6%)   █                                 │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  Critical Repositories                                              │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │  owner/legacy-app    Health: 34  │  12 critical findings     │ │
│  │  owner/old-service   Health: 41  │  8 critical findings      │ │
│  │  owner/unmaintained  Health: 45  │  6 critical findings      │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 9.7 Risk Dashboard

Organization-wide risk analysis.

```
┌─────────────────────────────────────────────────────────────────────┐
│  Risk Dashboard                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Risk by Category                                                   │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │  Security      23 findings  ████████████  HIGH               │ │
│  │  Complexity    45 findings  ████████████████████  MEDIUM     │ │
│  │  Debt          67 findings  ████████████████████████████  LOW│ │
│  │  Coverage      12 findings  █████  LOW                       │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  Risk by Language                                                   │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │  Python    156 repos  avg risk: 32  ████████                 │ │
│  │  JavaScript 78 repos  avg risk: 28  ██████                   │ │
│  │  Go         13 repos  avg risk: 15  ███                      │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  Risk Trend (90 days)                                               │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │  [Line chart showing risk score trend over 90 days]          │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 9.8 Operator Console

Administrative interface for platform operators.

```
┌─────────────────────────────────────────────────────────────────────┐
│  Operator Console                                                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  System Overview                                                    │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ │
│  │  Uptime     │ │  CPU        │ │  Memory     │ │  Storage    │ │
│  │  45d 12h    │ │  23%        │ │  67%        │ │  45%        │ │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘ │
│                                                                     │
│  Active Jobs                                                        │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │  scheduler-01    3 missions running   CPU: 12%                │ │
│  │  worker-01       2 missions running   CPU: 8%                 │ │
│  │  worker-02       1 mission running    CPU: 5%                 │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  Organization Management                                            │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │  acme-corp       247 repos  12 users  Plan: Enterprise       │ │
│  │  startup-inc     23 repos   4 users   Plan: Professional     │ │
│  │  open-source-org 12 repos   8 users   Plan: Community        │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  [Manage Organizations]  [System Settings]  [Audit Logs]           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 10. Multi-tenancy

### Hierarchy

```
Organization
├── Project
│   ├── Repository
│   ├── Repository
│   └── Repository
├── Project
│   ├── Repository
│   └── Repository
├── Team
│   └── Members (Users)
├── Policy Rules
└── Users
```

### Isolation Model

| Resource | Isolation Level | Mechanism |
|----------|-----------------|-----------|
| Data | Strong | Row-level security (RLS) in PostgreSQL |
| Compute | Shared | Request-scoped tenant context |
| Storage | Strong | Prefix-based isolation (org_id/) |
| Network | Shared | Service mesh with tenant headers |
| Secrets | Strong | Vault with org-scoped policies |

### Row-Level Security

```sql
-- Enable RLS on all tenant-scoped tables
ALTER TABLE missions ENABLE ROW LEVEL SECURITY;

CREATE POLICY org_isolation ON missions
    USING (organization_id = current_setting('app.current_org')::UUID);
```

### Tenant Context

Every request carries tenant context:

```python
@dataclass
class TenantContext:
    organization_id: UUID
    user_id: UUID
    roles: list[str]
    permissions: list[str]
```

Injected via middleware:

```
Request → Auth Middleware → JWT Decode → Tenant Context → Service
```

---

## 11. Security

### RBAC Model

```
Organization Owner
├── Full access to all resources
├── Manage users and teams
├── Configure policies
└── Delete organization

Organization Admin
├── Manage projects and repositories
├── Create and approve missions
├── Manage policies
└── View audit logs

Project Manager
├── Manage repositories in project
├── Create missions
├── Approve missions (within project)
└── View evidence and reports

Developer
├── View repositories
├── View missions
├── View evidence
└── Create draft missions

Viewer
├── View repositories
├── View missions
└── View reports
```

### Permission Matrix

| Resource | Owner | Admin | Manager | Developer | Viewer |
|----------|-------|-------|---------|-----------|--------|
| Organization | CRUD | R | R | R | R |
| Project | CRUD | CRUD | R | R | R |
| Repository | CRUD | CRUD | CRUD | R | R |
| Mission | CRUD | CRUD | CRU | R | R |
| Evidence | CRUD | R | R | R | R |
| Policy | CRUD | CRUD | R | - | - |
| User | CRUD | CU | R | - | - |
| Audit Log | R | R | - | - | - |

### SSO Integration

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Identity   │────►│  Hermes     │────►│  Application│
│  Provider   │     │  Auth       │     │  Session    │
│  (SAML/OIDC)│     │  Service    │     │             │
└─────────────┘     └─────────────┘     └─────────────┘
```

Supported providers:
- Okta (SAML 2.0)
- Azure AD (OIDC)
- Google Workspace (OIDC)
- Keycloak (SAML 2.0 / OIDC)
- Custom (SAML 2.0)

### Audit Logging

Every action logged:

```json
{
  "timestamp": "2026-08-09T12:00:00Z",
  "actor": "user@company.com",
  "action": "mission.approve",
  "resource": "mission/uuid",
  "organization": "acme-corp",
  "ip_address": "192.168.1.100",
  "user_agent": "Mozilla/5.0...",
  "changes": {
    "status": ["draft", "approved"]
  }
}
```

Audit logs are:
- Append-only
- Cryptographically chained (hash chain)
- Exportable (SOC 2, ISO 27001)
- Retained for 7 years (configurable)

### Secrets Management

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Application │────►│  Vault      │────►│  Database   │
│  (Request)   │     │  (HashiCorp)│     │  (Encrypted)│
└─────────────┘     └─────────────┘     └─────────────┘
```

Secrets stored:
- GitHub tokens → Vault, org-scoped
- AI provider keys → Vault, org-scoped
- Webhook secrets → Vault, org-scoped
- Database credentials → Vault, environment-scoped

### Encryption

| Data | At Rest | In Transit |
|------|---------|------------|
| Database | AES-256 | TLS 1.3 |
| Object Storage | AES-256 | TLS 1.3 |
| Evidence | AES-256 | TLS 1.3 |
| Secrets | Vault encryption | TLS 1.3 |
| API Traffic | N/A | TLS 1.3 |

### Repository Permissions

GitHub App installation scoped to:
- Specific repositories (not all)
- Read-only permissions (metadata, contents, actions)
- No admin permissions
- No delete permissions

---

## 12. GitHub Integration

### Current Capabilities (v1.0)

```
Read-Only Operations
├── Repository metadata
├── Branch listing
├── File content retrieval
├── Pull request listing
├── Workflow run status
├── Commit history
└── Materialization (git clone)
```

### Professional Capabilities (v1.1)

```
Write Operations (Limited)
├── Branch creation (for mission branches)
├── Draft PR creation (for mission results)
├── Status check posting
├── PR comment posting
└── Workflow trigger (repository_dispatch)
```

### Enterprise Capabilities (v2.0)

```
Full Integration
├── Multi-organization support
├── GitHub App management
├── Webhook processing at scale
├── Cross-repository analysis
├── Automated PR approval (configurable)
├── Branch protection integration
└── Custom status checks
```

### GitHub App Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  GitHub     │────►│  GitHub     │────►│  Hermes     │
│  Webhooks   │     │  Service    │     │  Enterprise │
│             │◄────│             │◄────│             │
└─────────────┘     └─────────────┘     └─────────────┘
```

GitHub App permissions:
- **Repository permissions:**
  - Contents: Read-only
  - Metadata: Read-only
  - Actions: Read-only
  - Pull requests: Read & Write (Professional+)
  - Statuses: Read & Write (Professional+)
- **Organization permissions:**
  - Members: Read-only
- **Events:**
  - Push
  - Pull request
  - Workflow run
  - Installation

### Future Write Model

```
Mission Execution
      │
      ▼
┌─────────────────┐
│  Create Branch   │  hermes/mission-{id}
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Apply Changes   │  Commit files
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Push Branch     │  Push to origin
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Create Draft PR │  Title, description, labels
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Request Review  │  Assign reviewers
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Await Approval  │  Human reviews PR
└─────────────────┘
```

---

## 13. AI Provider Layer

### Provider Abstraction

```python
class AIProvider(ABC):
    @abstractmethod
    def analyze(self, prompt: str, context: dict) -> AIResponse: ...

    @abstractmethod
    def generate_mission(self, findings: list[Finding]) -> MissionDraft: ...

    @abstractmethod
    def explain(self, evidence: EvidenceRecord) -> str: ...
```

### Supported Providers

| Provider | Models | Use Case |
|----------|--------|----------|
| OpenAI | GPT-4o, GPT-4o-mini | General analysis, mission generation |
| Anthropic | Claude 3.5 Sonnet | Complex reasoning, code review |
| Google | Gemini 1.5 Pro | Large context analysis |
| Local | Llama 3.1, Mistral | Air-gapped environments |
| Azure OpenAI | GPT-4o | Enterprise with Azure commitment |

### Prompt Management

```
┌─────────────────┐
│  Prompt Store    │  Versioned, templated
│  (Database)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Template Engine │  Variable substitution
│  (Jinja2)       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Provider Router │  Select provider by config
│                  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Response Parser │  Validate & extract
│                  │
└─────────────────┘
```

### Model Routing

```yaml
routing:
  default: openai/gpt-4o
  rules:
    - match:
        mission_type: security-scan
      provider: anthropic/claude-3.5-sonnet
    - match:
        organization: air-gapped-corp
      provider: local/llama-3.1-70b
    - match:
        task: simple-analysis
      provider: openai/gpt-4o-mini
```

### Cost Management

- Per-organization token budgets
- Usage tracking and alerting
- Model fallback on budget exceeded
- Cost attribution to projects/repositories

---

## 14. Policy Engine

### Policy Types

#### Repository Policies

```yaml
name: require-readme
type: repository
condition:
  file_not_exists: "README.md"
action:
  type: finding
  severity: medium
  message: "Repository missing README"
```

#### Mission Policies

```yaml
name: require-approval-for-high-risk
type: mission
condition:
  risk_score: "> 70"
action:
  type: approval_required
  approvers:
    - team: security-team
    - role: admin
```

#### Execution Policies

```yaml
name: limit-concurrent-missions
type: execution
condition:
  active_missions: "> 5"
action:
  type: queue
  max_concurrent: 5
```

#### Approval Policies

```yaml
name: security-missions-need-security-approval
type: approval
condition:
  mission_type: security-scan
action:
  type: require_approval
  approvers:
    - team: security-team
  timeout: 48h
  escalate_to: org-owner
```

#### Risk Policies

```yaml
name: auto-reject-critical-risk
type: risk
condition:
  risk_score: "> 90"
  risk_category: security
action:
  type: reject
  reason: "Critical security risk requires manual review"
```

#### Compliance Policies

```yaml
name: soc2-evidence-retention
type: compliance
condition:
  evidence_type: "*"
action:
  type: retain
  duration: 7years
  immutable: true
```

### Policy Evaluation

```
Event Received
      │
      ▼
┌─────────────────┐
│  Load Policies   │  Organization + Project
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Evaluate Rules  │  Condition matching
└────────┬────────┘
         │
    ┌────┼────┐
    │    │    │
    ▼    ▼    ▼
 Allow  Deny  Require
        │     Approval
        │        │
        ▼        ▼
   Log &     Notify &
   Proceed    Wait
```

### Policy Testing

```
POST /v1/policies/:id/test
{
  "scenario": {
    "repository": "owner/repo",
    "mission_type": "security-scan",
    "risk_score": 75
  }
}

Response:
{
  "decision": "require_approval",
  "matched_rules": ["require-approval-for-high-risk"],
  "reason": "Risk score 75 exceeds threshold 70"
}
```

---

## 15. Deployment

### Single Node

```
┌─────────────────────────────────────────┐
│  Single Server                          │
│  ┌───────────────────────────────────┐  │
│  │  Docker Compose                    │  │
│  │  ├── hermes-api                    │  │
│  │  ├── hermes-worker                 │  │
│  │  ├── hermes-scheduler              │  │
│  │  ├── postgres                      │  │
│  │  ├── redis                         │  │
│  │  └── nginx (reverse proxy)         │  │
│  └───────────────────────────────────┘  │
│                                         │
│  Requirements:                          │
│  ├── 4 CPU cores                        │
│  ├── 16 GB RAM                          │
│  ├── 100 GB SSD                         │
│  └── Ubuntu 22.04+                      │
└─────────────────────────────────────────┘
```

### Docker

```yaml
# docker-compose.yml
version: '3.8'
services:
  api:
    image: hermes/enterprise:latest
    ports:
      - "8080:8080"
    environment:
      DATABASE_URL: postgresql://...
      REDIS_URL: redis://...
    depends_on:
      - postgres
      - redis

  worker:
    image: hermes/enterprise:latest
    command: hermes-worker
    environment:
      DATABASE_URL: postgresql://...
      REDIS_URL: redis://...

  scheduler:
    image: hermes/enterprise:latest
    command: hermes-scheduler
    environment:
      DATABASE_URL: postgresql://...
      REDIS_URL: redis://...

  postgres:
    image: postgres:16
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    volumes:
      - redisdata:/data

volumes:
  pgdata:
  redisdata:
```

### Kubernetes

```yaml
# k8s deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hermes-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: hermes-api
  template:
    spec:
      containers:
        - name: api
          image: hermes/enterprise:latest
          ports:
            - containerPort: 8080
          resources:
            requests:
              memory: "512Mi"
              cpu: "250m"
            limits:
              memory: "1Gi"
              cpu: "500m"
```

### Enterprise HA

```
┌─────────────────────────────────────────────────────────────────────┐
│  Load Balancer                                                      │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
            ┌───────────────────┼───────────────────┐
            │                   │                   │
            ▼                   ▼                   ▼
    ┌───────────────┐  ┌───────────────┐  ┌───────────────┐
    │  API Node 1   │  │  API Node 2   │  │  API Node 3   │
    │  (Primary)    │  │  (Secondary)  │  │  (Secondary)  │
    └───────┬───────┘  └───────┬───────┘  └───────┬───────┘
            │                   │                   │
            └───────────────────┼───────────────────┘
                                │
            ┌───────────────────┼───────────────────┐
            │                   │                   │
            ▼                   ▼                   ▼
    ┌───────────────┐  ┌───────────────┐  ┌───────────────┐
    │  PostgreSQL   │  │  PostgreSQL   │  │  PostgreSQL   │
    │  (Primary)    │  │  (Replica)    │  │  (Replica)    │
    └───────────────┘  └───────────────┘  └───────────────┘
```

### Cloud

| Provider | Service | Notes |
|----------|---------|-------|
| AWS | ECS / EKS | Recommended for enterprise |
| GCP | GKE | Good for multi-region |
| Azure | AKS | Good for Azure AD integration |
| DigitalOcean | DOKS | Good for professional |

### On-Premise

- Air-gapped deployment supported
- Local AI models only
- No external network requirements
- Custom certificate authority support

---

## 16. Scalability

### 10 Repositories

```
Single Node
├── API: 1 instance
├── Worker: 1 instance
├── Database: SQLite or PostgreSQL
├── Storage: Local filesystem
└── AI: Single provider
```

**Resources:** 2 CPU, 8 GB RAM, 50 GB disk.

### 100 Repositories

```
Single Node (Upgraded)
├── API: 1 instance
├── Worker: 2 instances
├── Database: PostgreSQL
├── Storage: S3-compatible
└── AI: 1-2 providers
```

**Resources:** 4 CPU, 16 GB RAM, 200 GB SSD.

### 1,000 Repositories

```
Multi-Node
├── API: 2 instances (load balanced)
├── Worker: 4 instances
├── Database: PostgreSQL (primary + replica)
├── Storage: S3
├── Search: Elasticsearch (single node)
└── AI: Multiple providers with routing
```

**Resources:** 8 CPU, 32 GB RAM, 500 GB SSD per node.

### 10,000 Repositories

```
Kubernetes Cluster
├── API: 5+ instances (HPA)
├── Worker: 10+ instances (HPA)
├── Database: PostgreSQL (HA cluster)
├── Storage: S3
├── Search: Elasticsearch (3-node cluster)
├── Redis: Cluster mode
└── AI: Provider pool with load balancing
```

**Resources:** 16 CPU, 64 GB RAM per node, 10+ nodes.

### 100,000 Repositories

```
Multi-Region Kubernetes
├── API: 10+ instances per region
├── Worker: 50+ instances (auto-scaling)
├── Database: PostgreSQL (multi-region, read replicas)
├── Storage: S3 (multi-region)
├── Search: Elasticsearch (cross-cluster)
├── Redis: Regional clusters
├── AI: Dedicated GPU instances
└── CDN: Static asset delivery
```

**Resources:** 100+ nodes, 16+ CPU, 64+ GB RAM each.

### Performance Targets

| Metric | 10 repos | 100 repos | 1K repos | 10K repos |
|--------|----------|-----------|----------|-----------|
| API latency (p99) | < 100ms | < 150ms | < 200ms | < 300ms |
| Scan time | < 5min | < 30min | < 2hr | < 8hr |
| Mission execution | < 10min | < 30min | < 1hr | < 4hr |
| Search latency | < 50ms | < 100ms | < 200ms | < 500ms |

---

## 17. Disaster Recovery

### Backup Strategy

| Data | Frequency | Retention | Method |
|------|-----------|-----------|--------|
| Database | Hourly | 30 days | pg_dump + WAL archiving |
| Object Storage | Daily | 90 days | S3 versioning + cross-region |
| Configuration | On change | 30 days | Git + database |
| Secrets | On change | 90 days | Vault backup |

### Restore Procedures

```
Database Restore
├── Point-in-time recovery (WAL replay)
├── Full restore from daily backup
└── Cross-region replica promotion

Object Storage Restore
├── S3 version restore
├── Cross-region replication failover
└── Manual restore from backup

Application Restore
├── Redeploy from container registry
├── Restore configuration from database
└── Re-seed secrets from Vault
```

### Recovery Objectives

| Metric | Target |
|--------|--------|
| RPO (Recovery Point Objective) | 1 hour |
| RTO (Recovery Time Objective) | 4 hours |
| MTTR (Mean Time To Repair) | 2 hours |
| Availability | 99.9% (8.76 hours downtime/year) |

### Replication

```
Primary Region (US-East)
├── PostgreSQL Primary
├── Redis Primary
├── S3 Primary
└── API/Worker (3 replicas)

Secondary Region (US-West)
├── PostgreSQL Replica (async)
├── Redis Replica
├── S3 Cross-Region Replica
└── API/Worker (2 replicas, standby)
```

Failover:
- Automated database failover (Patroni/etcd)
- Manual application failover (DNS switch)
- Automatic storage failover (S3 cross-region)

---

## 18. Licensing

### Community (Open Source)

**License:** MIT

```
Hermes Core Runtime
├── All CLI commands
├── All scanners (Python, JavaScript, TypeScript)
├── Repository Intelligence (single repo)
├── Engineering Intelligence (single repo)
├── Engineering Governance (single repo)
├── Mission Planning & Execution
├── Evidence Collection & Review
├── Health Monitoring
├── Safety System
├── GitHub Provider (read-only)
├── Provider Abstraction
└── Readiness Assessment
```

### Professional

**License:** Commercial (per-repository)

```
Everything in Community, plus:
├── Web Dashboard (single-user)
├── REST API
├── Multi-repository management (up to 50)
├── Scheduled missions
├── Notifications (email, Slack webhook)
├── GitHub integration (branch, draft PR)
├── AI-assisted mission generation
├── Trend analysis
├── Email support
└── Documentation
```

**Pricing:** $49/repository/year (up to 50 repositories)

### Enterprise

**License:** Commercial (per-organization)

```
Everything in Professional, plus:
├── Multi-tenant architecture
├── Organization hierarchy
├── RBAC
├── SSO (SAML, OIDC)
├── Unlimited repositories
├── Policy engine (custom rules)
├── Approval workflows
├── Compliance reporting
├── High availability
├── Kubernetes deployment
├── Custom AI models
├── Audit log export
├── 24/7 support
└── Professional services
```

**Pricing:** Custom (based on repositories, users, deployment)

---

## 19. Five-Year Vision

### Year 1 (2026-2027): Foundation

```
Q1 2026: Hermes Core v1.0 (Stable Release)
├── Multi-language scanning
├── Repository Intelligence
├── Engineering Intelligence
├── Mission Execution
└── Evidence System

Q2 2026: Hermes Enterprise v1.0
├── Web Dashboard
├── REST API
├── Multi-tenancy (basic)
├── GitHub integration (write)
└── Professional tier

Q3 2026: Hermes Enterprise v1.1
├── Policy Engine
├── Approval Workflows
├── AI Provider Layer
├── Notification Service
└── SSO Integration

Q4 2026: Hermes Enterprise v1.2
├── Compliance Reporting
├── Advanced Analytics
├── Custom AI Models
├── Audit Log Export
└── Enterprise tier
```

### Year 2 (2027-2028): Scale

```
Q1 2027: Multi-Region Support
├── Cross-region replication
├── Global load balancing
├── Regional data residency
└── Multi-cloud deployment

Q2 2027: Advanced Analytics
├── Predictive risk scoring
├── Trend forecasting
├── Anomaly detection
└── Custom dashboards

Q3 2027: Ecosystem
├── Plugin marketplace
├── Custom scanner development
├── Third-party integrations
├── API ecosystem

Q4 2027: Enterprise Features
├── SAML 2.0 / OIDC
├── Custom roles and permissions
├── Data export / import
├── Compliance certifications (SOC 2)
```

### Year 3 (2028-2029): Intelligence

```
Q1 2028: AI-Powered Governance
├── Natural language policy creation
├── Automated remediation suggestions
├── Risk prediction
└── Intelligent alerting

Q2 2028: Cross-Repository Intelligence
├── Dependency graph analysis
├── Security vulnerability correlation
├── Code pattern detection
└── Architecture analysis

Q3 2028: Autonomous Operations
├── Self-healing missions
├── Adaptive scheduling
├── Resource optimization
└── Cost optimization

Q4 2028: Enterprise Intelligence
├── Executive dashboards
├── ROI measurement
├── Team performance analytics
└── Technology radar
```

### Year 4 (2029-2030): Platform

```
Q1 2029: Platform Ecosystem
├── Third-party mission types
├── Custom evidence types
├── Plugin architecture
├── Developer SDK

Q2 2029: Global Deployment
├── Multi-region active-active
├── Edge computing support
├── IoT device management
└── Satellite repositories

Q3 2029: Advanced Compliance
├── ISO 27001 automation
├── GDPR compliance tools
├── HIPAA compliance
└── PCI DSS compliance

Q4 2029: Enterprise Platform
├── White-label support
├── Multi-tenant isolation
├── Custom branding
├── SLA management
```

### Year 5 (2030-2031): Future

```
Q1 2030: Autonomous Engineering
├── Self-directed missions
├── Predictive maintenance
├── Code generation
└── Architecture evolution

Q2 2030: Quantum-Ready
├── Quantum-resistant encryption
├── Post-quantum cryptography
├── Quantum computing integration
└── Quantum-safe algorithms

Q3 2030: Global Intelligence
├── Cross-organization analytics
├── Industry benchmarking
├── Best practice recommendations
└── Technology trend analysis

Q4 2030: Hermes Platform
├── Complete engineering platform
├── Developer experience focus
├── Enterprise-grade reliability
└── Global availability
```

---

## 20. Architectural Principles

These principles are immutable. They define what Hermes is and what it must never become.

### 1. Evidence Over Opinion

Every claim must be backed by verifiable evidence. No assertion is accepted without data. This applies to risk scores, recommendations, governance decisions, and system health assessments.

### 2. Human Approval is Sacred

No mission executes without explicit human approval. No policy bypasses human review. No automation replaces human judgment for consequential decisions. The system recommends; humans decide.

### 3. Determinism is Non-Negotiable

Same inputs always produce same outputs. JSON keys sorted. Timestamps normalized. Reports derived from a single canonical model. No randomness in outputs. No hidden state. No magic.

### 4. Immutability for Evidence

Published evidence is append-only. Records cannot be modified after publication. Integrity is cryptographically verifiable. History cannot be rewritten.

### 5. Durability Over Convenience

Every state mutation uses atomic writes. No partial state survives a crash. Crash recovery recovers full context. Data loss is unacceptable.

### 6. Composability Over Monolith

Each subsystem has a narrow interface. CLIs compose libraries. Libraries don't depend on CLIs. Services are independently deployable. Modules don't do each other's jobs.

### 7. Safety Cannot Be Disabled

Worktree isolation is mandatory. Diff scope validation is mandatory. Readiness assessment is mandatory. These are not configuration options. They are architectural constraints.

### 8. Audit Everything

Every action is logged. Every decision is traceable. Every state change is recorded. Audit trails are complete, immutable, and exportable.

### 9. Fail Loud

Errors raise exceptions with descriptive messages. No silent failures. No swallowed exceptions. Graceful degradation over crash. Recoverable queues over lost work.

### 10. Open Core

The core engine remains open source. Enterprise capabilities extend, never replace. The community benefits from enterprise investment. Enterprise customers benefit from community contributions.

---

## Appendix A: Technology Stack

| Layer | Technology | Rationale |
|-------|------------|-----------|
| Frontend | React, TypeScript | Component ecosystem, type safety |
| API | Python, FastAPI | Async, OpenAPI, performance |
| Database | PostgreSQL | ACID, JSONB, RLS, reliability |
| Cache | Redis | Performance, pub/sub, queues |
| Search | Elasticsearch | Full-text, aggregations, scaling |
| Object Storage | S3 / MinIO | Durability, scalability, compatibility |
| Message Queue | Redis Streams | Simplicity, reliability, performance |
| Auth | Keycloak / Auth0 | SSO, RBAC, compliance |
| Secrets | HashiCorp Vault | Encryption, rotation, audit |
| Monitoring | Prometheus, Grafana | Metrics, alerting, dashboards |
| Logging | ELK Stack | Centralized, searchable, scalable |
| Tracing | OpenTelemetry | Distributed tracing, correlation |

## Appendix B: API Response Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created |
| 204 | No Content |
| 400 | Bad Request |
| 401 | Unauthorized |
| 403 | Forbidden |
| 404 | Not Found |
| 409 | Conflict |
| 422 | Unprocessable Entity |
| 429 | Too Many Requests |
| 500 | Internal Server Error |
| 503 | Service Unavailable |

## Appendix C: Mission Types

| Type | Description | Risk Level |
|------|-------------|------------|
| remediation | Fix known issues | Medium |
| security-scan | Security analysis | High |
| dependency-update | Update dependencies | Medium |
| code-quality | Improve code quality | Low |
| documentation | Update documentation | Low |
| refactoring | Restructure code | High |
| testing | Improve test coverage | Low |
| compliance | Ensure compliance | High |
| migration | Technology migration | High |
| custom | User-defined | Variable |

## Appendix D: Event Correlation

Every event carries:
- `event_id` — unique identifier
- `trace_id` — distributed trace identifier
- `correlation_id` — links related events
- `parent_event_id` — event that triggered this event

This enables:
- End-to-end tracing
- Causal analysis
- Debugging complex workflows
- Performance analysis

---

**End of Architecture Specification**
