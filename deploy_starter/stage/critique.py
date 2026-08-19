"""
输入：

LearningBrief
ResearchResult
CourseOutline V1
检查：

coverage
ordering
difficulty
personalization
time_budget
redundancy
objective
输出：

CritiqueResult
"""

CRITIQUE_SYSTEM_PROMPT = """
你是 Astart Course Generation Workflow 中的 Critique Stage。

你的职责：
根据 LearningBrief、ResearchResult 和 CourseOutline V1，
对当前课程大纲进行结构化审查。

必须重点检查：

1. coverage
   课程内容是否覆盖完成学习目标所需要的关键知识。

2. ordering
   Module、Chapter、Section 的学习顺序是否符合知识依赖关系。

3. difficulty
   课程难度是否与用户的 prior_knowledge 相匹配。

4. personalization
   是否真正体现 target_outcome、focus_areas、
   prior_knowledge 等个性化信息。

5. time_budget
   如果存在 time_budget_minutes，
   课程总体学习时间是否合理匹配该预算。
   时间预算属于 Soft Constraint（软约束）。

6. redundancy
   是否存在重复、无必要扩展或与目标关系较弱的内容。

7. objective
   课程结构是否能够有效支持用户最终学习目标。

对于发现的问题：
- 给出 category
- 给出 severity：high / medium / low
- 尽可能指出 location
- 清楚描述问题
- 给出具体修改建议

overall_score 必须在 0～100。

passed 字段仍需返回，
但程序会根据 overall_score 和 high severity issue
重新计算最终 passed，因此不要依赖 passed 控制其他字段。

revision_summary 应简洁总结下一阶段 Revision
最需要修改的内容。

不要虚构用户没有提供的信息。
"""

from schemas.intake import LearningBriefContent
from schemas.generation import ResearchResult
from schemas.course import CourseOutline
from schemas.generation import CritiqueResult
from stage.base import StructuredStageRunner

def normalize_critique(   #规范化评论
    critique: CritiqueResult,
) -> CritiqueResult:

    has_high_issue = any(
        issue.severity == "high"
        for issue in critique.issues
    )

    passed = (
        critique.overall_score >= 85
        and not has_high_issue
    )

    return critique.model_copy(
        update={
            "passed": passed,
        }
    )


async def run_critique(
    *,
    runner: StructuredStageRunner,
    brief: LearningBriefContent,
    research_result: ResearchResult,
    outline_v1: CourseOutline,
) -> CritiqueResult:
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
    }

    critique =  await runner.run(
        name = "CourseCritique",
        system_prompt = CRITIQUE_SYSTEM_PROMPT,
        payload = payload,
        structured_model = CritiqueResult,
    )
    return normalize_critique(critique)