"""Kafka integration for event streaming.

Original bug this fixes: KafkaProducer(...) blocks on its first broker
connection attempt before the surrounding try/except gets a chance to catch
anything, which made every request that touched this module hang
indefinitely whenever Kafka wasn't reachable - confirmed by calling
send_prediction_event() directly and watching it never return.

Fix: connecting and sending both happen on a single background thread via a
queue. API request handlers only ever call `.send_prediction_event(...)`,
which is a non-blocking queue.put() - it returns in microseconds regardless
of whether Kafka is up, down, or slow. The connection attempt itself is
still given a bounded timeout so the background thread doesn't hang forever
either.
"""
import json
import queue
import threading
from typing import Optional, Dict, Any
from loguru import logger

from core.config import KAFKA_BOOTSTRAP_SERVERS, KAFKA_ENABLED, KAFKA_CONNECT_TIMEOUT_SECONDS


class KafkaEventProducer:
    """Non-blocking producer. Events are queued and published by a single
    background worker thread; callers never touch the network directly."""

    def __init__(self, bootstrap_servers: Optional[list] = None, enabled: Optional[bool] = None):
        self.bootstrap_servers = bootstrap_servers or KAFKA_BOOTSTRAP_SERVERS
        self.enabled = KAFKA_ENABLED if enabled is None else enabled
        self._producer = None
        self._connect_attempted = False
        self._connected = False
        self._queue: "queue.Queue" = queue.Queue(maxsize=10_000)
        self._worker: Optional[threading.Thread] = None
        if self.enabled:
            self._start_worker()

    def _start_worker(self):
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    def _connect(self):
        """Attempt a bounded-time connection. Runs only on the worker thread."""
        if self._connect_attempted:
            return
        self._connect_attempted = True
        try:
            from kafka import KafkaProducer
            from kafka.errors import KafkaError  # noqa: F401

            self._producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
                acks="all",
                retries=1,
                # Fixing api_version avoids the broker-version auto-probe on
                # connect, which is what previously made construction block
                # for a long time when no broker was reachable.
                api_version=(2, 5, 0),
                request_timeout_ms=int(KAFKA_CONNECT_TIMEOUT_SECONDS * 1000),
            )
            self._connected = True
            logger.info("Connected to Kafka producer")
        except Exception as e:
            self._connected = False
            logger.warning(f"Could not connect to Kafka ({e}). Events will be logged locally instead.")

    def _run(self):
        self._connect()
        while True:
            topic, event, key = self._queue.get()
            if not self._connected:
                logger.info(f"Kafka event (local, no broker): {topic} - {event}")
                continue
            try:
                future = self._producer.send(topic, value=event, key=key)
                future.get(timeout=KAFKA_CONNECT_TIMEOUT_SECONDS)
            except Exception as e:
                logger.error(f"Failed to send Kafka event: {e}")

    def _enqueue(self, topic: str, event: dict, key: Optional[str] = None):
        if not self.enabled:
            logger.debug(f"Kafka disabled - dropping event: {topic}")
            return
        try:
            self._queue.put_nowait((topic, event, key))
        except queue.Full:
            logger.warning("Kafka event queue full - dropping event")

    def send_prediction_event(self, tenant_id: str, customer_id: int, model_version: str, risk_score: float, risk_class: int):
        event = {
            "event_type": "prediction",
            "tenant_id": tenant_id,
            "customer_id": customer_id,
            "model_version": model_version,
            "risk_score": risk_score,
            "risk_class": risk_class,
            "timestamp": self._get_timestamp(),
        }
        self._enqueue("risk-predictions", event, key=f"{tenant_id}-{customer_id}")

    def send_ab_result_event(self, user_id: int, model_version: str, outcome: str):
        event = {
            "event_type": "ab_result",
            "user_id": user_id,
            "model_version": model_version,
            "outcome": outcome,
            "timestamp": self._get_timestamp(),
        }
        self._enqueue("ab-testing-results", event, key=str(user_id))

    @staticmethod
    def _get_timestamp() -> str:
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).isoformat()

    def close(self):
        if self._producer:
            try:
                self._producer.close(timeout=1)
            except Exception:
                pass
            self._connected = False


# Singleton producer
_producer: Optional[KafkaEventProducer] = None


def get_kafka_producer() -> KafkaEventProducer:
    global _producer
    if _producer is None:
        _producer = KafkaEventProducer()
    return _producer
