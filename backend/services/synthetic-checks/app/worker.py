"""Temporal worker entrypoint — polls keep-synth for synthetic check workflows."""

from __future__ import annotations

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor

from temporalio.client import Client
from temporalio.worker import Worker

from app.activities import notify_keep_alert, probe_target
from app.otel_setup import setup_otel
from app.workflows import ProbeTarget, ProbeTargetGroup, ProbeTargets

logger = logging.getLogger(__name__)


async def main() -> None:
    address = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
    namespace = os.environ.get("TEMPORAL_NAMESPACE", "default")
    task_queue = os.environ.get("TEMPORAL_TASK_QUEUE", "keep-synth")

    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    setup_otel()
    logger.info(
        "Connecting synthetic-checks worker address=%s namespace=%s queue=%s",
        address,
        namespace,
        task_queue,
    )

    client = await Client.connect(address, namespace=namespace)
    with ThreadPoolExecutor(max_workers=20) as activity_executor:
        worker = Worker(
            client,
            task_queue=task_queue,
            workflows=[ProbeTarget, ProbeTargetGroup, ProbeTargets],
            activities=[probe_target, notify_keep_alert],
            activity_executor=activity_executor,
        )
        logger.info("Synthetic-checks worker started on %s", task_queue)
        await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
