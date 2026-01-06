"""
Release Arbiter Agent - Aggregates all agent results and makes final release decision.
"""
import asyncio
import logging
from typing import Dict, Any, List
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from shared.config import settings
from shared.message_bus import message_bus
from shared.models import AgentVerdict, ReleaseDecisionEvent, AgentResultEvent, ArbiterPayload

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ReleaseArbiterAgent:
    """Arbiter agent that aggregates results and makes final decision."""

    # Decision weights for each agent
    AGENT_WEIGHTS = {
        "security_agent": 0.35,
        "intent_agent": 0.25,
        "performance_agent": 0.20,
        "test_agent": 0.20,
        "diff_agent": 0.10,
    }

    # Expected agents (must receive results from all)
    EXPECTED_AGENTS = {"diff_agent", "intent_agent", "security_agent", "performance_agent", "test_agent"}

    def __init__(self):
        self.running = False
        self.job_results: Dict[str, List[AgentResultEvent]] = {}  # job_id -> results
        self.decision_tasks: Dict[str, asyncio.Task] = {}  # job_id -> task

    async def start(self):
        """Start the arbiter agent."""
        self.running = True
        logger.info("Starting Release Arbiter Agent")

        # Connect to message bus
        await message_bus.connect()

        # Start consuming agent results
        await self.consume_agent_results()

    async def stop(self):
        """Stop the arbiter agent."""
        self.running = False

        # Cancel all pending decision tasks
        for task in self.decision_tasks.values():
            task.cancel()

        await message_bus.disconnect()
        logger.info("Stopped Release Arbiter Agent")

    async def consume_agent_results(self):
        """Consume agent result events."""
        async def handler(data: Dict[str, Any]):
            """Handle agent result event."""
            try:
                job_id = data["job_id"]
                agent_name = data["agent_name"]

                logger.info(f"[Arbiter] Received result from {agent_name} for job {job_id}")

                # Parse agent result
                result = AgentResultEvent(
                    job_id=job_id,
                    agent_name=agent_name,
                    verdict=AgentVerdict(data["verdict"]),
                    confidence=data["confidence"],
                    payload=data["payload"],
                    timestamp=datetime.fromisoformat(data["timestamp"])
                )

                # Store result
                if job_id not in self.job_results:
                    self.job_results[job_id] = []

                self.job_results[job_id].append(result)

                # Check if we have all results
                received_agents = {r.agent_name for r in self.job_results[job_id]}

                if received_agents >= self.EXPECTED_AGENTS:
                    # All agents have reported, make decision immediately
                    if job_id not in self.decision_tasks:
                        logger.info(f"[Arbiter] All agents reported for job {job_id}, making decision")
                        await self.make_decision(job_id)
                elif job_id not in self.decision_tasks:
                    # Start timeout task if not already started
                    self.decision_tasks[job_id] = asyncio.create_task(
                        self.wait_and_decide(job_id)
                    )

            except Exception as e:
                logger.error(f"[Arbiter] Error handling agent result: {e}", exc_info=True)

        await message_bus.consume_stream(
            stream_name=message_bus.AGENT_RESULTS_STREAM,
            consumer_group="arbiter",
            consumer_name="arbiter_1",
            handler=handler
        )

    async def wait_and_decide(self, job_id: str):
        """Wait for timeout and then make decision with available results."""
        try:
            await asyncio.sleep(settings.arbiter_wait_timeout_seconds)

            logger.warning(f"[Arbiter] Timeout reached for job {job_id}, deciding with available results")
            await self.make_decision(job_id)

        except asyncio.CancelledError:
            logger.info(f"[Arbiter] Decision task cancelled for job {job_id}")

    async def make_decision(self, job_id: str):
        """Make final release decision based on all agent results."""
        try:
            results = self.job_results.get(job_id, [])

            if not results:
                logger.error(f"[Arbiter] No results available for job {job_id}")
                return

            # Calculate weighted score
            weighted_score = self._calculate_weighted_score(results)

            # Determine final verdict
            final_verdict = self._determine_final_verdict(results, weighted_score)

            # Generate explanation
            explanation = self._generate_explanation(results, weighted_score, final_verdict)

            # Identify blocking issues
            blocking_issues = self._identify_blocking_issues(results)

            # Build arbiter payload
            arbiter_payload = ArbiterPayload(
                weighted_score=weighted_score,
                agent_weights=self.AGENT_WEIGHTS,
                decision_matrix={
                    agent: {
                        "verdict": r.verdict.value,
                        "confidence": r.confidence,
                        "weight": self.AGENT_WEIGHTS.get(r.agent_name, 0.0)
                    }
                    for r in results
                    for agent in [r.agent_name]
                },
                blocking_issues=blocking_issues
            )

            # Publish decision
            decision_event = ReleaseDecisionEvent(
                job_id=job_id,
                decision=final_verdict,
                explanation=explanation,
                agent_results=results,
                timestamp=datetime.utcnow()
            )

            await message_bus.publish_release_decision(decision_event)

            logger.info(
                f"[Arbiter] Published decision for job {job_id}: "
                f"{final_verdict.value} (score: {weighted_score:.2f})"
            )

            # Cleanup
            if job_id in self.job_results:
                del self.job_results[job_id]
            if job_id in self.decision_tasks:
                del self.decision_tasks[job_id]

        except Exception as e:
            logger.error(f"[Arbiter] Error making decision for job {job_id}: {e}", exc_info=True)

    def _calculate_weighted_score(self, results: List[AgentResultEvent]) -> float:
        """Calculate weighted score based on agent verdicts and confidence."""
        total_score = 0.0
        total_weight = 0.0

        for result in results:
            weight = self.AGENT_WEIGHTS.get(result.agent_name, 0.0)

            # Convert verdict to score
            verdict_score = {
                AgentVerdict.APPROVE: 1.0,
                AgentVerdict.WARN: 0.5,
                AgentVerdict.REJECT: 0.0,
                AgentVerdict.SKIP: 0.5
            }.get(result.verdict, 0.5)

            # Weight by confidence
            weighted_verdict_score = verdict_score * result.confidence

            total_score += weighted_verdict_score * weight
            total_weight += weight

        return total_score / total_weight if total_weight > 0 else 0.5

    def _determine_final_verdict(
        self,
        results: List[AgentResultEvent],
        weighted_score: float
    ) -> AgentVerdict:
        """Determine final verdict based on results and score."""
        # Check for any REJECT verdicts from critical agents
        critical_agents = {"security_agent", "intent_agent"}
        for result in results:
            if result.agent_name in critical_agents and result.verdict == AgentVerdict.REJECT:
                return AgentVerdict.REJECT

        # Check weighted score
        if weighted_score < 0.4:
            return AgentVerdict.REJECT

        if weighted_score < 0.7:
            return AgentVerdict.WARN

        return AgentVerdict.APPROVE

    def _generate_explanation(
        self,
        results: List[AgentResultEvent],
        weighted_score: float,
        final_verdict: AgentVerdict
    ) -> str:
        """Generate human-readable explanation of the decision."""
        explanation_parts = [
            f"Release decision: {final_verdict.value.upper()}",
            f"Overall confidence score: {weighted_score:.2f}",
            "",
            "Agent Verdicts:"
        ]

        for result in results:
            explanation_parts.append(
                f"- {result.agent_name}: {result.verdict.value} "
                f"(confidence: {result.confidence:.2f})"
            )

        # Add key concerns
        warnings = [r for r in results if r.verdict in [AgentVerdict.WARN, AgentVerdict.REJECT]]
        if warnings:
            explanation_parts.append("")
            explanation_parts.append("Key Concerns:")
            for result in warnings:
                explanation_parts.append(f"- {result.agent_name}: {result.verdict.value}")

        return "\n".join(explanation_parts)

    def _identify_blocking_issues(self, results: List[AgentResultEvent]) -> List[str]:
        """Identify blocking issues from agent results."""
        blocking = []

        for result in results:
            if result.verdict == AgentVerdict.REJECT:
                blocking.append(f"{result.agent_name}: Critical issues detected")

        return blocking


arbiter = ReleaseArbiterAgent()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    asyncio.create_task(arbiter.start())
    logger.info("Release Arbiter Agent started")

    yield

    # Shutdown
    await arbiter.stop()
    logger.info("Release Arbiter Agent stopped")


app = FastAPI(
    title="Release Arbiter Agent",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "agent": "arbiter_agent"}


@app.get("/metrics")
async def metrics():
    """Metrics endpoint."""
    return {
        "pending_decisions": len(arbiter.job_results),
        "active_tasks": len(arbiter.decision_tasks)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.arbiter_agent_host,
        port=settings.arbiter_agent_port,
        log_level="info"
    )
