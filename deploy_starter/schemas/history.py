from pydantic import BaseModel, Field
from typing import Literal

class HistoryMessage(BaseModel):
    message_id: str = Field(..., min_length=1, description="A unique identifier for the message.")
    role: Literal["user", "assistant"] = Field(..., description="The role of the message sender.")
    content: str = Field(..., min_length=1, description="The content of the message.")


class HistoryResponse(BaseModel):
    session_id: str = Field(..., min_length=1, description="The identifier for the session.")
    user_id: str = Field(..., min_length=1, description="The identifier for the user.")
    messages: list[HistoryMessage]
    count: int = Field(..., ge=0, description="The number of messages returned.")

