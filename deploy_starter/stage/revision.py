"""
输入：
LearningBrief
ResearchResult
CourseOutline V1
CritiqueResult
输出：
CourseOutline V2
"""

from schemas.intake import LearningBriefContent
from schemas.generation import ResearchResult
from schemas.course import CourseOutline
from schemas.generation import CritiqueResult
from stage.base import StructuredStageRunner

REVISION_SYSTEM_PROMPT = """
你是 Astart Course Generation Workflow 中的 Revision Stage。

你的职责：
根据 LearningBrief、ResearchResult、CourseOutline V1
和 CritiqueResult，对课程大纲进行修订，
输出 CourseOutline V2。

必须遵守：

1. 优先针对 CritiqueResult 中的 CritiqueIssue 修改。
2. 保留 CourseOutline V1 中合理的部分。
3. 不因为局部问题而无必要地推翻整体课程结构。
4. 修订后仍必须遵守 LearningBrief。
5. 修订后仍必须遵守 ResearchResult 中的知识体系、
   learning_sequence 和 treatment。
6. 不额外扩展用户没有要求的大量主题。
7. 如果 CritiqueResult.passed = True，
   仍进行一次轻量修订，
   主要做一致性、结构和表达优化，
   不进行大规模重构。
8. 不虚构用户未提供的信息。
"""

async def run_revision(
    *,
    runner: StructuredStageRunner,
    brief: LearningBriefContent,
    research_result: ResearchResult,
    outline_v1: CourseOutline,
    critique_result:CritiqueResult,
) -> CourseOutline:
    payload = {
        "learning_brief": brief.model_dump(
            mode="json"
        ),
        "research_result": research_result.model_dump(
            mode = "json"
        ),
        "course_outline": outline_v1.model_dump(
            mode = "json"
        ),
        "critique_result":critique_result.model_dump(
            mode = "json"
        ),
    }

    revision =  await runner.run(
        name = "CourseRevision",
        system_prompt = REVISION_SYSTEM_PROMPT,
        payload = payload,
        structured_model = CourseOutline,
    )
    return revision