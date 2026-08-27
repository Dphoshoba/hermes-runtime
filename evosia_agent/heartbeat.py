"""Heartbeat — periodic heartbeat with retry/backoff and job polling for LA2/LA4."""

from __future__ import annotations

import logging
import time
from typing import Callable

from .api_client import ApiClient, ApiError
from .config import RETRY_BASE_SECONDS, RETRY_MAX_SECONDS, RETRY_MULTIPLIER

logger = logging.getLogger(__name__)


class HeartbeatLoop:
    """Manages periodic heartbeat to EVOSIA Cloud with job polling.

    Handles:
    - Periodic heartbeat at configured interval
    - Bounded retry/backoff on network failure
    - Revocation detection and stop
    - Credential expiry detection
    - Job polling and execution (LA4)
    """

    def __init__(
        self,
        api_client: ApiClient,
        device_id: str,
        device_credential: str,
        agent_version: str,
        interval_seconds: int = 60,
        on_revoked: Callable[[], None] | None = None,
        on_expired: Callable[[], None] | None = None,
        on_job_received: Callable[[dict], None] | None = None,
    ) -> None:
        self._api = api_client
        self._device_id = device_id
        self._device_credential = device_credential
        self._agent_version = agent_version
        self._interval = interval_seconds
        self._on_revoked = on_revoked
        self._on_expired = on_expired
        self._on_job_received = on_job_received
        self._running = False

    def start(self) -> None:
        """Start the heartbeat loop. Blocks until stopped or revoked."""
        self._running = True
        retry_delay = RETRY_BASE_SECONDS

        logger.info("Heartbeat started (interval: %ds)", self._interval)

        while self._running:
            try:
                response = self._api.send_heartbeat(
                    device_id=self._device_id,
                    device_credential=self._device_credential,
                    agent_version=self._agent_version,
                )

                status = response.get("status", "unknown")

                if status == "ok":
                    logger.debug("Heartbeat successful")
                    retry_delay = RETRY_BASE_SECONDS  # Reset backoff on success

                    # Check for pending jobs
                    pending_jobs = response.get("pending_jobs", [])
                    if pending_jobs and self._on_job_received:
                        for job_id in pending_jobs:
                            try:
                                job = self._api.get_job(job_id, self._device_credential)
                                self._on_job_received(job)
                            except ApiError as exc:
                                logger.warning("Failed to fetch job %s: %s", job_id, exc.detail)

                    self._sleep(self._interval)

                elif status == "revoked":
                    logger.warning("Device revoked — stopping heartbeat")
                    self._running = False
                    if self._on_revoked:
                        self._on_revoked()
                    return

                else:
                    logger.warning("Unexpected heartbeat status: %s", status)
                    self._sleep(retry_delay)
                    retry_delay = min(retry_delay * RETRY_MULTIPLIER, RETRY_MAX_SECONDS)

            except ApiError as exc:
                if exc.status_code == 401:
                    logger.error("Credential expired or invalid — stopping heartbeat")
                    self._running = False
                    if self._on_expired:
                        self._on_expired()
                    return

                if exc.status_code == 403:
                    logger.warning("Device revoked — stopping heartbeat")
                    self._running = False
                    if self._on_revoked:
                        self._on_revoked()
                    return

                logger.warning("Connection unavailable — retrying in %ds", retry_delay)
                self._sleep(retry_delay)
                retry_delay = min(retry_delay * RETRY_MULTIPLIER, RETRY_MAX_SECONDS)

            except Exception as exc:
                logger.error("Unexpected error in heartbeat: %s", exc)
                self._sleep(retry_delay)
                retry_delay = min(retry_delay * RETRY_MULTIPLIER, RETRY_MAX_SECONDS)

    def stop(self) -> None:
        """Stop the heartbeat loop gracefully."""
        self._running = False
        logger.info("Heartbeat stopped")

    def _sleep(self, seconds: float) -> None:
        """Sleep in small increments to allow quick shutdown."""
        end_time = time.monotonic() + seconds
        while self._running and time.monotonic() < end_time:
            time.sleep(0.5)
