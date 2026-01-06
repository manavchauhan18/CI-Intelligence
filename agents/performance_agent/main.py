"""
Performance Agent - Detects performance anti-patterns.
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
from shared.models import AgentVerdict, PerformanceAgentPayload
from shared.llm import llm_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PerformanceAgent(BaseAgent):
    """Agent that analyzes performance implications of code changes."""

    PERFORMANCE_PATTERNS = {
        "N+1 Query": r'for\s+\w+\s+in\s+.*:\s*\n\s+.*\.get\(|for.*in.*:.*query\(|for.*in.*:.*filter\(',
        "Blocking Call": r'\.wait\(|time\.sleep\(|requests\.get\((?!.*timeout)',
        "Nested Loop": r'for\s+.*:\s*\n\s+for\s+',
        "Large List Comprehension": r'\[.*for.*for.*\]',
        "Synchronous in Async": r'async\s+def.*:\s*\n.*(?<!await\s)requests\.|async\s+def.*:\s*\n.*time\.sleep',
    }

    def __init__(self):
        super().__init__("performance_agent")

    async def analyze(self, data: Dict[str, Any]) -> tuple[AgentVerdict, float, Dict[str, Any]]:
        """Analyze performance implications."""
        diff = data.get("diff", "")

        # Pattern-based detection
        performance_issues = self._detect_performance_issues(diff)

        # Count specific issue types
        n_plus_one = sum(1 for i in performance_issues if "N+1" in i["type"])
        blocking_calls = sum(1 for i in performance_issues if "Blocking" in i["type"])
        heavy_loops = sum(1 for i in performance_issues if "Loop" in i["type"])

        # LLM analysis for complex patterns
        llm_issues = await self._analyze_with_llm(diff)
        performance_issues.extend(llm_issues)

        # Calculate score
        performance_score = self._calculate_performance_score(performance_issues)

        # Determine verdict
        verdict = self._determine_verdict(performance_issues)
        confidence = 0.75

        payload = PerformanceAgentPayload(
            performance_issues=[{
                "type": i["type"],
                "line": i.get("line", 0),
                "details": i["details"]
            } for i in performance_issues],
            n_plus_one_queries=n_plus_one,
            blocking_calls=blocking_calls,
            heavy_loops=heavy_loops,
            performance_score=performance_score
        ).model_dump()

        return verdict, confidence, payload

    def _detect_performance_issues(self, diff: str) -> List[Dict[str, Any]]:
        """Detect performance issues using patterns."""
        issues = []
        lines = diff.split('\n')

        for line_num, line in enumerate(lines, 1):
            if not line.startswith('+'):
                continue

            line_content = line[1:]

            for issue_type, pattern in self.PERFORMANCE_PATTERNS.items():
                if re.search(pattern, line_content, re.IGNORECASE | re.MULTILINE):
                    issues.append({
                        "type": issue_type,
                        "line": line_num,
                        "details": f"Potential {issue_type} detected"
                    })

        return issues

    async def _analyze_with_llm(self, diff: str) -> List[Dict[str, Any]]:
        """LLM-based performance analysis."""
        max_diff_length = 3000
        truncated_diff = diff[:max_diff_length]
        if len(diff) > max_diff_length:
            truncated_diff += "\n... (truncated)"

        system_prompt = """Analyze code changes for performance issues:
- Database query inefficiencies
- Algorithmic complexity problems
- Resource leaks
- Inefficient data structures

Return:
ISSUES: [count]
FINDINGS:
- [finding]
(Or "None")"""

        user_prompt = f"""```diff
{truncated_diff}
```
Identify performance issues:"""

        try:
            response = await llm_client.complete(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.2,
                max_tokens=600
            )

            return self._parse_llm_response(response)
        except Exception as e:
            logger.error(f"LLM analysis failed: {e}")
            return []

    def _parse_llm_response(self, response: str) -> List[Dict[str, Any]]:
        """Parse LLM response."""
        issues = []
        for line in response.split('\n'):
            line = line.strip()
            if line.startswith("-") and line.lower() != "- none":
                issues.append({
                    "type": "Performance Concern (LLM)",
                    "details": line.lstrip("- ").strip()
                })
        return issues

    def _calculate_performance_score(self, issues: List[Dict[str, Any]]) -> float:
        """Calculate performance score."""
        score = 1.0
        score -= len(issues) * 0.15
        return max(0.0, score)

    def _determine_verdict(self, issues: List[Dict[str, Any]]) -> AgentVerdict:
        """Determine verdict."""
        critical = sum(1 for i in issues if any(x in i["type"].lower() for x in ["n+1", "blocking"]))

        if critical > 2:
            return AgentVerdict.REJECT
        if len(issues) > 3:
            return AgentVerdict.WARN
        if len(issues) > 0:
            return AgentVerdict.WARN

        return AgentVerdict.APPROVE


agent = PerformanceAgent()


@asynccontextmanager
async def lifespan(app: FastAPI):
    import asyncio
    asyncio.create_task(agent.start())
    logger.info("Performance Agent started")
    yield
    await agent.stop()


app = FastAPI(title="Performance Agent", version="1.0.0", lifespan=lifespan)


@app.get("/health")
async def health_check():
    return {"status": "healthy", "agent": "performance_agent"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.performance_agent_host, port=settings.performance_agent_port)
