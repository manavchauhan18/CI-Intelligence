"""
Redis Streams-based message bus for asynchronous agent communication.
"""
import asyncio
import json
import logging
from typing import Optional, Dict, Any, Callable, Awaitable
from uuid import UUID
import redis.asyncio as redis

from .config import settings
from .models import (
    CodeAnalysisRequestedEvent,
    AgentResultEvent,
    ReleaseDecisionEvent
)

logger = logging.getLogger(__name__)


class MessageBus:
    """Redis Streams-based message bus."""

    # Stream names
    CODE_ANALYSIS_STREAM = "code_analysis_requested"
    AGENT_RESULTS_STREAM = "agent_results"
    RELEASE_DECISION_STREAM = "release_decisions"

    def __init__(self):
        self.redis_client: Optional[redis.Redis] = None
        self._running = False

    async def connect(self):
        """Connect to Redis."""
        self.redis_client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True
        )
        logger.info("Connected to Redis message bus")

    async def disconnect(self):
        """Disconnect from Redis."""
        self._running = False
        if self.redis_client:
            await self.redis_client.close()
            logger.info("Disconnected from Redis message bus")

    async def publish_code_analysis_request(self, event: CodeAnalysisRequestedEvent) -> str:
        """Publish code analysis request event."""
        if not self.redis_client:
            raise RuntimeError("Redis client not connected")

        event_data = {
            "job_id": str(event.job_id),
            "repo_name": event.repo_name,
            "commit_hash": event.commit_hash,
            "commit_message": event.commit_message,
            "diff": event.diff,
            "branch": event.branch,
            "author": event.author,
            "timestamp": event.timestamp.isoformat()
        }

        message_id = await self.redis_client.xadd(
            self.CODE_ANALYSIS_STREAM,
            {"data": json.dumps(event_data)}
        )

        logger.info(f"Published code analysis request: job_id={event.job_id}, message_id={message_id}")
        return message_id

    async def publish_agent_result(self, event: AgentResultEvent) -> str:
        """Publish agent result event."""
        if not self.redis_client:
            raise RuntimeError("Redis client not connected")

        event_data = {
            "job_id": str(event.job_id),
            "agent_name": event.agent_name,
            "verdict": event.verdict.value,
            "confidence": event.confidence,
            "payload": event.payload,
            "timestamp": event.timestamp.isoformat()
        }

        message_id = await self.redis_client.xadd(
            self.AGENT_RESULTS_STREAM,
            {"data": json.dumps(event_data)}
        )

        logger.info(f"Published agent result: agent={event.agent_name}, job_id={event.job_id}, verdict={event.verdict}")
        return message_id

    async def publish_release_decision(self, event: ReleaseDecisionEvent) -> str:
        """Publish release decision event."""
        if not self.redis_client:
            raise RuntimeError("Redis client not connected")

        event_data = {
            "job_id": str(event.job_id),
            "decision": event.decision.value,
            "explanation": event.explanation,
            "agent_results": [
                {
                    "agent_name": r.agent_name,
                    "verdict": r.verdict.value,
                    "confidence": r.confidence
                }
                for r in event.agent_results
            ],
            "timestamp": event.timestamp.isoformat()
        }

        message_id = await self.redis_client.xadd(
            self.RELEASE_DECISION_STREAM,
            {"data": json.dumps(event_data)}
        )

        logger.info(f"Published release decision: job_id={event.job_id}, decision={event.decision}")
        return message_id

    async def consume_stream(
        self,
        stream_name: str,
        consumer_group: str,
        consumer_name: str,
        handler: Callable[[Dict[str, Any]], Awaitable[None]],
        batch_size: int = 10,
        block_ms: int = 5000
    ):
        """
        Consume messages from a Redis stream.

        Args:
            stream_name: Name of the stream to consume
            consumer_group: Consumer group name
            consumer_name: Unique consumer name
            handler: Async function to handle messages
            batch_size: Number of messages to fetch per batch
            block_ms: Time to block waiting for messages
        """
        if not self.redis_client:
            raise RuntimeError("Redis client not connected")

        # Create consumer group if it doesn't exist
        try:
            await self.redis_client.xgroup_create(
                stream_name,
                consumer_group,
                id="0",
                mkstream=True
            )
            logger.info(f"Created consumer group: {consumer_group} for stream: {stream_name}")
        except redis.ResponseError as e:
            if "BUSYGROUP" not in str(e):
                raise

        logger.info(f"Starting consumer: {consumer_name} in group: {consumer_group} for stream: {stream_name}")
        self._running = True

        while self._running:
            try:
                # Read messages from stream
                messages = await self.redis_client.xreadgroup(
                    groupname=consumer_group,
                    consumername=consumer_name,
                    streams={stream_name: ">"},
                    count=batch_size,
                    block=block_ms
                )

                if not messages:
                    continue

                for stream, stream_messages in messages:
                    for message_id, message_data in stream_messages:
                        try:
                            # Parse message
                            data = json.loads(message_data["data"])

                            # Handle message
                            await handler(data)

                            # Acknowledge message
                            await self.redis_client.xack(stream_name, consumer_group, message_id)
                            logger.debug(f"Processed and acknowledged message: {message_id}")

                        except Exception as e:
                            logger.error(f"Error processing message {message_id}: {e}", exc_info=True)
                            # Message will be retried or moved to dead letter queue

            except asyncio.CancelledError:
                logger.info("Consumer cancelled")
                break
            except Exception as e:
                logger.error(f"Error in consumer loop: {e}", exc_info=True)
                await asyncio.sleep(5)  # Back off on error

    async def get_pending_messages(self, stream_name: str, consumer_group: str) -> int:
        """Get count of pending messages in a consumer group."""
        if not self.redis_client:
            raise RuntimeError("Redis client not connected")

        try:
            info = await self.redis_client.xpending(stream_name, consumer_group)
            return info["pending"]
        except Exception:
            return 0

    async def claim_old_messages(
        self,
        stream_name: str,
        consumer_group: str,
        consumer_name: str,
        min_idle_time_ms: int = 300000  # 5 minutes
    ):
        """
        Claim messages that have been idle for too long (for retry/recovery).

        Args:
            stream_name: Stream name
            consumer_group: Consumer group name
            consumer_name: Consumer name to claim messages for
            min_idle_time_ms: Minimum idle time before claiming
        """
        if not self.redis_client:
            raise RuntimeError("Redis client not connected")

        try:
            # Get pending messages
            pending = await self.redis_client.xpending_range(
                stream_name,
                consumer_group,
                min="-",
                max="+",
                count=100
            )

            claimed_count = 0
            for msg in pending:
                message_id = msg["message_id"]
                idle_time = msg["time_since_delivered"]

                if idle_time >= min_idle_time_ms:
                    # Claim the message
                    await self.redis_client.xclaim(
                        stream_name,
                        consumer_group,
                        consumer_name,
                        min_idle_time_ms,
                        [message_id]
                    )
                    claimed_count += 1

            if claimed_count > 0:
                logger.info(f"Claimed {claimed_count} old messages for retry")

        except Exception as e:
            logger.error(f"Error claiming old messages: {e}", exc_info=True)


# Global message bus instance
message_bus = MessageBus()
