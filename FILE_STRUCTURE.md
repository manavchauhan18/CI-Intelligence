# Complete File Structure

```
ci-intelligence/
│
├── 📄 README.md                          # Main documentation
├── 📄 ARCHITECTURE.md                    # System architecture details
├── 📄 PROJECT_SUMMARY.md                 # Project overview & highlights
├── 📄 QUICKSTART.md                      # 5-minute quick start guide
├── 📄 SETUP_GUIDE.md                     # Complete setup instructions
├── 📄 FILE_STRUCTURE.md                  # This file
│
├── 📄 requirements.txt                   # Python dependencies
├── 📄 .env.example                       # Environment template
├── 📄 .gitignore                         # Git ignore rules
├── 📄 Makefile                           # Development commands
├── 📄 docker-compose.yml                 # Local development stack
├── 📄 Dockerfile.base                    # Base Docker image
│
├── 📁 gateway/                           # API Gateway Service
│   ├── __init__.py
│   └── main.py                           # FastAPI app, authentication, job creation
│
├── 📁 orchestrator/                      # Job Lifecycle Tracker
│   ├── __init__.py
│   └── main.py                           # Consumes agent results, updates DB
│
├── 📁 agents/                            # All Agent Services
│   ├── __init__.py
│   ├── base_agent.py                     # Base class for all agents
│   │
│   ├── 📁 diff_agent/                    # Diff Analysis Agent
│   │   ├── __init__.py
│   │   └── main.py                       # Parses diffs, categorizes changes
│   │
│   ├── 📁 intent_agent/                  # Commit Intent Agent
│   │   ├── __init__.py
│   │   └── main.py                       # LLM validates commit message vs changes
│   │
│   ├── 📁 security_agent/                # Security Agent
│   │   ├── __init__.py
│   │   └── main.py                       # Hybrid detection (Regex + LLM)
│   │
│   ├── 📁 performance_agent/             # Performance Agent
│   │   ├── __init__.py
│   │   └── main.py                       # Detects N+1, blocking calls, etc.
│   │
│   ├── 📁 test_agent/                    # Test Impact Agent
│   │   ├── __init__.py
│   │   └── main.py                       # Analyzes test coverage delta
│   │
│   └── 📁 arbiter_agent/                 # Release Arbiter Agent
│       ├── __init__.py
│       └── main.py                       # Aggregates results, makes final decision
│
├── 📁 shared/                            # Shared Utilities
│   ├── __init__.py
│   ├── config.py                         # Settings management (Pydantic)
│   ├── database.py                       # SQLAlchemy models & connection
│   ├── models.py                         # Pydantic schemas for API/events
│   ├── message_bus.py                    # Redis Streams wrapper
│   └── llm.py                            # LLM client adapter (OpenAI/Claude)
│
├── 📁 alembic/                           # Database Migrations
│   ├── env.py                            # Alembic environment config
│   ├── script.py.mako                    # Migration template
│   └── versions/                         # Migration files (auto-generated)
│       └── (empty - run alembic revision)
│
├── 📄 alembic.ini                        # Alembic configuration
│
├── 📁 infra/                             # Infrastructure Configurations
│   └── 📁 k8s/                           # Kubernetes Manifests
│       ├── namespace.yaml                # ci-intelligence namespace
│       ├── configmap.yaml                # Environment configuration
│       ├── gateway-deployment.yaml       # Gateway deployment & service
│       └── agents-deployment.yaml        # All agent deployments
│
└── 📁 .github/                           # GitHub Configurations
    └── 📁 workflows/
        └── ci-intelligence-check.yml     # GitHub Actions integration example
```

---

## File Descriptions

### 📋 Documentation Files

| File | Purpose |
|------|---------|
| `README.md` | Main project documentation with features, architecture, API reference |
| `ARCHITECTURE.md` | Deep dive into system design, data flow, decision algorithms |
| `PROJECT_SUMMARY.md` | Resume-ready project overview with key achievements |
| `QUICKSTART.md` | Get started in 5 minutes with Docker Compose |
| `SETUP_GUIDE.md` | Complete setup instructions for all deployment methods |
| `FILE_STRUCTURE.md` | This file - complete file tree with descriptions |

