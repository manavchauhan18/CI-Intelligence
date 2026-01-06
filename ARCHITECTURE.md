# Architecture Documentation

## System Overview

The CI Intelligence Platform is a production-grade Agent-to-Agent (A2A) system designed to validate code changes before deployment through autonomous agent collaboration.

## Design Principles

### 1. Agent Autonomy
Each agent operates independently without direct knowledge of other agents. Agents:
- Subscribe to event streams
- Process messages at their own pace
- Publish results independently
- Can fail without affecting other agents

### 2. Event-Driven Communication
- **Asynchronous**: No blocking between agents
- **Reliable**: Redis Streams with consumer groups
- **Scalable**: Agents can be scaled independently
- **Fault-tolerant**: Message replay on failure

### 3. Separation of Concerns
- **Gateway**: Entry point, authentication, job creation
- **Orchestrator**: Job lifecycle tracking, database updates
- **Agents**: Specialized analysis (diff, intent, security, etc.)
- **Arbiter**: Result aggregation and decision making

## Data Flow

```
1. CI Pipeline → Gateway (HTTP POST)
   └─> Creates job in PostgreSQL
   └─> Publishes to code_analysis_requested stream

2. All Agents consume → code_analysis_requested
   └─> Diff Agent: Parses diff, categorizes changes
   └─> Intent Agent: LLM validates commit intent
   └─> Security Agent: Scans for vulnerabilities
   └─> Performance Agent: Detects anti-patterns
   └─> Test Agent: Analyzes coverage
   └─> Each publishes to → agent_results stream

3. Orchestrator consumes → agent_results
   └─> Updates database with agent results
   └─> Sets job status to "processing"

4. Arbiter consumes → agent_results
   └─> Waits for all agents (or timeout)
   └─> Calculates weighted score
   └─> Makes final decision
   └─> Publishes to → release_decisions stream

5. Orchestrator consumes → release_decisions
   └─> Updates job to "completed"
   └─> Stores final decision

6. CI Pipeline polls → GET /api/v1/jobs/{job_id}
   └─> Retrieves decision
   └─> Proceeds or blocks deployment
```

## Agent Design Pattern

All agents follow this pattern:

```python
class MyAgent(BaseAgent):
    def __init__(self):
        super().__init__("my_agent")

    async def analyze(self, data: Dict) -> Tuple[AgentVerdict, float, Dict]:
        # 1. Extract relevant data
        diff = data.get("diff")

        # 2. Perform analysis (rules, LLM, etc.)
        issues = self._detect_issues(diff)

        # 3. Determine verdict
        verdict = self._determine_verdict(issues)

        # 4. Calculate confidence
        confidence = self._calculate_confidence(issues)

        # 5. Build payload
        payload = {"issues": issues}

        return verdict, confidence, payload
```

## Decision Algorithm (Arbiter)

The arbiter uses a weighted scoring system:

```
weighted_score = Σ (verdict_score × confidence × agent_weight)

where:
  verdict_score: APPROVE=1.0, WARN=0.5, REJECT=0.0
  confidence: 0.0 to 1.0 (from agent)
  agent_weight: configured per agent

Agent Weights:
  - security_agent: 0.35 (highest priority)
  - intent_agent: 0.25
  - performance_agent: 0.20
  - test_agent: 0.20
  - diff_agent: 0.10

Final Decision:
  - REJECT if: security/intent rejects OR score < 0.4
  - WARN if: score < 0.7
  - APPROVE if: score >= 0.7
```

## Scalability Strategy

### Horizontal Scaling

1. **Agents**: Scale each agent type independently
   ```bash
   kubectl scale deployment security-agent --replicas=5
   ```

2. **Consumer Groups**: Each agent type has its own consumer group
   - Multiple instances share the workload
   - Redis Streams ensure each message processed once

3. **Stateless Services**: All services are stateless
   - Can be killed/restarted without data loss
   - State stored in PostgreSQL and Redis

### Vertical Scaling

- Gateway/Orchestrator: CPU-bound (request handling)
- LLM Agents (Intent, Security, Performance): Memory-bound (API calls)
- Diff/Test Agents: CPU-bound (parsing)

## Failure Handling

### Agent Failure

