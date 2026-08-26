import hashlib
import io
import uuid
import zipfile
import asyncio
import logging

from pathlib import Path

from schemas.upload import UploadResponse
from storage.base import (
    FileStorage,
    FileStorageError,
)

from ingestion.errors import (
    DocumentParseError,
)
from ingestion.parsers import get_parser
from ingestion.types import ParsedBlock

logger = logging.getLogger(__name__)

ALLOWED_FILE_TYPES = {
    ".txt": {
        "text/plain",
    },

    ".md": {
        "text/markdown",
        "text/plain",
    },

    ".pdf": {
        "application/pdf",
    },

    ".docx": {
        (
            "application/vnd.openxmlformats-officedocument."
            "wordprocessingml.document"
        ),
    },
    ".pptx": {
        (
            "application/vnd.openxmlformats-officedocument."
            "presentationml.presentation"
        ),
    },
}


GENERIC_CONTENT_TYPES = {
    "application/octet-stream",
}


MAX_FILE_SIZE = (
    20 * 1024 * 1024
)


MAX_FILENAME_LENGTH = 255


MAX_OPENXML_ENTRIES = 5000

MAX_OPENXML_UNCOMPRESSED_SIZE = (
    200 * 1024 * 1024
)


def _validate_openxml_package(
    data: bytes,
    *,
    required_entries: set[str],
    document_name: str,
) -> None:
    try:
        with zipfile.ZipFile(
            io.BytesIO(data),
            mode="r",
        ) as archive:

            entries = archive.infolist()

            if (
                len(entries)
                > MAX_OPENXML_ENTRIES
            ):
                raise UploadServiceError(
                    code="INVALID_FILE_CONTENT",
                    message=(
                        f"The {document_name} file "
                        "contains too many "
                        "archive entries."
                    ),
                )

            total_uncompressed_size = sum(
                entry.file_size
                for entry in entries
            )

            if (
                total_uncompressed_size
                > MAX_OPENXML_UNCOMPRESSED_SIZE
            ):
                raise UploadServiceError(
                    code="INVALID_FILE_CONTENT",
                    message=(
                        f"The {document_name} archive "
                        "is unreasonably large."
                    ),
                )

            names = {
                entry.filename
                for entry in entries
            }

            if not required_entries.issubset(
                names
            ):
                raise UploadServiceError(
                    code="INVALID_FILE_CONTENT",
                    message=(
                        "The uploaded file is not a "
                        f"valid {document_name} document."
                    ),
                )

    except zipfile.BadZipFile as exc:
        raise UploadServiceError(
            code="INVALID_FILE_CONTENT",
            message=(
                "The uploaded file is not a "
                f"valid {document_name} document."
            ),
        ) from exc

class UploadServiceError(Exception):
    """
    Business exception raised by UploadService.
    """

    def __init__(
        self,
        code: str,
        message: str,
    ) -> None:

        super().__init__(
            message
        )

        self.code = code
        self.message = message


def sanitize_filename(
    filename: str | None,
) -> str:
    """
    Sanitize a client supplied filename.

    Removes directory components and rejects
    invalid filenames.
    """

    if not filename:
        raise UploadServiceError(
            code="INVALID_FILENAME",
            message="Filename must not be empty.",
        )

    # Normalize Windows and Unix path separators.
    sanitized = (
        filename
        .replace("\\", "/")
        .split("/")[-1]
        .strip()
    )

    if (
        not sanitized
        or sanitized in {".", ".."}
    ):
        raise UploadServiceError(
            code="INVALID_FILENAME",
            message="The filename is invalid.",
        )

    if len(sanitized) > MAX_FILENAME_LENGTH:
        raise UploadServiceError(
            code="INVALID_FILENAME",
            message="The filename is too long.",
        )

    # Reject control characters.
    if any(
        ord(char) < 32
        for char in sanitized
    ):
        raise UploadServiceError(
            code="INVALID_FILENAME",
            message="The filename contains invalid characters.",
        )

    return sanitized


def validate_file_metadata(
    filename: str,
    content_type: str | None,
) -> str:
    """
    Validate extension and MIME type.

    Returns:
        Normalized file suffix.
    """

    suffix = (
        Path(filename)
        .suffix
        .lower()
    )

    allowed_types = (
        ALLOWED_FILE_TYPES.get(
            suffix
        )
    )

    if allowed_types is None:
        raise UploadServiceError(
            code="UNSUPPORTED_FILE_TYPE",
            message=(
                "The uploaded file type "
                "is not supported."
            ),
        )

    normalized_content_type = (
        content_type
        or "application/octet-stream"
    ).lower()

    if (
        normalized_content_type
        not in allowed_types
        and normalized_content_type
        not in GENERIC_CONTENT_TYPES
    ):
        raise UploadServiceError(
            code="UNSUPPORTED_FILE_TYPE",
            message=(
                "The uploaded file MIME type "
                "does not match the file extension."
            ),
        )

    return suffix


