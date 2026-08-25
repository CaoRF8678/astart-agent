import asyncio
import logging

from collections.abc import AsyncIterable
from datetime import datetime, timedelta, timezone
from pathlib import Path

import alibabacloud_oss_v2 as oss

from storage.base import (
    FileStorage,
    FileStorageError,
)


logger = logging.getLogger(__name__)

DEFAULT_MULTIPART_PART_SIZE = 8 * 1024 * 1024


class OSSFileStorage(FileStorage):
    def __init__(
        self,
        *,
        region: str,
        bucket: str,
        access_key_id: str,
        access_key_secret: str,
        endpoint: str | None = None,
        multipart_part_size: int = DEFAULT_MULTIPART_PART_SIZE,
    ) -> None:
        if multipart_part_size <= 0:
            raise ValueError(
                "multipart_part_size must be positive."
            )

        credentials_provider = (
            oss.credentials.StaticCredentialsProvider(
                access_key_id=access_key_id,
                access_key_secret=access_key_secret,
            )
        )

        cfg = oss.config.load_default()
        cfg.credentials_provider = credentials_provider
        cfg.region = region

        if endpoint:
            cfg.endpoint = endpoint

        self._client = oss.Client(cfg)
        self._bucket = bucket
        self._part_size = multipart_part_size

    @staticmethod
    def _build_storage_key(
        *,
        file_id: str,
        filename: str,
    ) -> str:
        suffix = Path(filename).suffix.lower()
        now = datetime.now(timezone.utc)
        return (
            f"{now.year:04d}/"
            f"{now.month:02d}/"
            f"{file_id}{suffix}"
        )

    async def _call_oss(
        self,
        func,
        /,
        *args,
        operation: str,
        **kwargs,
    ):
        try:
            return await asyncio.to_thread(
                func,
                *args,
                **kwargs,
            )
        except Exception as exc:
            raise FileStorageError(
                f"OSS {operation} failed."
            ) from exc

    async def save(
        self,
        *,
        file_id: str,
        filename: str,
        data: bytes,
    ) -> str:
        storage_key = self._build_storage_key(
            file_id=file_id,
            filename=filename,
        )

        request = oss.PutObjectRequest(
            bucket=self._bucket,
            key=storage_key,
            body=data,
        )

        await self._call_oss(
            self._client.put_object,
            request,
            operation="put_object",
        )
        return storage_key

    async def _upload_part(
        self,
        *,
        storage_key: str,
        upload_id: str,
        part_number: int,
        data: bytes,
    ) -> oss.UploadPart:
        result = await self._call_oss(
            self._client.upload_part,
            oss.UploadPartRequest(
                bucket=self._bucket,
                key=storage_key,
                upload_id=upload_id,
                part_number=part_number,
                body=data,
            ),
            operation="upload_part",
        )

        return oss.UploadPart(
            part_number=part_number,
            etag=result.etag,
        )

    async def _abort_multipart(
        self,
        *,
        storage_key: str,
        upload_id: str,
    ) -> None:
        await self._call_oss(
            self._client.abort_multipart_upload,
            oss.AbortMultipartUploadRequest(
                bucket=self._bucket,
                key=storage_key,
                upload_id=upload_id,
            ),
            operation="abort_multipart_upload",
        )

    async def save_stream(
        self,
        *,
        file_id: str,
        filename: str,
        chunks: AsyncIterable[bytes],
    ) -> str:
        storage_key = self._build_storage_key(
            file_id=file_id,
            filename=filename,
        )

        initiate_result = await self._call_oss(
            self._client.initiate_multipart_upload,
            oss.InitiateMultipartUploadRequest(
                bucket=self._bucket,
                key=storage_key,
            ),
            operation="initiate_multipart_upload",
        )

        upload_id = initiate_result.upload_id
        parts: list[oss.UploadPart] = []
        buffer = bytearray()
        part_number = 1

        try:
            async for chunk in chunks:
                if not chunk:
                    continue

                buffer.extend(chunk)

                while len(buffer) >= self._part_size:
                    part_data = bytes(
                        buffer[: self._part_size]
                    )
                    del buffer[: self._part_size]

                    parts.append(
                        await self._upload_part(
                            storage_key=storage_key,
                            upload_id=upload_id,
                            part_number=part_number,
                            data=part_data,
                        )
                    )
                    part_number += 1

            if buffer:
                parts.append(
                    await self._upload_part(
                        storage_key=storage_key,
                        upload_id=upload_id,
                        part_number=part_number,
                        data=bytes(buffer),
                    )
                )

            if not parts:
                raise FileStorageError(
                    "Cannot complete an empty multipart upload."
                )

            await self._call_oss(
                self._client.complete_multipart_upload,
                oss.CompleteMultipartUploadRequest(
                    bucket=self._bucket,
                    key=storage_key,
                    upload_id=upload_id,
                    complete_multipart_upload=(
                        oss.CompleteMultipartUpload(
                            parts=parts
                        )
                    ),
                ),
                operation="complete_multipart_upload",
            )

            return storage_key

        except Exception:
            try:
                await self._abort_multipart(
                    storage_key=storage_key,
                    upload_id=upload_id,
                )
            except FileStorageError:
                logger.exception(
                    "Failed to abort OSS multipart upload: %s",
                    storage_key,
                )
            raise

    async def delete(
        self,
        storage_key: str,
    ) -> None:
        await self._call_oss(
            self._client.delete_object,
            oss.DeleteObjectRequest(
                bucket=self._bucket,
                key=storage_key,
            ),
            operation="delete_object",
        )

    async def exists(
        self,
        storage_key: str,
    ) -> bool:
        return await self._call_oss(
            self._client.is_object_exist,
            bucket=self._bucket,
            key=storage_key,
            operation="is_object_exist",
        )

    async def create_signed_url(
        self,
        storage_key: str,
        *,
        expires_seconds: int,
    ) -> str:
        if expires_seconds <= 0:
            raise ValueError(
                "expires_seconds must be positive."
            )

        result = await self._call_oss(
            self._client.presign,
            oss.GetObjectRequest(
                bucket=self._bucket,
                key=storage_key,
            ),
            expires=timedelta(
                seconds=expires_seconds
            ),
            operation="presign_get_object",
        )

        return result.url