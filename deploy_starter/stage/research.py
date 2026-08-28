
from schemas.intake import LearningBriefContent
from schemas.generation import ResearchResult,RetrievalQueryPlan
from stage.base import StructuredStageRunner
RESEARCH_SYSTEM_PROMPT = """
你是 Astart Course Generation Workflow 中的 Research Stage。

你的职责：
研究完成当前学习目标所需要的合理知识体系，
并根据用户的真实情况制定个性化的课程研究方案。

必须遵守：

1. 根据 prior_knowledge 调整知识深度。
2. 根据 target_outcome 调整学习内容。
3. 根据 focus_areas 调整重点。
4. 根据 time_budget_minutes 决定各知识点采用：
   deep / standard / compressed / skip。
5. 用户未提供的信息不能虚构。
6. 未知不等于零基础。
7. 如果没有明确时间预算，不得虚构用户的时间限制。
8. 当前 V1 没有联网搜索能力，
   sources 和 evidence 必须为空列表。
9. 严禁伪造论文、URL、官方文档或其他来源。
"""

RETRIEVAL_QUERY_SYSTEM_PROMPT = """
你是 Astart Course Research 的检索查询规划器。

你的任务：
根据 LearningBrief 生成 2～5 条用于课程资料向量检索的查询。

要求：
1. 查询应覆盖用户核心 goal。
2. 优先覆盖 target_outcome 与 focus_areas。
3. 必要时加入完成目标所需的 prerequisite 查询。
4. 查询必须简洁、自包含，适合语义向量检索。
5. 不要生成答案，只生成 retrieval query。
6. 不得虚构 LearningBrief 中不存在的用户背景。
7. 多条查询不要只是同义改写，应覆盖不同检索方向。
"""

def normalize_queries(
    *,
    goal: str,
    planned: list[str],
) -> list[str]:
    result = []
    seen = set()

    for raw in [goal, *planned]:
        query = raw.strip()

        if not query:
            continue

        normalized_key = query.casefold()

        if normalized_key in seen:
            continue

        seen.add(normalized_key)
        result.append(query)

        if len(result) >= 5:
            break

    return result

def calculate_time_budget_minutes(
    brief: LearningBriefContent,
) -> int | None:

    if (
        brief.weekly_hours is None
        or brief.expected_duration_weeks is None
    ):
        return None

    return round(
        brief.weekly_hours * brief.expected_duration_weeks *60
    )

async def run_research(
    *,
    runner: StructuredStageRunner,
    brief: LearningBriefContent,
) -> ResearchResult:

    time_budget_minutes = (
        calculate_time_budget_minutes(brief)
    )

    payload = {
        "learning_brief": brief.model_dump(
            mode="json"
        ),
        "time_budget_minutes": (
            time_budget_minutes
        ),
    }

    result = await runner.run(   #result 的结构就是ResearchResult
        name="CourseResearch",
        system_prompt=RESEARCH_SYSTEM_PROMPT,
        payload=payload,
        structured_model=ResearchResult,
    )
    result = result.model_copy(
        update = {
            "time_budget_minutes":time_budget_minutes,
            "sources":[],
            "evidence":[],
        }
    )
    return result

async def plan_retrieval_queries(
    *,
    runner: StructuredStageRunner,
    brief: LearningBriefContent,
) -> list[str]:

    plan = await runner.run(
        name="RetrievalQueryPlanner",
        system_prompt=RETRIEVAL_QUERY_SYSTEM_PROMPT,
        payload={
            "learning_brief": brief.model_dump(
                mode="json"
            ),
        },
        structured_model=RetrievalQueryPlan,
    )

    return normalize_queries(
        goal=brief.goal,
        planned=plan.queries,
    )