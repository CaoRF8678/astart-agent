from typing import Any

from agentscope_runtime.engine.schemas.agent_schemas import (
    Message,
    TextContent,
)

from schemas.history import (
    HistoryMessage,
    HistoryResponse,
)


class HistoryServiceError(Exception):
    """
    History service execution error.
    """

    def __init__(
        self,
        code: str,
        message: str,
    ):
        super().__init__(message)

        self.code = code
        self.message = message



def convert_message(
    raw_message: Message | dict[str, Any],
) -> HistoryMessage | None:
    """
    Convert AgentScope Message into Astart HistoryMessage.

    Args:
        raw_message:
            AgentScope Message object or dict.

    Returns:
        HistoryMessage if the message is a visible chat message,
        otherwise None.
    """

    # 1. Normalize input
    # dict -> Message
    if isinstance(raw_message, dict):
        message = Message.model_validate(raw_message)

    else:
        message = raw_message


    # 2. Only keep normal message type
    #
    # Exclude:
    # reasoning
    # function_call
    # tool message
    #
    if message.type != "message":
        return None


    # 3. Only expose user/assistant messages
    if message.role not in [
        "user",
        "assistant",
    ]:
        return None


    # 4. Content empty
    if not message.content:
        return None


    # 5. Extract all text content

    text_parts = []

    for content in message.content:

        if isinstance(
            content,
            TextContent,
        ):

            if content.text:
                text_parts.append(
                    content.text
                )


    text = "".join(text_parts).strip()


    # 6. No text
    if not text:
        return None


    # 7. Convert to Astart schema

    return HistoryMessage(
        message_id=message.id,

        # AgentRole may be Enum
        # Convert to string
        role=(
            message.role.value
            if hasattr(
                message.role,
                "value",
            )
            else str(message.role)
        ),

        content=text,
    )



async def get_history(
    session_service,
    user_id: str,
    session_id: str,
) -> HistoryResponse:
    """
    Get chat history by user_id and session_id.
    """

    # 1. Get user's sessions

    session_list = await session_service.list_sessions(
        user_id,
    )


    # 2. Check session existence

    session_exists = any(
        session.id == session_id
        for session in session_list
    )


    if not session_exists:

        raise HistoryServiceError(
            code="SESSION_NOT_FOUND",
            message=(
                "The specified session does not exist."
            ),
        )


    # 3. Get full session
    #
    # list_sessions()
    # only returns metadata
    #
    # get_session()
    # returns messages

    session = await session_service.get_session(
        user_id,
        session_id,
    )


    if session is None:

        raise HistoryServiceError(
            code="SESSION_NOT_FOUND",
            message=(
                "The specified session does not exist."
            ),
        )


    # 4. Convert messages

    history_messages = []


    for raw_message in session.messages:

        history_message = convert_message(
            raw_message
        )


        if history_message is not None:

            history_messages.append(
                history_message
            )


    # 5. Build response

    return HistoryResponse(

        session_id=session_id,

        user_id=user_id,

        messages=history_messages,

        count=len(history_messages),
    )