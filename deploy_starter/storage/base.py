from abc import ABC, abstractmethod


class FileStorageError(Exception):
    """Base exception for file storage operations."""


class FileStorage(ABC):
    """
    Abstract file storage backend.

    Implementations may store files on:
    - local disk
    - Alibaba Cloud OSS
    - Amazon S3
    - MinIO
    """

    @abstractmethod
    async def save(
        self,
        *,
        file_id: str,
        filename: str,
        data: bytes,
    ) -> str:
        """
        Save a file.

        Returns:
            Internal storage key.

        Raises:
            FileStorageError:
                If the file cannot be stored.
        """
        raise NotImplementedError

    @abstractmethod
    async def delete(
        self,
        storage_key: str,
    ) -> None:
        """
        Delete a file.

        The operation should be idempotent.
        """
        raise NotImplementedError

    @abstractmethod
    async def exists(
        self,
        storage_key: str,
    ) -> bool:
        """Check whether a stored file exists."""
        raise NotImplementedError