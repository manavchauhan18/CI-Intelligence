# Multi-Agent CI/CD Intelligence Platform (A2A)

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)

A **production-grade Agent-to-Agent (A2A) platform** that validates code changes through autonomous agents collaborating asynchronously before deployment. This system prevents faulty deployments by ensuring commit intent matches actual code changes through security, performance, and quality validation.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Agents](#agents)
- [API Reference](#api-reference)
- [Deployment](#deployment)
- [Development](#development)
- [Monitoring](#monitoring)
- [Contributing](#contributing)

---

## Overview

This platform consists of **autonomous agents** that independently analyze code changes and collaborate asynchronously through Redis Streams to reach a release decision. Unlike traditional linear CI checks, agents reason independently using both deterministic rules and LLM-powered analysis.

### Key Benefits

- ✅ Prevent deployment of code that doesn't match commit intent
- ✅ Automated security vulnerability detection (secrets, injection risks)
- ✅ Performance anti-pattern identification (N+1 queries, blocking calls)
- ✅ Test coverage analysis
- ✅ Explainable AI-driven decisions
- ✅ Horizontally scalable and fault-tolerant
- ✅ Production-ready with observability built-in

---

## Architecture

### High-Level Components

```
┌──────────────┐
│   CI/CD      │
│  Pipeline    │
└──────┬───────┘
       │
       ▼
┌──────────────────────────────────────────┐
│         API Gateway (FastAPI)             │
│  - Authentication (HMAC)                  │
│  - Job Creation                           │
└──────────────┬───────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────┐
│      Message Bus (Redis Streams)          │
│  - code_analysis_requested                │
│  - agent_results                          │
│  - release_decisions                      │
└──────────────┬───────────────────────────┘
               │
       ┌───────┴───────┐
       │               │
       ▼               ▼
┌─────────────┐ ┌─────────────┐
│  Agents     │ │ Orchestrator│
│ (Autonomous)│ │  (Tracker)  │
└─────────────┘ └─────────────┘
       │
       ├── Diff Analysis Agent
       ├── Commit Intent Agent (LLM)
       ├── Security Agent (Hybrid)
       ├── Performance Agent (LLM)
       ├── Test Impact Agent
       └── Release Arbiter Agent
```

### Agent Communication Flow

1. **Developer** pushes code → CI pipeline triggered
2. **CI Pipeline** sends webhook to API Gateway
3. **API Gateway** creates job, publishes `code_analysis_requested` event
4. **Agents** consume event independently and perform analysis
5. Each **Agent** publishes result to `agent_results` stream
6. **Arbiter Agent** aggregates results and applies decision matrix
7. **Arbiter** publishes final decision to `release_decisions` stream
8. **Orchestrator** updates job status in database
9. **CI Pipeline** queries job status and proceeds/blocks deployment

---

## Features

### 🔍 Intelligent Analysis

- **Diff Analysis**: Categorizes changes (DB, API, UI, etc.) and calculates risk
- **Intent Validation**: LLM-powered comparison of commit message vs actual changes
- **Security Scanning**: Regex + LLM hybrid detection of secrets and vulnerabilities
- **Performance Analysis**: Identifies N+1 queries, blocking calls, heavy loops
- **Test Impact**: Analyzes test coverage delta and untested paths

### 🤖 Agent-to-Agent Architecture

- **Autonomous Agents**: Each agent operates independently
- **Asynchronous Communication**: No blocking, event-driven via Redis Streams
- **Weighted Decision Matrix**: Configurable weights per agent
- **Fault Tolerance**: Agents can fail independently without system failure
- **Horizontal Scaling**: Scale agents individually based on load

### 🔐 Production-Ready

- **HMAC Authentication**: Secure CI/CD pipeline integration
- **Database Persistence**: PostgreSQL for audit trails
- **Observability**: OpenTelemetry, Prometheus, Grafana ready
- **Docker & Kubernetes**: Complete deployment configurations
- **Health Checks**: Built-in health endpoints for all services

---

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- PostgreSQL 15+
- Redis 7+
- OpenAI or Anthropic API key

### Run with Docker Compose

```bash
# Clone repository
git clone https://github.com/your-org/ci-intelligence.git
cd ci-intelligence

# Set environment variables
cp .env.example .env
# Edit .env and add your API keys

# Start all services
docker-compose up -d

# Check service health
curl http://localhost:8000/health
```

### Services will be available at:

- API Gateway: `http://localhost:8000`
- Orchestrator: `http://localhost:8001`
- Diff Agent: `http://localhost:8100`
- Intent Agent: `http://localhost:8101`
- Security Agent: `http://localhost:8102`
- Performance Agent: `http://localhost:8103`
- Test Agent: `http://localhost:8104`
- Arbiter Agent: `http://localhost:8105`

---

## Installation

### Manual Installation

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up database
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/ci_intelligence"

# 3. Run migrations
alembic upgrade head

# 4. Start Redis
redis-server

# 5. Start services (in separate terminals)
python gateway/main.py
python orchestrator/main.py
python agents/diff_agent/main.py
python agents/intent_agent/main.py
python agents/security_agent/main.py
python agents/performance_agent/main.py
python agents/test_agent/main.py
python agents/arbiter_agent/main.py
```

---

## Configuration

### Environment Variables

Key configuration in [.env](.env.example):

```bash
# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ci_intelligence

# Redis
REDIS_URL=redis://localhost:6379/0

# LLM Configuration
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
DEFAULT_LLM_PROVIDER=openai  # or "claude"

# Security
HMAC_SECRET_KEY=your-secret-key-change-in-production
JWT_SECRET_KEY=your-jwt-secret

# Agent Timeouts
AGENT_TIMEOUT_SECONDS=300
ARBITER_WAIT_TIMEOUT_SECONDS=600
```

### Agent Weights

Configure agent weights in [agents/arbiter_agent/main.py](agents/arbiter_agent/main.py):

```python
AGENT_WEIGHTS = {
    "security_agent": 0.35,     # Highest priority
    "intent_agent": 0.25,
    "performance_agent": 0.20,
    "test_agent": 0.20,
    "diff_agent": 0.10,
}
```

---

## Usage

### Submit Analysis Job

```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -H "X-Signature: YOUR_HMAC_SIGNATURE" \
  -H "X-Timestamp: $(date +%s)" \
  -d '{
    "repo_name": "my-org/my-repo",
    "commit_hash": "abc123",
    "commit_message": "Fix authentication bug",
    "diff": "diff --git a/auth.py...",
    "branch": "main",
    "author": "developer"
  }'
```

### Get Job Status

```bash
curl http://localhost:8000/api/v1/jobs/{job_id}
```

### Response Example

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "decision": "approve",
  "explanation": "Release decision: APPROVE\nOverall confidence score: 0.82\n...",
  "agent_results": [
    {
      "agent_name": "security_agent",
      "verdict": "approve",
      "confidence": 0.85
    }
  ]
}
```

---

## Agents

### 1. Diff Analysis Agent

**Responsibility**: Parse git diffs, categorize changes, assess risk level

**Key Logic**:
- Identifies file types (DB, API, UI, config, tests, docs)
- Counts lines added/deleted
- Calculates risk level (LOW/MEDIUM/HIGH/CRITICAL)

**Verdict**: `APPROVE` or `WARN` (never rejects)

---

### 2. Commit Intent Agent

**Responsibility**: Validate commit message matches actual code changes

**Technology**: LLM-powered (GPT-4 / Claude)

**Key Logic**:
- Extracts commit intent from message
- Compares with diff summary
- Identifies discrepancies

**Verdict**: `APPROVE`, `WARN`, or `REJECT`

---

### 3. Security Agent

**Responsibility**: Detect secrets, vulnerabilities, insecure patterns

**Technology**: Hybrid (Regex + LLM)

**Detects**:
- AWS keys, API keys, JWT tokens, private keys
- SQL injection, command injection patterns
- Hardcoded secrets
- Insecure random, eval() usage

**Verdict**: `REJECT` for secrets/critical vulns, otherwise `WARN` or `APPROVE`

---

### 4. Performance Agent

**Responsibility**: Identify performance anti-patterns

**Technology**: Regex + LLM

**Detects**:
- N+1 query patterns
- Blocking calls in async code
- Nested loops
- Synchronous operations in async functions

**Verdict**: `REJECT` for critical issues, `WARN`, or `APPROVE`

---

### 5. Test Impact Agent

**Responsibility**: Analyze test coverage impact

**Key Logic**:
- Categorizes test vs implementation files
- Estimates coverage delta
- Identifies untested paths

**Verdict**: `REJECT` if many impl changes with no tests, otherwise `WARN` or `APPROVE`

---

### 6. Release Arbiter Agent

**Responsibility**: Aggregate all agent results and make final decision

**Decision Algorithm**:
1. Collect results from all agents (or timeout after 10 minutes)
2. Apply weighted scoring based on agent importance
3. Check for blocking issues (e.g., security rejects)
4. Calculate overall confidence score
5. Determine final verdict with explanation

**Weighted Score Calculation**:
```
score = Σ (agent_verdict_score × agent_confidence × agent_weight)
```

**Final Decision**:
- `REJECT` if security/intent rejects OR score < 0.4
- `WARN` if score < 0.7
- `APPROVE` otherwise

---

## API Reference

### POST /api/v1/analyze

Create analysis job

**Request**:
```json
{
  "repo_name": "string",
  "commit_hash": "string",
  "commit_message": "string",
  "diff": "string",
  "branch": "string",
  "author": "string"
}
```

**Response**:
```json
{
  "job_id": "uuid",
  "status": "pending",
  "created_at": "timestamp"
}
```

### GET /api/v1/jobs/{job_id}

Get job status and results

**Response**:
```json
{
  "job_id": "uuid",
  "status": "completed|processing|pending|failed",
  "decision": "approve|warn|reject",
  "explanation": "string",
  "agent_results": [...],
  "created_at": "timestamp",
  "completed_at": "timestamp"
}
```

### GET /api/v1/jobs

List jobs (with optional repo filter)

---

## Deployment

### Docker Compose (Local/Staging)

```bash
docker-compose up -d
```

### Kubernetes (Production)

```bash
# Apply Kubernetes manifests
kubectl apply -f infra/k8s/namespace.yaml
kubectl apply -f infra/k8s/configmap.yaml
kubectl apply -f infra/k8s/secrets.yaml  # Create this with your secrets
kubectl apply -f infra/k8s/gateway-deployment.yaml
kubectl apply -f infra/k8s/agents-deployment.yaml

# Verify deployment
kubectl get pods -n ci-intelligence
```

### CI/CD Integration

See [.github/workflows/ci-intelligence-check.yml](.github/workflows/ci-intelligence-check.yml) for GitHub Actions example.

**Required Secrets**:
- `CI_INTELLIGENCE_URL`: Your platform URL
- `CI_INTELLIGENCE_HMAC`: HMAC secret for authentication
- `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`

---

## Development

### Project Structure

```
ci-intelligence/
├── gateway/              # API Gateway service
├── orchestrator/         # Agent orchestrator
├── agents/              # All agent services
│   ├── base_agent.py    # Base agent class
│   ├── diff_agent/
│   ├── intent_agent/
│   ├── security_agent/
│   ├── performance_agent/
│   ├── test_agent/
│   └── arbiter_agent/
├── shared/              # Shared utilities
│   ├── config.py        # Configuration
│   ├── database.py      # Database models
│   ├── models.py        # Pydantic models
│   ├── message_bus.py   # Redis Streams wrapper
│   └── llm.py           # LLM client
├── infra/               # Infrastructure configs
│   └── k8s/             # Kubernetes manifests
├── alembic/             # Database migrations
├── requirements.txt
├── docker-compose.yml
└── README.md
```

### Running Tests

```bash
# Unit tests
pytest tests/

# Integration tests
pytest tests/integration/

# Load tests
locust -f tests/load/locustfile.py
```

### Adding a New Agent

1. Create agent directory under `agents/`
2. Extend `BaseAgent` class
3. Implement `analyze()` method
4. Add to Docker Compose and Kubernetes manifests
5. Update arbiter's `EXPECTED_AGENTS` set

---

## Monitoring

### Health Checks

All services expose `/health` endpoints:

```bash
curl http://localhost:8000/health  # Gateway
curl http://localhost:8001/health  # Orchestrator
curl http://localhost:8100/health  # Diff Agent
# ... etc
```

### Metrics

Orchestrator exposes metrics at `/metrics`:

```bash
curl http://localhost:8001/metrics
```

**Built with ❤️ for production-grade Agent-to-Agent systems**
