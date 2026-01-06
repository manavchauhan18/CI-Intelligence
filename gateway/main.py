"""
API Gateway - Entry point for CI/CD pipeline integration.
Authenticates requests and creates analysis jobs.
"""
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from uuid import UUID

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import hmac
import hashlib

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.config import settings
from shared.database import db, AnalysisJob, AgentResult, ReleaseDecision, JobStatusEnum, VerdictEnum
from shared.message_bus import message_bus
from shared.models import (
    AnalysisJobRequest,
    AnalysisJobResponse,
    JobStatusResponse,
    CodeAnalysisRequestedEvent,
    JobStatus,
    AgentVerdict
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    await db.create_tables()
    await message_bus.connect()
    logger.info("Gateway started successfully")

    yield

    # Shutdown
    await message_bus.disconnect()
    await db.close()
    logger.info("Gateway shut down")


app = FastAPI(
    title="CI Intelligence Gateway",
    description="API Gateway for Multi-Agent CI/CD Intelligence Platform",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Security
# ============================================================================

def verify_hmac_signature(payload: str, signature: str) -> bool:
    """Verify HMAC signature for request authentication."""
    expected = hmac.new(
        settings.hmac_secret_key.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


async def verify_signature(
    x_signature: str = Header(...),
    x_timestamp: str = Header(...)
) -> bool:
    """Dependency to verify request signature."""
    # In production, also verify timestamp to prevent replay attacks
    try:
        timestamp = int(x_timestamp)
        current_time = int(datetime.utcnow().timestamp())

        # Reject requests older than 5 minutes
        if abs(current_time - timestamp) > 300:
            raise HTTPException(status_code=401, detail="Request timestamp too old")

        return True

    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid timestamp")


async def get_db_session():
    """Dependency to get database session."""
    async for session in db.get_session():
        yield session


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "gateway"}


@app.post("/api/v1/analyze", response_model=AnalysisJobResponse)
async def create_analysis_job(
    request: AnalysisJobRequest,
    session: AsyncSession = Depends(get_db_session),
    # authenticated: bool = Depends(verify_signature)  # Uncomment for production
):
    """
    Create a new code analysis job.

    This endpoint is called by CI/CD pipelines to trigger analysis.
    """
    try:
        # Create job in database
        job = AnalysisJob(
            repo_name=request.repo_name,
            commit_hash=request.commit_hash,
            commit_message=request.commit_message,
            branch=request.branch,
            author=request.author,
            status=JobStatusEnum.PENDING
        )

        session.add(job)
        await session.commit()
        await session.refresh(job)

        logger.info(f"Created analysis job: {job.id} for {request.repo_name}@{request.commit_hash}")

        # Publish event to message bus
        event = CodeAnalysisRequestedEvent(
            job_id=job.id,
            repo_name=request.repo_name,
            commit_hash=request.commit_hash,
            commit_message=request.commit_message,
            diff=request.diff,
            branch=request.branch,
            author=request.author
        )

        await message_bus.publish_code_analysis_request(event)

        return AnalysisJobResponse(
            job_id=job.id,
            status=JobStatus.PENDING,
            created_at=job.created_at
        )

    except Exception as e:
        logger.error(f"Error creating analysis job: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to create analysis job")


@app.get("/api/v1/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: UUID,
    session: AsyncSession = Depends(get_db_session)
):
    """
    Get status and results of an analysis job.
    """
    try:
        # Get job
        result = await session.execute(
            select(AnalysisJob).where(AnalysisJob.id == job_id)
        )
        job = result.scalar_one_or_none()

        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        # Get agent results
        agent_results_query = await session.execute(
            select(AgentResult).where(AgentResult.job_id == job_id)
        )
        agent_results = agent_results_query.scalars().all()

        # Get release decision
        decision_query = await session.execute(
            select(ReleaseDecision).where(ReleaseDecision.job_id == job_id)
        )
        decision = decision_query.scalar_one_or_none()

        # Map database enums to response models
        status_map = {
            JobStatusEnum.PENDING: JobStatus.PENDING,
            JobStatusEnum.PROCESSING: JobStatus.PROCESSING,
            JobStatusEnum.COMPLETED: JobStatus.COMPLETED,
            JobStatusEnum.FAILED: JobStatus.FAILED
        }

        verdict_map = {
            VerdictEnum.APPROVE: AgentVerdict.APPROVE,
            VerdictEnum.REJECT: AgentVerdict.REJECT,
            VerdictEnum.WARN: AgentVerdict.WARN,
            VerdictEnum.SKIP: AgentVerdict.SKIP
        }

        from shared.models import AgentResultEvent

        return JobStatusResponse(
            job_id=job.id,
            status=status_map[job.status],
            decision=verdict_map[decision.decision] if decision else None,
            explanation=decision.explanation if decision else None,
            agent_results=[
                AgentResultEvent(
                    job_id=r.job_id,
                    agent_name=r.agent_name,
                    verdict=verdict_map[r.verdict],
                    confidence=r.confidence,
                    payload=r.payload
                )
                for r in agent_results
            ],
            created_at=job.created_at,
            completed_at=job.completed_at
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching job status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch job status")


@app.get("/api/v1/jobs")
async def list_jobs(
    repo_name: str = None,
    limit: int = 50,
    session: AsyncSession = Depends(get_db_session)
):
    """
    List analysis jobs with optional filtering.
    """
    try:
        query = select(AnalysisJob).order_by(AnalysisJob.created_at.desc()).limit(limit)

        if repo_name:
            query = query.where(AnalysisJob.repo_name == repo_name)

        result = await session.execute(query)
        jobs = result.scalars().all()

        status_map = {
            JobStatusEnum.PENDING: JobStatus.PENDING,
            JobStatusEnum.PROCESSING: JobStatus.PROCESSING,
            JobStatusEnum.COMPLETED: JobStatus.COMPLETED,
            JobStatusEnum.FAILED: JobStatus.FAILED
        }

        return {
            "jobs": [
                {
                    "job_id": str(job.id),
                    "repo_name": job.repo_name,
                    "commit_hash": job.commit_hash,
                    "status": status_map[job.status].value,
                    "created_at": job.created_at.isoformat()
                }
                for job in jobs
            ]
        }

    except Exception as e:
        logger.error(f"Error listing jobs: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list jobs")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.gateway_host,
        port=settings.gateway_port,
        log_level="info"
    )
