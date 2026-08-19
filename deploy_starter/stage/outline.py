#输入 LearningBrief + ResearchResult
#输出 CourseOutline V1

from schemas.intake import LearningBriefContent
from schemas.generation import ResearchResult
from schemas.course import CourseOutline
from stage.base import StructuredStageRunner

OUTLINE_SYSTEM_PROMPT = """
你是 Astart Course Generation Workflow 中的 Outline Stage。

你的职责：
根据 LearningBrief 与 ResearchResult，
生成结构清晰、个性化并且可执行的 CourseOutline。

ResearchResult 是本阶段制定课程结构的重要依据，
不要脱离 ResearchResult 重新设计另一套知识体系。

必须遵守：

1. 根据 LearningBrief 中的 prior_knowledge、
   target_outcome、focus_areas 保持课程个性化。

2. 必须遵循 ResearchResult 中 topics 的 treatment：

   deep
   → 作为重点内容，安排更充分的学习深度和内容。

   standard
   → 按正常深度安排。

   compressed
   → 压缩内容，只保留完成学习目标所需要的关键知识。

   skip
   → 原则上不得作为课程主体内容。

3. 必须遵循 ResearchResult 中的 learning_sequence，
   保持合理的知识依赖和学习顺序。

4. 用户未提供的信息不得虚构。
   未知不等于零基础。

5. 每个 Section 的 estimated_minutes
   表示学习该 Section 内容本身所需要的预计时间。

6. 如果 ResearchResult 中存在 time_budget_minutes，
   整门课程的预计学习时间应尽量与其匹配，
   但该时间预算属于 Soft Constraint（软约束），
   不应为了严格满足时间而破坏必要的知识结构。

7. 如果没有明确 time_budget_minutes，
   不得虚构用户的总学习时间预算。
"""


async def run_outline(
    *,
    runner:StructuredStageRunner,
    brief:LearningBriefContent,
    research_result:ResearchResult,
) -> CourseOutline:

    payload = {
        "learning_brief": brief.model_dump(
            mode="json"
        ),
        "research_result": research_result.model_dump(
            mode = "json"
        ),
    }

    return await runner.run(
        name="CourseOutline",
        system_prompt=OUTLINE_SYSTEM_PROMPT,
        payload=payload,
        structured_model=CourseOutline,
    )