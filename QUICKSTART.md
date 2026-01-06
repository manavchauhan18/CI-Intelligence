# Quick Start Guide

Get the CI Intelligence Platform running in 5 minutes.

## Prerequisites

- Docker and Docker Compose installed
- Git
- OpenAI or Anthropic API key

## Step 1: Clone and Configure

```bash
# Clone the repository
git clone https://github.com/your-org/ci-intelligence.git
cd ci-intelligence

# Copy environment template
cp .env.example .env

# Edit .env and add your API key
nano .env
# Add: OPENAI_API_KEY=sk-your-key-here
```

## Step 2: Start Services

```bash
# Start all services with Docker Compose
docker-compose up -d

# Verify services are running
docker-compose ps

# Check logs
docker-compose logs -f gateway
```

## Step 3: Test the System

### Create a test diff file

```bash
cat > test_diff.txt << 'EOF'
diff --git a/auth.py b/auth.py
index abc123..def456 100644
--- a/auth.py
+++ b/auth.py
@@ -10,7 +10,8 @@ def login(username, password):
-    query = f"SELECT * FROM users WHERE username = '{username}'"
+    query = "SELECT * FROM users WHERE username = %s"
+    cursor.execute(query, (username,))
-    cursor.execute(query)
EOF
```

### Submit analysis job

```bash
DIFF=$(cat test_diff.txt | jq -Rs .)

curl -X POST http://localhost:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -H "X-Signature: test-signature" \
  -H "X-Timestamp: $(date +%s)" \
  -d "{
    \"repo_name\": \"test/repo\",
    \"commit_hash\": \"abc123\",
    \"commit_message\": \"Fix SQL injection vulnerability\",
    \"diff\": $DIFF,
    \"branch\": \"main\",
    \"author\": \"developer\"
  }"
```

### Check job status

```bash
# Copy the job_id from the response above
JOB_ID="<paste-job-id-here>"

# Poll for results
curl http://localhost:8000/api/v1/jobs/$JOB_ID | jq
```

## Expected Result

You should see output like:

```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "decision": "approve",
  "explanation": "Release decision: APPROVE\nOverall confidence score: 0.85\n\nAgent Verdicts:\n- diff_agent: approve (confidence: 0.85)\n- intent_agent: approve (confidence: 0.90)\n- security_agent: approve (confidence: 0.95)\n- performance_agent: approve (confidence: 0.75)\n- test_agent: warn (confidence: 0.70)",
  "created_at": "2025-01-06T12:00:00Z",
  "completed_at": "2025-01-06T12:00:30Z"
}
```

## Step 4: Integrate with CI/CD

### GitHub Actions

```yaml
# .github/workflows/ci-check.yml
name: CI Intelligence Check

on: [push, pull_request]

jobs:
  analyze:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Get diff
        id: diff
        run: |
          DIFF=$(git diff HEAD~1 HEAD)
          echo "diff=$(echo "$DIFF" | jq -Rs .)" >> $GITHUB_OUTPUT

      - name: Submit to CI Intelligence
        run: |
          curl -X POST ${{ secrets.CI_INTELLIGENCE_URL }}/api/v1/analyze \
            -H "Content-Type: application/json" \
            -d "{
              \"repo_name\": \"${{ github.repository }}\",
              \"commit_hash\": \"${{ github.sha }}\",
              \"commit_message\": \"${{ github.event.head_commit.message }}\",
              \"diff\": ${{ steps.diff.outputs.diff }},
              \"branch\": \"${{ github.ref_name }}\",
              \"author\": \"${{ github.actor }}\"
            }"
```

## Troubleshooting

### Services not starting

```bash
# Check logs
docker-compose logs

# Restart a specific service
docker-compose restart gateway
```

### Database connection errors

```bash
# Verify PostgreSQL is running
docker-compose ps postgres

# Check database logs
docker-compose logs postgres
```

### LLM agents failing

```bash
# Verify API key is set
docker-compose exec intent-agent env | grep API_KEY

# Check agent logs
docker-compose logs intent-agent
```

### Redis connection errors

```bash
# Verify Redis is running
docker-compose ps redis

# Test Redis connection
docker-compose exec redis redis-cli ping
```

## Next Steps

1. Read the [README.md](README.md) for full documentation
2. Review [ARCHITECTURE.md](ARCHITECTURE.md) for system design
3. Customize agent weights in `agents/arbiter_agent/main.py`
4. Set up monitoring with Prometheus/Grafana
5. Deploy to production with Kubernetes

## Stopping Services

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (clean slate)
docker-compose down -v
```

## Getting Help

- GitHub Issues: https://github.com/your-org/ci-intelligence/issues
- Documentation: https://docs.ci-intelligence.dev
- Email: support@ci-intelligence.dev

Happy analyzing! 🚀
