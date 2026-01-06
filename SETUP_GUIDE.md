# Complete Setup Guide

## Installation Options

### Option 1: Docker Compose (Recommended for Development)

```bash
# 1. Clone repository
git clone https://github.com/your-org/ci-intelligence.git
cd ci-intelligence

# 2. Configure environment
cp .env.example .env
nano .env  # Add your API keys

# 3. Start services
docker-compose up -d

# 4. Verify
curl http://localhost:8000/health
```

### Option 2: Manual Installation (Development)

```bash
# 1. Prerequisites
# - Python 3.11+
# - PostgreSQL 15+
# - Redis 7+

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Set environment variables
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/ci_intelligence"
export REDIS_URL="redis://localhost:6379/0"
export OPENAI_API_KEY="sk-your-key"

# 4. Initialize database
alembic upgrade head

# 5. Start services (each in separate terminal)
python gateway/main.py
python orchestrator/main.py
python agents/diff_agent/main.py
python agents/intent_agent/main.py
python agents/security_agent/main.py
python agents/performance_agent/main.py
python agents/test_agent/main.py
python agents/arbiter_agent/main.py
```

### Option 3: Kubernetes (Production)

```bash
# 1. Create namespace
kubectl apply -f infra/k8s/namespace.yaml

# 2. Create secrets
kubectl create secret generic ci-intelligence-secrets \
  --from-literal=OPENAI_API_KEY=sk-your-key \
  --from-literal=HMAC_SECRET_KEY=your-secret \
  -n ci-intelligence

# 3. Apply configurations
kubectl apply -f infra/k8s/configmap.yaml
kubectl apply -f infra/k8s/gateway-deployment.yaml
kubectl apply -f infra/k8s/agents-deployment.yaml

# 4. Verify deployment
kubectl get pods -n ci-intelligence
kubectl get svc -n ci-intelligence
```

---

## Configuration Guide

### Required Environment Variables

```bash
# Database
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/ci_intelligence

# Redis
REDIS_URL=redis://localhost:6379/0

# LLM Provider (choose one or both)
OPENAI_API_KEY=sk-...              # For GPT-4
ANTHROPIC_API_KEY=sk-ant-...       # For Claude
DEFAULT_LLM_PROVIDER=openai        # or "claude"

# Security
HMAC_SECRET_KEY=change-me-in-production
JWT_SECRET_KEY=change-me-in-production

# Agent Configuration
AGENT_TIMEOUT_SECONDS=300
ARBITER_WAIT_TIMEOUT_SECONDS=600
MAX_RETRIES=3
```

### Optional Environment Variables

```bash
# Observability
ENABLE_TELEMETRY=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
PROMETHEUS_PORT=9090

# Service Ports
GATEWAY_PORT=8000
ORCHESTRATOR_PORT=8001
DIFF_AGENT_PORT=8100
INTENT_AGENT_PORT=8101
SECURITY_AGENT_PORT=8102
PERFORMANCE_AGENT_PORT=8103
TEST_AGENT_PORT=8104
ARBITER_AGENT_PORT=8105
```

---

## Database Setup

### Automatic (with Docker Compose)

Database is automatically created and migrated when you run `docker-compose up`.

### Manual Setup

```bash
# 1. Create database
psql -U postgres
CREATE DATABASE ci_intelligence;
\q

# 2. Run migrations
export DATABASE_URL="postgresql+asyncpg://postgres:postgres@localhost:5432/ci_intelligence"
alembic upgrade head

# 3. Verify tables
psql -U postgres -d ci_intelligence -c "\dt"
```

### Database Schema

The system creates 3 main tables:

1. **analysis_jobs** - Stores job metadata
2. **agent_results** - Stores individual agent verdicts
3. **release_decisions** - Stores final arbiter decisions

---

## Redis Setup

### Using Docker

```bash
docker run -d -p 6379:6379 redis:7-alpine
```

### Using Package Manager

