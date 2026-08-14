import uuid
from datetime import datetime, timedelta, timezone

from agents.intake_agent import IntakeAnalyzer
from schemas.intake import (
    IntakeRequest,
    IntakeResponse,
    IntakeSession,
    LearningBriefContent,
    LearningBriefDraft,
)


MAX_INTAKE_ROUNDS = 6
INTAKE_TIMEOUT_MINUTES = 10


class IntakeServiceError(Exception):
    """Intake 业务异常。"""

    def __init__(
        self,
        *,
        request_id: str,
        code: str,
        message: str,
    ):
        super().__init__(message)
        self.request_id = request_id
        self.code = code
        self.message = message


def merge_draft(
    current: LearningBriefDraft,
    patch: LearningBriefDraft,
) -> LearningBriefDraft:
    """把本轮新信息合并到已有 Draft 中。"""

    # 已有完整 Draft
    current_data = current.model_dump()

    # Patch 中只取非 None 字段
    patch_data = patch.model_dump(
        exclude_none=True,
    )

    # 新信息覆盖旧信息
    current_data.update(patch_data)

    return LearningBriefDraft.model_validate(
        current_data
    )


def merge_asked_fields(
    current: list[str],
    new_fields: list[str],
) -> list[str]:
    """合并已询问字段，去重并保留顺序。"""

    result = current.copy()

    for field in new_fields:
        if field not in result:
            result.append(field)

    return result


def format_questions(
    questions: list[str],
) -> str:
    """把问题列表转换成用户看到的文本。"""

    return "\n".join(
        f"{index}. {question}"
        for index, question in enumerate(
            questions,
            start=1,
        )
    )


