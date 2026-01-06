"""
Diff Analysis Agent - Parses git diffs and categorizes changes.
"""
import re
import logging
from typing import Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.base_agent import BaseAgent
from shared.config import settings
from shared.models import AgentVerdict, ChangeType, RiskLevel, DiffAgentPayload

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DiffAnalysisAgent(BaseAgent):
    """Agent that analyzes git diffs and categorizes changes."""

    def __init__(self):
        super().__init__("diff_agent")

    async def analyze(self, data: Dict[str, Any]) -> tuple[AgentVerdict, float, Dict[str, Any]]:
        """Analyze the diff and categorize changes."""
        diff = data.get("diff", "")

        # Parse diff
        files_changed = self._count_files_changed(diff)
        lines_added, lines_deleted = self._count_lines(diff)
        change_types = self._categorize_changes(diff)
        affected_modules = self._extract_affected_modules(diff)

        # Calculate risk level
        risk_level = self._calculate_risk_level(
            files_changed, lines_added, lines_deleted, change_types
        )

        # Determine verdict based on risk
        verdict = self._determine_verdict(risk_level, change_types)
        confidence = self._calculate_confidence(files_changed, diff)

        # Build payload
        payload = DiffAgentPayload(
            files_changed=files_changed,
            lines_added=lines_added,
            lines_deleted=lines_deleted,
            change_types=change_types,
            risk_level=risk_level,
            affected_modules=affected_modules
        ).model_dump()

        return verdict, confidence, payload

    def _count_files_changed(self, diff: str) -> int:
        """Count number of files changed in diff."""
        file_pattern = r'^\+\+\+ b/(.+)$'
        matches = re.findall(file_pattern, diff, re.MULTILINE)
        return len(matches)

    def _count_lines(self, diff: str) -> tuple[int, int]:
        """Count lines added and deleted."""
        lines = diff.split('\n')
        added = sum(1 for line in lines if line.startswith('+') and not line.startswith('+++'))
        deleted = sum(1 for line in lines if line.startswith('-') and not line.startswith('---'))
        return added, deleted

    def _categorize_changes(self, diff: str) -> list[ChangeType]:
        """Categorize types of changes."""
        change_types = set()

        # Extract file paths
        file_pattern = r'^\+\+\+ b/(.+)$'
        files = re.findall(file_pattern, diff, re.MULTILINE)

        for file in files:
            file_lower = file.lower()

            # Database changes
            if any(x in file_lower for x in ['migration', 'schema', 'models.py', 'alembic']):
                change_types.add(ChangeType.DB)

            # API changes
            if any(x in file_lower for x in ['api', 'endpoint', 'route', 'controller']):
                change_types.add(ChangeType.API)

            # UI changes
            if any(x in file_lower for x in ['.jsx', '.tsx', '.vue', '.html', '.css', 'component']):
                change_types.add(ChangeType.UI)

            # Config changes
            if any(x in file_lower for x in ['config', '.env', '.yaml', '.yml', '.json', 'settings']):
                change_types.add(ChangeType.CONFIG)

            # Dependency changes
            if any(x in file_lower for x in ['requirements.txt', 'package.json', 'go.mod', 'cargo.toml']):
                change_types.add(ChangeType.DEPENDENCY)

            # Test changes
            if any(x in file_lower for x in ['test_', '_test.', 'spec.', '.test.', '__test__']):
                change_types.add(ChangeType.TEST)

            # Documentation
            if any(x in file_lower for x in ['.md', 'readme', 'docs/']):
                change_types.add(ChangeType.DOCS)

        if not change_types:
            change_types.add(ChangeType.OTHER)

        return list(change_types)

    def _extract_affected_modules(self, diff: str) -> list[str]:
        """Extract affected modules/directories."""
        file_pattern = r'^\+\+\+ b/(.+)$'
        files = re.findall(file_pattern, diff, re.MULTILINE)

        modules = set()
        for file in files:
            parts = file.split('/')
            if len(parts) > 1:
                modules.add(parts[0])

        return list(modules)

    def _calculate_risk_level(
        self,
        files_changed: int,
        lines_added: int,
        lines_deleted: int,
        change_types: list[ChangeType]
    ) -> RiskLevel:
        """Calculate risk level based on change metrics."""
        total_lines = lines_added + lines_deleted

        # Critical risk factors
        if ChangeType.DB in change_types and files_changed > 1:
            return RiskLevel.CRITICAL

        if files_changed > 20 or total_lines > 1000:
            return RiskLevel.CRITICAL

        # High risk factors
        if ChangeType.DB in change_types or ChangeType.DEPENDENCY in change_types:
            return RiskLevel.HIGH

        if files_changed > 10 or total_lines > 500:
            return RiskLevel.HIGH

        # Medium risk
        if ChangeType.API in change_types or files_changed > 5:
            return RiskLevel.MEDIUM

        # Low risk
        if change_types == [ChangeType.TEST] or change_types == [ChangeType.DOCS]:
            return RiskLevel.LOW

        return RiskLevel.MEDIUM

    def _determine_verdict(self, risk_level: RiskLevel, change_types: list[ChangeType]) -> AgentVerdict:
        """Determine verdict based on risk level."""
        # Diff agent doesn't reject, only warns or approves
        if risk_level == RiskLevel.CRITICAL:
            return AgentVerdict.WARN

        if risk_level == RiskLevel.HIGH:
            return AgentVerdict.WARN

        return AgentVerdict.APPROVE

    def _calculate_confidence(self, files_changed: int, diff: str) -> float:
        """Calculate confidence in the analysis."""
        # Higher confidence when we have clear patterns
        if files_changed == 0 or not diff:
            return 0.3

        # Moderate confidence for normal changes
        if files_changed < 20:
            return 0.85

        # Lower confidence for massive changes
        return 0.65


agent = DiffAnalysisAgent()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    import asyncio
    asyncio.create_task(agent.start())
    logger.info("Diff Analysis Agent started")

    yield

    # Shutdown
    await agent.stop()
    logger.info("Diff Analysis Agent stopped")


app = FastAPI(
    title="Diff Analysis Agent",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "agent": "diff_agent"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.diff_agent_host,
        port=settings.diff_agent_port,
        log_level="info"
    )
