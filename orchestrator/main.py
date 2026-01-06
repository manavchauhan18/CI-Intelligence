"""
Agent Orchestrator - Tracks agent lifecycle and job status.
"""
import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.config import settings
from shared.database import db, AnalysisJob, AgentResult, ReleaseDecision, JobStatusEnum, VerdictEnum
from shared.message_bus import message_bus
from shared.models import AgentVerdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Orchestrator:
    """Orchestrator manages agent lifecycle and job status updates."""

    def __init__(self):
        self.running = False

    async def start(self):
        """Start orchestrator services."""
        self.running = True

        # Start consuming agent results
        asyncio.create_task(self.consume_agent_results())

        # Start consuming release decisions
        asyncio.create_task(self.consume_release_decisions())

        logger.info("Orchestrator started")

    async def stop(self):
        """Stop orchestrator services."""
        self.running = False
        logger.info("Orchestrator stopped")

    async def consume_agent_results(self):
        """Consume agent result events and update job status."""
        async def handle_agent_result(data: dict):
            """Handle agent result event."""
            try:
                job_id = data["job_id"]
                agent_name = data["agent_name"]
                verdict = data["verdict"]
                confidence = data["confidence"]
                payload = data["payload"]

                logger.info(f"Received result from {agent_name} for job {job_id}: {verdict}")

                # Save to database
                async for session in db.get_session():
                    # Create agent result
                    agent_result = AgentResult(
                        job_id=job_id,
                        agent_name=agent_name,
                        verdict=VerdictEnum(verdict),
                        confidence=confidence,
                        payload=payload
                    )
                    session.add(agent_result)

                    # Update job status to processing
                    await session.execute(
                        update(AnalysisJob)
                        .where(AnalysisJob.id == job_id)
                        .values(status=JobStatusEnum.PROCESSING)
                    )

                    await session.commit()
                    logger.info(f"Saved result from {agent_name} for job {job_id}")

            except Exception as e:
                logger.error(f"Error handling agent result: {e}", exc_info=True)

        await message_bus.consume_stream(
            stream_name=message_bus.AGENT_RESULTS_STREAM,
            consumer_group="orchestrator",
            consumer_name="orchestrator-1",
            handler=handle_agent_result
        )

    async def consume_release_decisions(self):
        """Consume release decision events and finalize jobs."""
        async def handle_release_decision(data: dict):
            """Handle release decision event."""
            try:
                job_id = data["job_id"]
                decision = data["decision"]
                explanation = data["explanation"]
                agent_results = data["agent_results"]

                logger.info(f"Received release decision for job {job_id}: {decision}")

                # Save to database
                async for session in db.get_session():
                    # Create release decision
                    release_decision = ReleaseDecision(
                        job_id=job_id,
                        decision=VerdictEnum(decision),
                        explanation=explanation,
                        agent_results_summary=agent_results
                    )
                    session.add(release_decision)

                    # Update job to completed
                    from datetime import datetime
                    await session.execute(
                        update(AnalysisJob)
                        .where(AnalysisJob.id == job_id)
                        .values(
                            status=JobStatusEnum.COMPLETED,
                            completed_at=datetime.utcnow()
                        )
                    )

                    await session.commit()
                    logger.info(f"Finalized job {job_id} with decision: {decision}")

            except Exception as e:
                logger.error(f"Error handling release decision: {e}", exc_info=True)

        await message_bus.consume_stream(
            stream_name=message_bus.RELEASE_DECISION_STREAM,
            consumer_group="orchestrator",
            consumer_name="orchestrator-1",
            handler=handle_release_decision
        )


orchestrator = Orchestrator()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    await db.create_tables()
    await message_bus.connect()
    await orchestrator.start()
    logger.info("Orchestrator service started")

    yield

    # Shutdown
    await orchestrator.stop()
    await message_bus.disconnect()
    await db.close()
    logger.info("Orchestrator service shut down")


app = FastAPI(
    title="CI Intelligence Orchestrator",
    description="Agent Orchestrator for Multi-Agent CI/CD Intelligence Platform",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "orchestrator"}


@app.get("/metrics")
async def metrics():
    """Basic metrics endpoint."""
    # Get pending messages count
    code_analysis_pending = await message_bus.get_pending_messages(
        message_bus.CODE_ANALYSIS_STREAM,
        "diff_agent"
    )

    agent_results_pending = await message_bus.get_pending_messages(
        message_bus.AGENT_RESULTS_STREAM,
        "orchestrator"
    )

    return {
        "code_analysis_pending": code_analysis_pending,
        "agent_results_pending": agent_results_pending,
        "orchestrator_running": orchestrator.running
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.orchestrator_host,
        port=settings.orchestrator_port,
        log_level="info"
    )
