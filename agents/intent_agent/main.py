"""
Commit Intent Agent - Compares commit message intent with actual code changes.
Uses LLM reasoning to detect intent mismatches.
"""
import logging
from typing import Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from agents.base_agent import BaseAgent
from shared.config import settings
from shared.models import AgentVerdict, IntentAgentPayload
from shared.llm import llm_client

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IntentAgent(BaseAgent):
    """Agent that validates commit intent against actual changes."""

    def __init__(self):
        super().__init__("intent_agent")

    async def analyze(self, data: Dict[str, Any]) -> tuple[AgentVerdict, float, Dict[str, Any]]:
        """Analyze commit intent vs actual changes."""
        commit_message = data.get("commit_message", "")
        diff = data.get("diff", "")

        # Extract commit intent
        commit_intent = self._extract_intent(commit_message)

        # Get diff summary
        diff_summary = self._summarize_diff(diff)

        # Use LLM to analyze intent match
        intent_match, reason, discrepancies = await self._analyze_with_llm(
            commit_intent, diff_summary, diff
        )

        # Determine verdict
        verdict = self._determine_verdict(intent_match, discrepancies)
        confidence = self._calculate_confidence(intent_match, len(discrepancies))

        # Build payload
        payload = IntentAgentPayload(
            intent_match=intent_match,
            reason=reason,
            commit_intent=commit_intent,
            actual_changes=diff_summary,
            discrepancies=discrepancies
        ).model_dump()

        return verdict, confidence, payload

    def _extract_intent(self, commit_message: str) -> str:
        """Extract the intent from commit message."""
        # Get first line (subject)
        lines = commit_message.strip().split('\n')
        return lines[0] if lines else ""

    def _summarize_diff(self, diff: str) -> str:
        """Create a summary of the diff."""
        import re

        # Extract changed files
        file_pattern = r'^\+\+\+ b/(.+)$'
        files = re.findall(file_pattern, diff, re.MULTILINE)

        # Count additions/deletions
        lines = diff.split('\n')
        added = sum(1 for line in lines if line.startswith('+') and not line.startswith('+++'))
        deleted = sum(1 for line in lines if line.startswith('-') and not line.startswith('---'))

        summary = f"Changed {len(files)} file(s): {', '.join(files[:5])}"
        if len(files) > 5:
            summary += f" and {len(files) - 5} more"

        summary += f"\n+{added} lines added, -{deleted} lines deleted"

        return summary

    async def _analyze_with_llm(
        self,
        commit_intent: str,
        diff_summary: str,
        full_diff: str
    ) -> tuple[bool, str, list[str]]:
        """Use LLM to analyze intent match."""
        # Truncate diff if too long
        max_diff_length = 4000
        truncated_diff = full_diff[:max_diff_length]
        if len(full_diff) > max_diff_length:
            truncated_diff += "\n... (truncated)"

        system_prompt = """You are a code review assistant analyzing whether a commit's stated intent matches its actual changes.

Your task:
1. Compare the commit message with the actual code changes
2. Identify any mismatches or discrepancies
3. Determine if the changes align with the stated intent

Return your analysis in this exact format:
MATCH: [YES/NO]
REASON: [Brief explanation]
DISCREPANCIES: [List any discrepancies, one per line, or "None"]"""

        user_prompt = f"""Commit Intent: {commit_intent}

Diff Summary: {diff_summary}

Actual Changes:
```diff
{truncated_diff}
```

Does this diff align with the commit intent?"""

        try:
            response = await llm_client.complete(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.3,
                max_tokens=1000
            )

            # Parse response
            intent_match, reason, discrepancies = self._parse_llm_response(response)

            return intent_match, reason, discrepancies

        except Exception as e:
            logger.error(f"LLM analysis failed: {e}", exc_info=True)
            # Fallback to simple heuristic
            return True, "LLM analysis unavailable, defaulting to approval", []

    def _parse_llm_response(self, response: str) -> tuple[bool, str, list[str]]:
        """Parse LLM response."""
        lines = response.strip().split('\n')

        intent_match = True
        reason = "No specific reason provided"
        discrepancies = []

        for line in lines:
            line = line.strip()

            if line.startswith("MATCH:"):
                match_value = line.split(":", 1)[1].strip().upper()
                intent_match = match_value == "YES"

            elif line.startswith("REASON:"):
                reason = line.split(":", 1)[1].strip()

            elif line.startswith("DISCREPANCIES:"):
                disc_value = line.split(":", 1)[1].strip()
                if disc_value.lower() != "none":
                    discrepancies.append(disc_value)

            elif line.startswith("-") and discrepancies:
                # Additional discrepancy line
                discrepancies.append(line.lstrip("- ").strip())

        return intent_match, reason, discrepancies

    def _determine_verdict(self, intent_match: bool, discrepancies: list[str]) -> AgentVerdict:
        """Determine verdict based on intent match."""
        if not intent_match:
            # Critical mismatch
            if len(discrepancies) > 3:
                return AgentVerdict.REJECT

            # Minor mismatch
            return AgentVerdict.WARN

        return AgentVerdict.APPROVE

    def _calculate_confidence(self, intent_match: bool, num_discrepancies: int) -> float:
        """Calculate confidence in the analysis."""
        base_confidence = 0.85

        if not intent_match:
            # Lower confidence when rejecting
            base_confidence = 0.75

        # Reduce confidence based on number of discrepancies
        confidence_penalty = num_discrepancies * 0.05
        return max(0.5, base_confidence - confidence_penalty)


agent = IntentAgent()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    import asyncio
    asyncio.create_task(agent.start())
    logger.info("Intent Agent started")

    yield

    # Shutdown
    await agent.stop()
    logger.info("Intent Agent stopped")


app = FastAPI(
    title="Commit Intent Agent",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "agent": "intent_agent"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.intent_agent_host,
        port=settings.intent_agent_port,
        log_level="info"
    )