### ⚙️ Configuration Files

| File | Purpose |
|------|---------|
| `requirements.txt` | Python dependencies (FastAPI, SQLAlchemy, etc.) |
| `.env.example` | Environment variable template |
| `.gitignore` | Git ignore rules for Python, Docker, IDE files |
| `Makefile` | Development commands (install, dev, up, down, etc.) |
| `docker-compose.yml` | Local development stack (all services) |
| `Dockerfile.base` | Base Docker image for all services |
| `alembic.ini` | Alembic database migration configuration |

### 🚪 Gateway Service

| File | Lines | Purpose |
|------|-------|---------|
| `gateway/main.py` | ~250 | FastAPI app, HMAC authentication, job creation, status endpoints |

**Key Endpoints:**
- `POST /api/v1/analyze` - Create analysis job
- `GET /api/v1/jobs/{job_id}` - Get job status
- `GET /api/v1/jobs` - List jobs
- `GET /health` - Health check

### 🎭 Orchestrator Service

| File | Lines | Purpose |
|------|-------|---------|
| `orchestrator/main.py` | ~200 | Consumes agent results, updates database, tracks job lifecycle |

**Key Functions:**
- Consume agent results from Redis
- Update job status (pending → processing → completed)
- Consume release decisions
- Finalize jobs with decision

### 🤖 Agent Services

| Agent | File | Lines | Purpose |
|-------|------|-------|---------|
| **Base** | `agents/base_agent.py` | ~120 | Abstract base class with common functionality |
| **Diff** | `agents/diff_agent/main.py` | ~200 | Parse diffs, categorize changes, assess risk |
| **Intent** | `agents/intent_agent/main.py` | ~250 | LLM validates commit message vs actual changes |
| **Security** | `agents/security_agent/main.py` | ~300 | Hybrid detection (Regex + LLM) for vulnerabilities |
| **Performance** | `agents/performance_agent/main.py` | ~200 | Detect N+1 queries, blocking calls, heavy loops |
| **Test** | `agents/test_agent/main.py` | ~180 | Analyze test coverage impact |
| **Arbiter** | `agents/arbiter_agent/main.py` | ~280 | Aggregate results, weighted decision algorithm |

### 🔧 Shared Utilities

| File | Lines | Purpose |
|------|-------|---------|
| `shared/config.py` | ~80 | Pydantic settings management |
| `shared/database.py` | ~150 | SQLAlchemy models (AnalysisJob, AgentResult, ReleaseDecision) |
| `shared/models.py` | ~200 | Pydantic schemas for API requests/responses & events |
| `shared/message_bus.py` | ~250 | Redis Streams wrapper with consumer groups |
| `shared/llm.py` | ~180 | LLM client adapter (OpenAI/Claude with fallback) |

### 🗄️ Database

**Schema (3 tables):**

1. **analysis_jobs**
   - `id` (UUID, PK)
   - `repo_name`, `commit_hash`, `commit_message`
   - `branch`, `author`
   - `status` (pending/processing/completed/failed)
   - `created_at`, `completed_at`

2. **agent_results**
   - `id` (Integer, PK)
   - `job_id` (FK → analysis_jobs)
   - `agent_name`, `verdict`, `confidence`
   - `payload` (JSONB)
   - `created_at`

3. **release_decisions**
   - `id` (Integer, PK)
   - `job_id` (FK → analysis_jobs, unique)
   - `decision`, `explanation`
   - `agent_results_summary` (JSONB)
   - `created_at`

### 🐳 Docker & Kubernetes

| File | Purpose |
|------|---------|
| `docker-compose.yml` | 11 services (postgres, redis, gateway, orchestrator, 6 agents) |
| `Dockerfile.base` | Multi-stage build for all Python services |
| `infra/k8s/namespace.yaml` | Kubernetes namespace definition |
| `infra/k8s/configmap.yaml` | Environment configuration for K8s |
| `infra/k8s/gateway-deployment.yaml` | Gateway deployment (3 replicas) + LoadBalancer |
| `infra/k8s/agents-deployment.yaml` | All agent deployments with replicas |