- Agent crashes → Message not acknowledged → Redis redelivers
- Agent timeout → Arbiter proceeds with partial results
- Consumer lag → Orchestrator can claim old messages

### Database Failure

- Gateway: Returns 503, CI retries
- Orchestrator: Messages queue up in Redis
- Recovery: Replay pending messages

### Redis Failure

- Services log error and retry with backoff
- Messages may be lost (acceptable for analysis jobs)
- Alternative: Add backup message queue (RabbitMQ)

### LLM Provider Failure

- LLM client automatically falls back to alternative provider
- If all fail, agent returns low-confidence approval

## Security Considerations

### Authentication

- HMAC-based request signing (prevents replay attacks)
- Timestamp validation (5-minute window)
- JWT for future user authentication

### Data Isolation

- Each analysis job isolated in database
- No cross-job data leakage
- Diff data not stored permanently (privacy)

### Agent Sandboxing

- Agents have read-only access to diff data
- No file system access
- No network access except to LLM APIs

## Performance Optimization

### Caching

- LLM responses cached in Redis (15 minutes)
- Common patterns pre-compiled (regex)

### Batching

- Redis Streams batch reads (up to 10 messages)
- Database batch inserts for agent results

### Timeouts

- Agent timeout: 5 minutes (configurable)
- Arbiter timeout: 10 minutes (configurable)
- LLM timeout: 30 seconds with retry

## Observability

### Metrics

- Job throughput (jobs/minute)
- Agent latency (processing time)
- Verdict distribution (approve/warn/reject)
- Error rates per agent

### Logging

- Structured JSON logging
- Correlation IDs (job_id) across services
- Log levels: DEBUG, INFO, WARN, ERROR

### Tracing

- OpenTelemetry for distributed tracing
- Trace job from gateway → agents → arbiter
- Identify bottlenecks

## Future Enhancements

1. **Learning-based Weights**: Adjust agent weights based on historical accuracy
2. **Feedback Loop**: Allow developers to challenge decisions, train models
3. **Cross-repo Intelligence**: Learn patterns across repositories
4. **Self-improving Prompts**: A/B test and optimize LLM prompts
5. **Cost Optimization**: Use cheaper models for simple cases
6. **Multi-tenancy**: Support multiple organizations
7. **Audit Trails**: Compliance-ready decision logs

## Technology Choices

### Why Redis Streams?

- Native consumer groups (vs Pub/Sub)
- Message persistence and replay
- Simpler than Kafka for this scale
- Excellent Python support

### Why PostgreSQL?

- ACID compliance for audit trails
- JSONB for flexible agent payloads
- Mature ecosystem
- Easy to replicate

### Why FastAPI?

- Async/await support (concurrent requests)
- Auto-generated OpenAPI docs
- Type hints for validation
- High performance

### Why LLMs?

- Complex intent analysis beyond rules
- Natural language understanding
- Contextual security analysis
- Continuous improvement via prompt tuning

## Deployment Patterns

### Development

```
docker-compose up
```

### Staging

- Kubernetes cluster (3 nodes)
- Single replica per agent
- Shared PostgreSQL (managed)
- Shared Redis (managed)

### Production

- Kubernetes cluster (10+ nodes)
- Multiple replicas per agent
- PostgreSQL cluster (primary + replicas)
- Redis Cluster (sharded)
- Load balancer for Gateway
- CDN for static assets

## Cost Estimation

**AWS (us-east-1) for 1000 jobs/day:**

- EKS Cluster: ~$75/month
- EC2 instances (t3.medium × 5): ~$180/month
- RDS PostgreSQL (db.t3.medium): ~$75/month
- ElastiCache Redis (cache.t3.medium): ~$50/month
- LLM API calls (OpenAI): ~$100/month
- Total: **~$480/month**

## Conclusion

This architecture prioritizes:
✅ **Reliability**: Fault-tolerant, message replay
✅ **Scalability**: Horizontal scaling, stateless
✅ **Maintainability**: Clean separation, standard patterns
✅ **Observability**: Metrics, logs, traces
✅ **Security**: Authentication, isolation, audit trails

The A2A design enables true agent autonomy while maintaining system coherence through event-driven communication.
