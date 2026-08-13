from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str = Field(
        ...,
        min_length=1,
        description="The machine-readable error code.",
    )
    message: str = Field(
        ...,
        min_length=1,
        description="The human-readable error message.",
    )


class ErrorResponse(BaseModel):
    request_id: str = Field(
        ...,
        min_length=1,
        description="The unique identifier for the request.",
    )
    error: ErrorDetail