### 🔄 CI/CD Integration

| File | Purpose |
|------|---------|
| `.github/workflows/ci-intelligence-check.yml` | GitHub Actions workflow example |

**Workflow Steps:**
1. Checkout code
2. Get commit diff
3. Submit to CI Intelligence API
4. Wait for results (with timeout)
5. Check decision (approve/warn/reject)
6. Comment on PR with results

---

## Code Statistics

```
Total Files: ~45
Total Python Files: ~30
Total Lines of Code: ~3,500

Breakdown:
- Gateway: ~250 lines
- Orchestrator: ~200 lines
- Agents: ~1,600 lines (6 agents)
- Shared: ~860 lines
- Config: ~190 lines
- Documentation: ~1,400 lines
```

---

## Dependencies

### Core (requirements.txt)

```
fastapi==0.109.0          # API framework
uvicorn==0.27.0           # ASGI server
pydantic==2.5.3           # Data validation
sqlalchemy==2.0.25        # ORM
asyncpg==0.29.0           # Async PostgreSQL driver
redis==5.0.1              # Redis client
openai==1.10.0            # OpenAI API
anthropic==0.18.1         # Claude API
alembic==1.13.1           # Database migrations
opentelemetry-*           # Observability
```

### Infrastructure

```
PostgreSQL 15+            # Database
Redis 7+                  # Message bus
Docker 20+                # Containerization
Kubernetes 1.25+          # Orchestration (production)
```

---

## Service Ports

| Service | Port | Purpose |
|---------|------|---------|
| Gateway | 8000 | Main API endpoint |
| Orchestrator | 8001 | Internal metrics |
| Diff Agent | 8100 | Health check |
| Intent Agent | 8101 | Health check |
| Security Agent | 8102 | Health check |
| Performance Agent | 8103 | Health check |
| Test Agent | 8104 | Health check |
| Arbiter Agent | 8105 | Health check + metrics |
| PostgreSQL | 5432 | Database |
| Redis | 6379 | Message bus |

---

## Redis Streams

| Stream Name | Purpose | Producers | Consumers |
|-------------|---------|-----------|-----------|
| `code_analysis_requested` | Analysis job requests | Gateway | All 6 agents |
| `agent_results` | Agent verdicts | All agents | Orchestrator, Arbiter |
| `release_decisions` | Final decisions | Arbiter | Orchestrator |

---

## Environment Variables (Summary)

### Required
- `DATABASE_URL` - PostgreSQL connection string
- `REDIS_URL` - Redis connection string
- `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` - LLM provider

### Security
- `HMAC_SECRET_KEY` - Request signing
- `JWT_SECRET_KEY` - Token signing

### Optional
- `DEFAULT_LLM_PROVIDER` - openai or claude
- `AGENT_TIMEOUT_SECONDS` - Agent processing timeout
- `ARBITER_WAIT_TIMEOUT_SECONDS` - Arbiter aggregation timeout
- `ENABLE_TELEMETRY` - OpenTelemetry enable/disable

---

## Development Commands (Makefile)

```bash
make install     # Install Python dependencies
make dev         # Run all services locally (no Docker)
make up          # Start Docker Compose stack
make down        # Stop Docker Compose stack
make logs        # View logs from all services
make test        # Run tests (pytest)
make migrate     # Run database migrations
make clean       # Clean up containers and volumes
```

---

## Quick Reference

### Start Everything
```bash
docker-compose up -d
```

### View Logs
```bash
docker-compose logs -f gateway
```

### Submit Job
```bash
curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{"repo_name":"test","commit_hash":"abc",...}'
```

### Check Status
```bash
curl http://localhost:8000/api/v1/jobs/{job_id}
```

---

## Next Steps

1. ✅ Review file structure
2. ✅ Read README.md for overview
3. ✅ Follow QUICKSTART.md to run locally
4. ✅ Study ARCHITECTURE.md for deep dive
5. [ ] Customize for your use case
6. [ ] Deploy to production

---

**This file structure demonstrates a production-grade microservices architecture with proper separation of concerns!**
