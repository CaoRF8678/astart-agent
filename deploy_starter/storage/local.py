import asyncio
import os
import tempfile

from datetime import datetime, timezone
from pathlib import Path

from storage.base import (
    FileStorage,
    FileStorageError,
)


class LocalFileStorage(FileStorage):
    """
    Local filesystem implementation of FileStorage.

    Files are stored using:

        YYYY/MM/file_<uuid>.<ext>

    Example:

        data/uploads/2026/08/file_abc123.pdf
    """

    def __init__(
        self,
        root_dir: str = "data/uploads",
    ) -> None:
        try:
            self.root_dir = Path(
                root_dir
            ).resolve()

            self.root_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

        except OSError as exc:
            raise FileStorageError(
                "Failed to initialize local file storage."
            ) from exc

    def _resolve_storage_key(
        self,
        storage_key: str,
    ) -> Path:
        """
        Resolve storage key and prevent path traversal.
        """

        candidate = (
            self.root_dir / storage_key
        ).resolve()

        try:
            candidate.relative_to(
                self.root_dir
            )

        except ValueError as exc:
            raise FileStorageError(
                "Invalid storage key."
            ) from exc

        return candidate

    @staticmethod
    def _write_atomic(
        path: Path,
        data: bytes,
    ) -> None:
        """
        Atomically write data to disk.

        Data is first written to a temporary file and then
        moved to the final location using os.replace().
        """

        path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temp_path: str | None = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=path.parent,
                prefix=".upload_",
                delete=False,
            ) as temp_file:

                temp_path = temp_file.name

                temp_file.write(data)

                temp_file.flush()

                os.fsync(
                    temp_file.fileno()
                )

            os.replace(
                temp_path,
                path,
            )

            temp_path = None

        except OSError as exc:
            raise FileStorageError(
                "Failed to write file to local storage."
            ) from exc

        finally:
            if temp_path is not None:
                try:
                    Path(temp_path).unlink(
                        missing_ok=True
                    )
                except OSError:
                    pass

    async def save(
        self,
        *,
        file_id: str,
        filename: str,
        data: bytes,
    ) -> str:
        suffix = (
            Path(filename)
            .suffix
            .lower()
        )

        now = datetime.now(
            timezone.utc
        )

        storage_key = (
            f"{now.year:04d}/"
            f"{now.month:02d}/"
            f"{file_id}{suffix}"
        )

        path = self._resolve_storage_key(
            storage_key
        )

        await asyncio.to_thread(
            self._write_atomic,
            path,
            data,
        )

        return storage_key

    async def delete(
        self,
        storage_key: str,
    ) -> None:
        path = self._resolve_storage_key(
            storage_key
        )

        try:
            await asyncio.to_thread(
                path.unlink,
                missing_ok=True,
            )

        except OSError as exc:
            raise FileStorageError(
                "Failed to delete file."
            ) from exc

    async def exists(
        self,
        storage_key: str,
    ) -> bool:
        path = self._resolve_storage_key(
            storage_key
        )

        try:
            return await asyncio.to_thread(
                path.is_file
            )

        except OSError as exc:
            raise FileStorageError(
                "Failed to check file existence."
            ) from exc