```bash
# Ubuntu/Debian
sudo apt install redis-server
sudo systemctl start redis

# macOS
brew install redis
brew services start redis
```

### Verify Redis

```bash
redis-cli ping
# Should return: PONG
```

---

## LLM Provider Setup

### OpenAI

1. Sign up at https://platform.openai.com/
2. Create API key
3. Add to `.env`: `OPENAI_API_KEY=sk-your-key`
4. Set default provider: `DEFAULT_LLM_PROVIDER=openai`

### Anthropic Claude

1. Sign up at https://console.anthropic.com/
2. Create API key
3. Add to `.env`: `ANTHROPIC_API_KEY=sk-ant-your-key`
4. Set default provider: `DEFAULT_LLM_PROVIDER=claude`

### Using Both (Recommended)

```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
DEFAULT_LLM_PROVIDER=openai  # Primary
```

The system will automatically fallback to the other provider if the primary fails.

---

## Verification Steps

### 1. Check Service Health

```bash
# Gateway
curl http://localhost:8000/health
# Expected: {"status":"healthy","service":"gateway"}

# Orchestrator
curl http://localhost:8001/health
# Expected: {"status":"healthy","service":"orchestrator"}

# Each Agent
curl http://localhost:8100/health  # diff_agent
curl http://localhost:8101/health  # intent_agent
curl http://localhost:8102/health  # security_agent
curl http://localhost:8103/health  # performance_agent
curl http://localhost:8104/health  # test_agent
curl http://localhost:8105/health  # arbiter_agent
```

### 2. Check Database Connection

```bash
docker-compose exec gateway python -c "
from shared.database import db
import asyncio
async def test():
    await db.create_tables()
    print('✅ Database connected and tables created')
asyncio.run(test())
"
```

### 3. Check Redis Connection

```bash
docker-compose exec gateway python -c "
from shared.message_bus import message_bus
import asyncio
async def test():
    await message_bus.connect()
    print('✅ Redis connected')
    await message_bus.disconnect()
asyncio.run(test())
"
```

### 4. Submit Test Job

```bash
# Save as test_analysis.sh
#!/bin/bash

DIFF='diff --git a/test.py b/test.py
index abc..def 100644
--- a/test.py
+++ b/test.py
@@ -1,3 +1,4 @@
 def hello():
-    pass
+    print("Hello World")
+    return True
'

curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -H "X-Signature: test" \
  -H "X-Timestamp: $(date +%s)" \
  -d "{
    \"repo_name\": \"test/repo\",
    \"commit_hash\": \"test123\",
    \"commit_message\": \"Add hello function\",
    \"diff\": $(echo "$DIFF" | jq -Rs .),
    \"branch\": \"main\",
    \"author\": \"tester\"
  }"

# Save the job_id from response
# Then check status:
# curl http://localhost:8000/api/v1/jobs/{job_id}
```

---

## Troubleshooting

### Problem: Services won't start

**Check Docker logs:**
```bash
docker-compose logs gateway
docker-compose logs orchestrator
```

**Common causes:**
- Port already in use
- Missing environment variables
- Database not accessible

**Solution:**
```bash
# Stop conflicting services
sudo lsof -i :8000  # Find process on port 8000
sudo kill -9 <PID>

# Restart services
docker-compose down
docker-compose up -d
```

### Problem: Database connection errors

**Check PostgreSQL:**
```bash
docker-compose ps postgres
docker-compose logs postgres
```

**Test connection:**
```bash
docker-compose exec postgres psql -U postgres -c "SELECT 1"
```

**Solution:**
```bash
# Restart PostgreSQL
docker-compose restart postgres

# Recreate database
docker-compose down -v
docker-compose up -d
```

### Problem: Agents not processing jobs

**Check Redis:**
```bash
docker-compose ps redis
docker-compose logs redis
```

**Check consumer groups:**
```bash
docker-compose exec redis redis-cli XINFO GROUPS code_analysis_requested
```

