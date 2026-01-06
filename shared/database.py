"""
Database models and connection management.
"""
from sqlalchemy import Column, String, DateTime, JSON, Float, Enum as SQLEnum, ForeignKey, Integer
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from datetime import datetime
from uuid import uuid4
import enum

from .config import settings

Base = declarative_base()


# ============================================================================
# Database Models
# ============================================================================

class JobStatusEnum(str, enum.Enum):
    """Job status enum for database."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class VerdictEnum(str, enum.Enum):
    """Verdict enum for database."""
    APPROVE = "approve"
    REJECT = "reject"
    WARN = "warn"
    SKIP = "skip"


class AnalysisJob(Base):
    """Analysis job table."""
    __tablename__ = "analysis_jobs"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    repo_name = Column(String, nullable=False, index=True)
    commit_hash = Column(String, nullable=False, index=True)
    commit_message = Column(String, nullable=False)
    branch = Column(String, nullable=False)
    author = Column(String, nullable=False)
    status = Column(SQLEnum(JobStatusEnum), nullable=False, default=JobStatusEnum.PENDING)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    agent_results = relationship("AgentResult", back_populates="job", cascade="all, delete-orphan")
    release_decision = relationship("ReleaseDecision", back_populates="job", uselist=False, cascade="all, delete-orphan")


class AgentResult(Base):
    """Agent results table."""
    __tablename__ = "agent_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(PGUUID(as_uuid=True), ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_name = Column(String, nullable=False, index=True)
    verdict = Column(SQLEnum(VerdictEnum), nullable=False)
    confidence = Column(Float, nullable=False)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    job = relationship("AnalysisJob", back_populates="agent_results")


class ReleaseDecision(Base):
    """Release decisions table."""
    __tablename__ = "release_decisions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(PGUUID(as_uuid=True), ForeignKey("analysis_jobs.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    decision = Column(SQLEnum(VerdictEnum), nullable=False)
    explanation = Column(String, nullable=False)
    agent_results_summary = Column(JSON, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    job = relationship("AnalysisJob", back_populates="release_decision")


# ============================================================================
# Database Connection
# ============================================================================

class Database:
    """Database connection manager."""

    def __init__(self):
        self.engine = create_async_engine(
            settings.database_url,
            echo=False,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20
        )
        self.async_session = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

    async def get_session(self) -> AsyncSession:
        """Get database session."""
        async with self.async_session() as session:
            yield session

    async def create_tables(self):
        """Create all tables."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def drop_tables(self):
        """Drop all tables (use with caution)."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    async def close(self):
        """Close database connections."""
        await self.engine.dispose()


# Global database instance
db = Database()