def _validate_pdf(
    data: bytes,
) -> None:
    """
    Perform basic PDF signature validation.
    """

    if not data.startswith(
        b"%PDF-"
    ):
        raise UploadServiceError(
            code="INVALID_FILE_CONTENT",
            message=(
                "The file content is not "
                "a valid PDF document."
            ),
        )


def _validate_text(
    data: bytes,
) -> None:
    """
    Require uploaded TXT/Markdown files
    to contain UTF-8 text.
    """

    if b"\x00" in data:
        raise UploadServiceError(
            code="INVALID_FILE_CONTENT",
            message=(
                "The text file contains "
                "binary content."
            ),
        )

    try:
        data.decode(
            "utf-8-sig"
        )

    except UnicodeDecodeError as exc:
        raise UploadServiceError(
            code="INVALID_FILE_CONTENT",
            message=(
                "Text files must use "
                "UTF-8 encoding."
            ),
        ) from exc

def _validate_docx(
    data: bytes,
) -> None:
    _validate_openxml_package(
        data,
        required_entries={
            "[Content_Types].xml",
            "word/document.xml",
        },
        document_name="DOCX",
    )

def _validate_pptx(
    data: bytes,
) -> None:
    _validate_openxml_package(
        data,
        required_entries={
            "[Content_Types].xml",
            "ppt/presentation.xml",
        },
        document_name="PPTX",
    )


def validate_file_content(
    *,
    data: bytes,
    suffix: str,
) -> tuple[int, str]:
    """
    Validate file content and calculate SHA-256.

    Returns:
        (file_size, sha256)
    """

    size = len(data)

    if size == 0:
        raise UploadServiceError(
            code="EMPTY_FILE",
            message=(
                "The uploaded file is empty."
            ),
        )

    if size > MAX_FILE_SIZE:
        raise UploadServiceError(
            code="FILE_TOO_LARGE",
            message=(
                "The uploaded file exceeds "
                "the maximum allowed size."
            ),
        )

    if suffix in {
        ".txt",
        ".md",
    }:
        _validate_text(
            data
        )

    elif suffix == ".pdf":
        _validate_pdf(
            data
        )

    elif suffix == ".docx":
        _validate_docx(
            data
        )
    elif suffix == ".pptx":
        _validate_pptx(data)

    else:
        # Defensive fallback.
        raise UploadServiceError(
            code="UNSUPPORTED_FILE_TYPE",
            message=(
                "The uploaded file type "
                "is not supported."
            ),
        )

    sha256_hash = hashlib.sha256(
        data
    ).hexdigest()

    return (
        size,
        sha256_hash,
    )


async def validate_session_access(
    *,
    session_service,
    user_id: str,
    session_id: str | None,
) -> None:
    """
    Verify that session_id belongs to user_id.

    No validation is needed when session_id is None.
    """

    if session_id is None:
        return

    if session_service is None:
        raise UploadServiceError(
            code="SERVICE_NOT_READY",
            message=(
                "Session service "
                "is not initialized."
            ),
        )

    sessions = await (
        session_service.list_sessions(
            user_id
        )
    )

    session_exists = any(
        session.id == session_id
        for session in sessions
    )

    if not session_exists:
        raise UploadServiceError(
            code="SESSION_NOT_FOUND",
            message=(
                "The specified session "
                "does not exist."
            ),
        )


async def upload_file(
    *,
    storage: FileStorage,
    filename: str | None,
    content_type: str | None,
    data: bytes,
    user_id: str,
    session_id: str | None,
    session_service=None,
) -> UploadResponse:
    """
    Validate and persist an uploaded file.
    """

    normalized_user_id = (
        user_id.strip()
    )

    if not normalized_user_id:
        raise UploadServiceError(
            code="INVALID_USER_ID",
            message=(
                "User ID must not be empty."
            ),
        )

    normalized_session_id = (
        session_id.strip()
        if session_id
        else None
    )

    safe_filename = sanitize_filename(
        filename
    )

    suffix = validate_file_metadata(
        filename=safe_filename,
        content_type=content_type,
    )

    size, sha256_hash = (
        validate_file_content(
            data=data,
            suffix=suffix,
        )
    )

    await validate_session_access(
        session_service=session_service,
        user_id=normalized_user_id,
        session_id=normalized_session_id,
    )

    file_id = (
        f"file_{uuid.uuid4().hex}"
    )

    try:
        storage_key = (
            await storage.save(
                file_id=file_id,
                filename=safe_filename,
                data=data,
            )
        )

    except FileStorageError as exc:
        raise UploadServiceError(
            code="FILE_STORAGE_FAILED",
            message=(
                "Failed to store "
                "the uploaded file."
            ),
        ) from exc

    # storage_key intentionally remains internal.
    #
    # PostgreSQL 阶段需要持久化：
    #
    # file_id
    # user_id
    # session_id
    # original_filename
    # content_type
    # size
    # sha256_hash
    # storage_key
    # status
    # created_at

    return UploadResponse(
        file_id=file_id,
        filename=safe_filename,
        content_type=(
            content_type
            or "application/octet-stream"
        ),
        size=size,
        sha256=sha256_hash,
        session_id=normalized_session_id,
        status="uploaded",
    )


