"""
Base agent class with common functionality for all agents.
"""
import logging
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.config import settings
from shared.message_bus import message_bus
from shared.models import AgentResultEvent, AgentVerdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all agents.

    Each agent:
    - Subscribes to code_analysis_requested stream
    - Performs independent analysis
    - Publishes results to agent_results stream
    """

    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.running = False
        logger.info(f"Initialized agent: {agent_name}")

    async def start(self):
        """Start the agent."""
        self.running = True
        logger.info(f"Starting agent: {self.agent_name}")

        # Connect to message bus
        await message_bus.connect()

        # Start consuming messages
        await self.consume_analysis_requests()

    async def stop(self):
        """Stop the agent."""
        self.running = False
        await message_bus.disconnect()
        logger.info(f"Stopped agent: {self.agent_name}")

    async def consume_analysis_requests(self):
        """Consume code analysis request events."""
        async def handler(data: Dict[str, Any]):
            """Handle code analysis request."""
            try:
                job_id = data["job_id"]
                logger.info(f"[{self.agent_name}] Processing job: {job_id}")

                # Perform analysis
                verdict, confidence, payload = await self.analyze(data)

                # Publish result
                result_event = AgentResultEvent(
                    job_id=job_id,
                    agent_name=self.agent_name,
                    verdict=verdict,
                    confidence=confidence,
                    payload=payload,
                    timestamp=datetime.utcnow()
                )

                await message_bus.publish_agent_result(result_event)

                logger.info(
                    f"[{self.agent_name}] Completed job: {job_id} "
                    f"with verdict: {verdict.value} (confidence: {confidence:.2f})"
                )

            except Exception as e:
                logger.error(f"[{self.agent_name}] Error processing job: {e}", exc_info=True)

        await message_bus.consume_stream(
            stream_name=message_bus.CODE_ANALYSIS_STREAM,
            consumer_group=f"{self.agent_name}_group",
            consumer_name=f"{self.agent_name}_1",
            handler=handler
        )

    @abstractmethod
    async def analyze(self, data: Dict[str, Any]) -> tuple[AgentVerdict, float, Dict[str, Any]]:
        """
        Perform agent-specific analysis.

        Args:
            data: Analysis request data containing commit info and diff

        Returns:
            Tuple of (verdict, confidence, payload)
        """
        pass

    async def run_with_timeout(self, coro, timeout: int = None):
        """
        Run a coroutine with timeout.

        Args:
            coro: Coroutine to run
            timeout: Timeout in seconds (defaults to settings.agent_timeout_seconds)

        Returns:
            Result of coroutine

        Raises:
            asyncio.TimeoutError: If timeout is exceeded
        """
        timeout = timeout or settings.agent_timeout_seconds
        return await asyncio.wait_for(coro, timeout=timeout)

    def calculate_confidence(self, factors: Dict[str, float]) -> float:
        """
        Calculate confidence score from multiple factors.

        Args:
            factors: Dictionary of factor_name -> score (0.0 to 1.0)

        Returns:
            Weighted confidence score (0.0 to 1.0)
        """
        if not factors:
            return 0.5

        # Simple average for now
        return sum(factors.values()) / len(factors)
