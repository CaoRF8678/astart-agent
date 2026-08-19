#负责轮询，领取job，执行workflow，处理停止

import os
import socket
from asyncio import sleep
from core.logging_config import logger

class CourseGenerationWorker:

    def __init__(
        self,
        *,
        repository,
        workflow,
        poll_interval_seconds=2, #轮询间隔
    ):
        self.repository = repository
        self.workflow = workflow
        self.poll_interval_seconds = poll_interval_seconds
        self.worker_id = (
            f"{socket.gethostname()}-"
            f"{os.getpid()}"
            )


    async def run_forever(self):

        while True:
            generation_id = (
                await self.repository
                .claim_next_pending_job(
                    worker_id=self.worker_id
                )
            )

            if generation_id is None:
                # sleep
                await sleep(self.poll_interval_seconds)
                continue

            try:
                await self.workflow.run(
                    generation_id=generation_id
                )

            except Exception:
                logger.exception(
                    "Course generation failed: %s",
                    generation_id,
                )
            