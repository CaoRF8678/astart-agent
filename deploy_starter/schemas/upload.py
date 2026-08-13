from typing import Literal

from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    file_id: str = Field(
        ...,
        min_length=1,
        description="The unique identifier of the uploaded file.",
    )

    filename: str = Field(
        ...,
        min_length=1,
        description="The sanitized original filename.",
    )

    content_type: str = Field(
        ...,
        min_length=1,
        description="The MIME type of the uploaded file.",
    )

    size: int = Field(
        ...,
        ge=1,
        description="The file size in bytes.",
    )

    sha256: str = Field(
        ...,
        pattern=r"^[0-9a-f]{64}$",
        description="The SHA-256 digest of the uploaded file.",
    )

    session_id: str | None = Field(
        default=None,
        description="The session associated with the uploaded file.",
    )

    status: Literal["uploaded"] = Field(
        default="uploaded",
        description="The current upload status.",
    )