**Solution:**
```bash
# Restart agents
docker-compose restart diff-agent intent-agent security-agent

# Clear Redis (development only)
docker-compose exec redis redis-cli FLUSHALL
```

### Problem: LLM API errors

**Check API key:**
```bash
docker-compose exec intent-agent env | grep API_KEY
```

**Test API directly:**
```bash
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

**Solution:**
- Verify API key is correct
- Check API rate limits
- Try fallback provider

### Problem: High latency

**Check metrics:**
```bash
curl http://localhost:8001/metrics
```

**Check Redis queue depth:**
```bash
docker-compose exec redis redis-cli XLEN code_analysis_requested
docker-compose exec redis redis-cli XLEN agent_results
```

**Solution:**
- Scale up agents: `docker-compose up -d --scale intent-agent=3`
- Increase timeouts in `.env`
- Check LLM API response times

---

## Performance Tuning

### For Development

```bash
# Reduce replicas
# In docker-compose.yml, use 1 replica per agent

# Reduce timeouts
AGENT_TIMEOUT_SECONDS=60
ARBITER_WAIT_TIMEOUT_SECONDS=120
```

### For Production

```bash
# Increase replicas in Kubernetes
kubectl scale deployment security-agent --replicas=5 -n ci-intelligence

# Increase database pool size
# In shared/database.py:
# pool_size=20, max_overflow=40

# Enable Redis persistence
# In docker-compose.yml:
# redis:
#   command: redis-server --appendonly yes
```

---

## Monitoring Setup

### Prometheus + Grafana

```bash
# Add to docker-compose.yml
services:
  prometheus:
    image: prom/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./infra/prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin

# Access:
# Prometheus: http://localhost:9090
# Grafana: http://localhost:3000 (admin/admin)
```

---

## Security Hardening

### Production Checklist

- [ ] Change `HMAC_SECRET_KEY` to strong random value
- [ ] Change `JWT_SECRET_KEY` to strong random value
- [ ] Enable HTTPS/TLS for all services
- [ ] Use managed PostgreSQL (RDS, Cloud SQL)
- [ ] Use managed Redis (ElastiCache, MemoryStore)
- [ ] Implement rate limiting on gateway
- [ ] Enable database encryption at rest
- [ ] Set up network policies (Kubernetes)
- [ ] Implement audit logging
- [ ] Regular security scanning (Trivy, Snyk)

### Generate Secure Keys

```bash
# HMAC Secret
python -c "import secrets; print(secrets.token_urlsafe(32))"

# JWT Secret
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## Backup & Recovery

### Database Backup

```bash
# Backup
docker-compose exec postgres pg_dump -U postgres ci_intelligence > backup.sql

# Restore
docker-compose exec -T postgres psql -U postgres ci_intelligence < backup.sql
```

### Redis Backup

```bash
# Trigger save
docker-compose exec redis redis-cli SAVE

# Copy RDB file
docker cp <container_id>:/data/dump.rdb ./redis_backup.rdb
```

---

## Upgrading

### Update Code

```bash
git pull origin main
docker-compose build
docker-compose up -d
```

### Database Migration

```bash
# Generate migration
alembic revision --autogenerate -m "description"

# Apply migration
alembic upgrade head

# Or with Docker:
docker-compose exec gateway alembic upgrade head
```

---

## Getting Help

- **Documentation**: [README.md](README.md), [ARCHITECTURE.md](ARCHITECTURE.md)
- **Quick Start**: [QUICKSTART.md](QUICKSTART.md)
- **GitHub Issues**: https://github.com/your-org/ci-intelligence/issues
- **Email**: support@ci-intelligence.dev

---

## Next Steps

1. ✅ Complete setup
2. ✅ Verify all services
3. ✅ Submit test job
4. ✅ Review results
5. [ ] Integrate with CI/CD (see [GitHub Actions example](.github/workflows/ci-intelligence-check.yml))
6. [ ] Customize agent weights
7. [ ] Set up monitoring
8. [ ] Deploy to production

---

**Need help? Open an issue or contact support!**
