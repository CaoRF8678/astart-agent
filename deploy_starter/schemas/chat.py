from pydantic import BaseModel, Field
from typing import Literal

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1,description="The message sent by the user.")
    session_id: str | None = Field(default=None, description="The unique identifier for the chat session.")
    user_id: str = Field(..., min_length=1,description="The unique identifier for the user.")

#两个Class之间留两个空行
class TokenUsage(BaseModel):
    input_tokens: int = Field( ge=0, description="The number of tokens used in the input message.")
    output_tokens: int = Field(ge=0, description="The number of tokens used in the output message.")
    total_tokens: int = Field(ge =0, description="The total number of tokens used.")

class ChatResponse(BaseModel):
    request_id: str = Field(..., description="The unique identifier for the request.")
    message_id: str = Field(..., description="The unique identifier for the message.")
    session_id: str = Field(..., description="The unique identifier for the chat session.")
    status: Literal["completed","failed"]
    answer: str
    usage: TokenUsage | None = None

