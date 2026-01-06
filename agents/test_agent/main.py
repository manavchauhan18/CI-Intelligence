"""
Test Impact Agent - Analyzes test coverage and identifies untested paths.
"""
import re
import logging
from typing import Dict, Any, List
from contextlib import asynccontextmanager
from fastapi import FastAPI

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.base_agent import BaseAgent
from shared.config import settings
from shared.models import AgentVerdict, TestAgentPayload

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestImpactAgent(BaseAgent):
    """Agent that analyzes test coverage impact."""

    def __init__(self):
        super().__init__("test_agent")

    async def analyze(self, data: Dict[str, Any]) -> tuple[AgentVerdict, float, Dict[str, Any]]:
        """Analyze test impact."""
        diff = data.get("diff", "")

        # Count test files vs implementation files
        test_files, impl_files = self._categorize_files(diff)

        # Calculate coverage delta (simplified)
        coverage_delta = self._estimate_coverage_delta(test_files, impl_files)

        # Identify untested paths
        untested_paths = self._identify_untested_paths(impl_files, test_files)

        # Calculate test score
        test_score = self._calculate_test_score(len(test_files), len(impl_files), len(untested_paths))

        # Determine verdict
        verdict = self._determine_verdict(len(test_files), len(impl_files), len(untested_paths))
        confidence = 0.70

        payload = TestAgentPayload(
            tests_affected=len(test_files),
            coverage_delta=coverage_delta,
            untested_paths=untested_paths,
            test_score=test_score
        ).model_dump()

        return verdict, confidence, payload

    def _categorize_files(self, diff: str) -> tuple[List[str], List[str]]:
        """Categorize files into test and implementation."""
        file_pattern = r'^\+\+\+ b/(.+)$'
        files = re.findall(file_pattern, diff, re.MULTILINE)

        test_files = []
        impl_files = []

        for file in files:
            file_lower = file.lower()
            if any(x in file_lower for x in ['test_', '_test.', 'spec.', '.test.', '__test__', '/tests/']):
                test_files.append(file)
            else:
                impl_files.append(file)

        return test_files, impl_files

    def _estimate_coverage_delta(self, test_files: List[str], impl_files: List[str]) -> float:
        """Estimate coverage change (simplified heuristic)."""
        if len(impl_files) == 0:
            return 0.0

        # Rough heuristic: ratio of test files to impl files
        ratio = len(test_files) / len(impl_files)

        # Assume each test file covers ~60% of its corresponding impl
        coverage_estimate = min(ratio * 0.6, 1.0)

        # Return delta (negative if inadequate)
        if coverage_estimate < 0.5:
            return -(0.5 - coverage_estimate)

        return 0.0

    def _identify_untested_paths(self, impl_files: List[str], test_files: List[str]) -> List[str]:
        """Identify implementation files without corresponding tests."""
        untested = []

        for impl_file in impl_files:
            # Skip certain file types
            if any(impl_file.endswith(x) for x in ['.md', '.json', '.yaml', '.yml', '.txt']):
                continue

            # Check if there's a corresponding test file
            base_name = impl_file.rsplit('.', 1)[0]
            has_test = any(base_name in test_file for test_file in test_files)

            if not has_test:
                untested.append(impl_file)

        return untested

    def _calculate_test_score(self, num_tests: int, num_impl: int, num_untested: int) -> float:
        """Calculate test adequacy score."""
        if num_impl == 0:
            return 1.0

        # Base score on test ratio
        test_ratio = num_tests / max(num_impl, 1)
        base_score = min(test_ratio, 1.0)

        # Penalize untested paths
        untested_ratio = num_untested / num_impl
        penalty = untested_ratio * 0.5

        return max(0.0, base_score - penalty)

    def _determine_verdict(self, num_tests: int, num_impl: int, num_untested: int) -> AgentVerdict:
        """Determine verdict based on test coverage."""
        # No implementation changes
        if num_impl == 0:
            return AgentVerdict.APPROVE

        # Implementation changes with no tests
        if num_impl > 0 and num_tests == 0:
            if num_impl > 3:
                return AgentVerdict.REJECT
            return AgentVerdict.WARN

        # High ratio of untested paths
        if num_impl > 0:
            untested_ratio = num_untested / num_impl
            if untested_ratio > 0.7:
                return AgentVerdict.WARN

        return AgentVerdict.APPROVE


agent = TestImpactAgent()


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    asyncio.create_task(agent.start())
    logger.info("Test Impact Agent started")
    yield
    await agent.stop()


app = FastAPI(title="Test Impact Agent", version="1.0.0", lifespan=lifespan)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "agent": "test_agent"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.test_agent_host, port=settings.test_agent_port)
