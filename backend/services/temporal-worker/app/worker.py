"""Temporal worker entrypoint — polls keep-ops for ListAndZipDirectory."""

from __future__ import annotations

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor

from temporalio.client import Client
from temporalio.worker import Worker

from app.activities import create_zip_from_ls, run_ls
from app.workflows import ListAndZipDirectory

logger = logging.getLogger(__name__)


async def main() -> None:
    address = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
    namespace = os.environ.get("TEMPORAL_NAMESPACE", "default")
    task_queue = os.environ.get("TEMPORAL_TASK_QUEUE", "keep-ops")

    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logger.info(
        "Connecting Temporal worker address=%s namespace=%s task_queue=%s",
        address,
        namespace,
        task_queue,
    )

    client = await Client.connect(address, namespace=namespace)
    activity_executor = ThreadPoolExecutor(max_workers=10)
    worker = Worker(
        client,
        task_queue=task_queue,
        workflows=[ListAndZipDirectory],
        activities=[run_ls, create_zip_from_ls],
        activity_executor=activity_executor,
    )
    logger.info("Temporal worker started on queue %s", task_queue)
    try:
        await worker.run()
    finally:
        activity_executor.shutdown(wait=False)


if __name__ == "__main__":
    asyncio.run(main())
