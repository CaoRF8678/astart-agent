import asyncio
import os
import socket
import time

from contextlib import suppress
from datetime import datetime, timedelta, timezone

from core.logging_config import logger
from workflows.material_processing_workflow import (
    MaterialProcessingError,
)


class MaterialProcessingWorker:
    def __init__(
        self,
        *,
        repository,
        workflow,
        poll_interval_seconds: float = 2,  #Worker 没有领到任务时，隔多久再去数据库检查一次
        heartbeat_interval_seconds: float = 60,  #Worker 正在处理某个任务时，每隔多久更新一次 heartbeat。
        stale_timeout_seconds: float = 300, #一个 processing 任务多久没收到 heartbeat，就认为它可能已经失活。
        stale_check_interval_seconds: float = 60, #Worker 每隔多久执行一次 stale task 检查。
    ) -> None:
        self.repository = repository
        self.workflow = workflow
        self.poll_interval_seconds = poll_interval_seconds
        self.heartbeat_interval_seconds = heartbeat_interval_seconds
        self.stale_timeout_seconds = stale_timeout_seconds
        self.stale_check_interval_seconds = (
            stale_check_interval_seconds
        )
        self.worker_id = (
            f"{socket.gethostname()}-{os.getpid()}"    #前半段，获取当前电脑/服务器的主机名 后半段，获取当前python的pid
        )

    async def _heartbeat_loop(
        self,
        *,
        file_id: str,
    ) -> None:
        while True:
            await asyncio.sleep(
                self.heartbeat_interval_seconds
            )
            try:
                updated = await self.repository.update_heartbeat(
                    file_id=file_id,
                    worker_id=self.worker_id,
                )
            except Exception:
                logger.exception(
                    "Material heartbeat failed: %s",
                    file_id,
                )
                continue

            if not updated:
                logger.warning(
                    "Material heartbeat lost ownership: %s",
                    file_id,
                )
                return

    async def _maybe_requeue_stale(
        self,
        *,
        last_check: float,
    ) -> float:
        now = time.monotonic()
        if (
            now - last_check
            < self.stale_check_interval_seconds
        ):
            return last_check

        stale_before = (      #更新时间不早于这个时间的，就该out了
            datetime.now(timezone.utc)
            - timedelta(
                seconds=self.stale_timeout_seconds
            )
        )
        try:
            count = await self.repository.requeue_stale_sources(   #找出已经失活的任务，并且将他重新设置为pending
                stale_before=stale_before
            )
            if count:
                logger.warning(
                    "Requeued %s stale material source(s).",
                    count,
                )
        except Exception:
            logger.exception(
                "Failed to requeue stale material sources."
            )

        return now

    async def run_forever(self) -> None:
        last_stale_check = 0.0

        while True:
            last_stale_check = await self._maybe_requeue_stale(   #检查是否到了清理stale任务的时间，如果到了，就把失联任务放回pending
                last_check=last_stale_check
            )

            try:
                source = await self.repository.claim_next_pending_source(
                    worker_id=self.worker_id
                )
            except Exception:
                logger.exception(
                    "Failed to claim pending material source."
                )
                await asyncio.sleep(
                    self.poll_interval_seconds
                )
                continue

            if source is None:
                await asyncio.sleep(
                    self.poll_interval_seconds
                )
                continue

            heartbeat_task = asyncio.create_task(
                self._heartbeat_loop(
                    file_id=source.file_id
                )
            )

            try:
                await self.workflow.run(
                    source=source,
                    worker_id=self.worker_id,
                )
            except MaterialProcessingError as exc:
                logger.exception(
                    "Material processing failed: %s",
                    source.file_id,
                )
                try:
                    updated = await self.repository.mark_source_failed(
                        file_id=source.file_id,
                        worker_id=self.worker_id,
                        error_code=exc.code,
                        error_message=exc.message,
                    )
                    if not updated:
                        logger.warning(
                            "Could not mark material failed because ownership changed: %s",
                            source.file_id,
                        )
                except Exception:
                    logger.exception(
                        "Failed to persist material failure: %s",
                        source.file_id,
                    )
            finally:  #不管前面是成功还是失败，最后都执行
                heartbeat_task.cancel() 
                with suppress(asyncio.CancelledError):  #等 heartbeat 结束；如果只是因为正常取消而抛出 CancelledError，就忽略它。
                    await heartbeat_task