class IntakeService:
    def __init__(
        self,
        analyzer: IntakeAnalyzer,
    ):
        self.analyzer = analyzer

        # 第一版暂时把 IntakeSession 存在 Python 内存中
        self._sessions: dict[
            tuple[str, str],
            IntakeSession,
        ] = {}

    def _session_key(
        self,
        user_id: str,
        session_id: str,
    ) -> tuple[str, str]:
        """生成 Session 在内存字典中的 Key。"""

        return user_id, session_id

    def _create_session(
        self,
        *,
        user_id: str,
        session_id: str,
    ) -> IntakeSession:
        """创建新的 IntakeSession 并保存到内存。"""

        session = IntakeSession(
            user_id=user_id,
            session_id=session_id,
            brief_draft=LearningBriefDraft(),
            last_activity_at=datetime.now(
                timezone.utc
            ),
        )

        self._sessions[
            self._session_key(
                user_id,
                session_id,
            )
        ] = session

        return session

    def _is_expired(
        self,
        session: IntakeSession,
    ) -> bool:
        """判断 Session 是否已经超过 10 分钟未活动。"""

        now = datetime.now(
            timezone.utc
        )

        return (
            now - session.last_activity_at
            > timedelta(
                minutes=INTAKE_TIMEOUT_MINUTES
            )
        )

    async def handle_turn(
        self,
        *,
        intake_request: IntakeRequest,
        request_id: str,
    ) -> IntakeResponse:
        """处理用户的一轮 Intake 输入。"""

        # 1. 获取或创建 Session
        if intake_request.session_id is None:
            session_id = str(
                uuid.uuid4()
            )

            session = self._create_session(
                user_id=intake_request.user_id,
                session_id=session_id,
            )

        else:
            session_id = intake_request.session_id

            session = self._sessions.get(
                self._session_key(
                    intake_request.user_id,
                    session_id,
                )
            )

            if session is None:
                raise IntakeServiceError(
                    request_id=request_id,
                    code="INTAKE_SESSION_NOT_FOUND",
                    message="Intake session not found.",
                )

        # 2. 检查已有 Session 状态
        if session.status == "completed":
            raise IntakeServiceError(
                request_id=request_id,
                code="INTAKE_SESSION_COMPLETED",
                message=(
                    "Intake session has already "
                    "been completed."
                ),
            )

        if session.status == "cancelled":
            raise IntakeServiceError(
                request_id=request_id,
                code="INTAKE_SESSION_CANCELLED",
                message=(
                    "Intake session has been cancelled."
                ),
            )

        if session.status == "expired":
            raise IntakeServiceError(
                request_id=request_id,
                code="INTAKE_SESSION_EXPIRED",
                message=(
                    "Intake session has expired."
                ),
            )

        # 3. 检查是否超时
        if self._is_expired(session):
            session.status = "expired"

            raise IntakeServiceError(
                request_id=request_id,
                code="INTAKE_SESSION_EXPIRED",
                message=(
                    "Intake session has expired."
                ),
            )

        # 4. 调用 Intake Agent 分析用户本轮输入
        try:
            decision = (
                await self.analyzer.analyze_turn(
                    session,
                    intake_request.message,
                )
            )

        except Exception as exc:
            print(
                    "\n[IntakeAnalyzer ERROR]",
                    type(exc).__name__,
                    repr(exc),
                    )
            raise IntakeServiceError(
                request_id=request_id,
                code="INTAKE_AGENT_FAILED",
                message=(
                    "Intake agent failed to "
                    "analyze the user message."
                ),
            ) from exc
        

        # 5. 合并本轮提取到的新信息
        session.brief_draft = merge_draft(
            session.brief_draft,
            decision.draft_patch,
        )

        now = datetime.now(
            timezone.utc
        )

        # 6. 判断是否已经有必需字段 goal
        has_goal = bool(
            session.brief_draft.goal
            and session.brief_draft.goal.strip()
        )

        # 已经发送过 6 组补充问题
        reached_limit = (
            session.round_count
            >= MAX_INTAKE_ROUNDS
        )

        # 7. 判断是否完成
        should_complete = (
            has_goal
            and (
                decision.ready_to_complete
                or reached_limit
            )
        )

        # 8A. 正常完成
        if should_complete:
            session.status = "completed"
            session.last_activity_at = now

            brief = (
                LearningBriefContent.model_validate(
                    session.brief_draft.model_dump()
                )
            )

            return IntakeResponse(
                request_id=request_id,
                session_id=session_id,
                status="completed",
                round_count=session.round_count,
                message="学习需求已经整理完成。",
                brief=brief,
            )

        # 8B. 已经达到 6 轮，但 goal 仍然没有获取到
        if reached_limit and not has_goal:
            session.last_activity_at = now

            return IntakeResponse(
                request_id=request_id,
                session_id=session_id,
                status="active",
                round_count=session.round_count,
                message=(
                    "还缺少必要信息："
                    "请明确你具体想学习什么主题。"
                    "明确后我会直接整理学习简报。"
                ),
                brief=None,
            )

        # Agent 不允许在没有 goal 时建议完成
        if (
            decision.ready_to_complete
            and not has_goal
        ):
            raise IntakeServiceError(
                request_id=request_id,
                code="INTAKE_INVALID_AGENT_OUTPUT",
                message=(
                    "Intake agent requested completion "
                    "before the learning goal was identified."
                ),
            )

        # 9. 如果继续提问，问题数量必须合法
        if not (
            2
            <= len(decision.questions)
            <= 6
        ):
            raise IntakeServiceError(
                request_id=request_id,
                code="INTAKE_INVALID_AGENT_OUTPUT",
                message=(
                    "Intake agent must return "
                    "2 to 6 questions when "
                    "more information is required."
                ),
            )

        # 10. 记录这一轮询问过哪些字段
        session.asked_fields = (
            merge_asked_fields(
                session.asked_fields,
                decision.question_fields,
            )
        )

        # 真正返回了一组问题，所以轮数 +1
        session.round_count += 1

        # 更新最后活动时间
        session.last_activity_at = now

        # 11. 返回给用户下一轮问题
        return IntakeResponse(
            request_id=request_id,
            session_id=session_id,
            status="active",
            round_count=session.round_count,
            message=format_questions(
                decision.questions
            ),
            brief=None,
        )