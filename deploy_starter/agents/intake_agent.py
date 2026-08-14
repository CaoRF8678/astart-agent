import json

from agentscope.agent import ReActAgent
from agentscope.memory import InMemoryMemory
from agentscope.message import Msg

from core.model_factory import create_chat_model_and_formatter
from schemas.intake import IntakeSession, IntakeTurnDecision


INTAKE_SYSTEM_PROMPT = """
你是 Astart 的学习目标引导 Agent。

你的职责：
通过自然的逐步询问，收集生成个性化学习方案所需的关键信息，
并将用户明确提供的信息整理为结构化学习需求。

必须遵守：
1. 只提取用户明确表达的信息，不能虚构。
2. 不要把“未知”当成“零基础”。
3. 当前 Draft 已经存在的信息默认保留。
4. asked_fields 中已经问过的内容原则上不要重复询问。

信息询问优先级：
优先获取 goal / prior_knowledge / target_outcome / 时间约束。
其次获取 application_scenario / focus_areas / learning_preferences / constraints。

提问规则：
1. 通常一次提出 2～4 个高度相关的问题。
2. 当学习主题复杂、当前信息明显不足时，可以增加到 5～6 个。
3. 用户可以跳过不确定或暂时不想回答的问题。
4. 不要为了填满所有字段而机械追问。

完成规则：
1. 用户明确要求直接生成时，只要 goal 已明确，可以建议完成。
2. 当已有信息足以支持后续生成合理的个性化学习方案时，可以建议完成。
"""



class IntakeAnalyzer:
    def __init__(self):
        self.model, self.formatter = create_chat_model_and_formatter(
            stream=False,
            generate_kwargs = {
                "extra_body": {
                    "thinking": {
                        "type":"disabled",
                    }
                }
            },
        )

    async def analyze_turn(
        self,
        session: IntakeSession,
        user_message: str,
    ) -> IntakeTurnDecision:

        payload = {
            "current_draft": session.brief_draft.model_dump(),
            "asked_fields": session.asked_fields,
            "round_count": session.round_count,
            "max_rounds": 6,
            "user_message": user_message,
        }
        payload_text = json.dumps(
            payload,
            ensure_ascii= False,
        )
        agent = ReActAgent(
            name="Astart",
            model=self.model,
            sys_prompt=INTAKE_SYSTEM_PROMPT,
            formatter=self.formatter,
            memory=InMemoryMemory(),
        )

        result = await agent(
            Msg(
                name = "user",
                role = "user",
                content = payload_text,
            ),
            structured_model=IntakeTurnDecision,
        )

        decision = IntakeTurnDecision.model_validate(   #格式检验的函数
            result.metadata
        )

        return decision