"""Capability metadata for the unified football assistant."""
from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class AgentCapability:
    code: str
    name: str
    description: str
    memory_scope: str = "user"
    draft_enabled: bool = True
    tool_modules: list[str] = field(default_factory=list)
    quick_questions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


AGENT_CAPABILITIES: dict[str, AgentCapability] = {
    "auto": AgentCapability(
        code="auto",
        name="自动",
        description="自动判断问题类型，并选择合适能力。",
        tool_modules=["academic", "rag", "study", "document", "emotion", "map", "data_analysis", "code_review", "github"],
        quick_questions=["查询所有学生", "总结这段文字", "分析项目 E:\\student", "查看 GitHub 仓库"],
    ),
    "academic_ops": AgentCapability(
        code="academic_ops",
        name="教务助手",
        description="统一查询和操作权限范围内的教务数据，写操作会先确认。",
        tool_modules=["academic"],
        quick_questions=["查询所有学生", "我的成绩怎么样", "今天有什么课", "给学生吴浩发邮件"],
    ),
    "rag": AgentCapability(
        code="rag",
        name="RAG知识问答",
        description="面向综合知识库的检索问答。",
        tool_modules=["rag"],
        quick_questions=["十常侍都是谁", "总结三国演义第一回"],
    ),
    "search": AgentCapability(
        code="search",
        name="搜索引擎",
        description="联网搜索实时资讯、外部资料和来源链接，适合最新消息、新闻、政策、版本和资料查证。",
        tool_modules=["search"],
        quick_questions=["搜索今天 AI 有什么新闻", "联网查 DeepSeek 最新消息", "帮我查 LangGraph 最新文档", "搜索一下深圳大学近期活动"],
    ),
    "study": AgentCapability(
        code="study",
        name="学习辅导",
        description="课程知识讲解、题目解析、复习计划和诗词鉴赏。",
        tool_modules=["study"],
        quick_questions=["数据库事务隔离级别怎么理解", "帮我制定一周英语复习计划", "赏析一下《静夜思》"],
    ),
    "document": AgentCapability(
        code="document",
        name="文档处理",
        description="支持文本/文件总结、图片文字识别和英汉互译。",
        tool_modules=["document"],
        quick_questions=["总结这段文字", "识别图片里的文字", "把这段话翻译成英文"],
    ),
    "code_review": AgentCapability(
        code="code_review",
        name="编程助手",
        description="代码问答、代码生成、文件定位、代码解释和项目体检。",
        tool_modules=["code_review"],
        quick_questions=["分析项目 E:\\student", "学生新增接口在哪", "帮我写一个 FastAPI 上传接口", "解释 AIAssistant.vue"],
    ),
    "github": AgentCapability(
        code="github",
        name="GitHub助手",
        description="读取 GitHub 仓库、目录、issue、PR，并可确认后创建 issue。",
        tool_modules=["github"],
        quick_questions=["分析仓库 https://github.com/owner/repo", "查看这个仓库的 open issues", "创建一个 GitHub issue"],
    ),
    "emotion": AgentCapability(
        code="emotion",
        name="情绪陪伴",
        description="基于 CBT、压力应对、正念等框架提供专业心理支持；明显风险时可确认后提醒班主任/院系老师。",
        memory_scope="user_private",
        tool_modules=["emotion"],
        quick_questions=["我最近考试压力很大，给我专业建议", "我总是拖延和自责怎么办", "我有点撑不住了"],
    ),
    "map": AgentCapability(
        code="map",
        name="路线生活",
        description="规划公共交通和自驾路线，并搜索目的地附近吃喝玩乐。",
        tool_modules=["map"],
        quick_questions=["从石芽岭地铁站到深圳大学再到深圳人才公园", "深圳大学附近有什么吃喝玩乐", "从学校到火车站优先地铁"],
    ),
    "data_analysis": AgentCapability(
        code="data_analysis",
        name="数据分析",
        description="面向数据体检、统计分析和管理建议。",
        tool_modules=["data_analysis"],
        quick_questions=["系统还有哪些高危异常", "分析一下学生成绩趋势"],
    ),
    "worldcup": AgentCapability(
        code="worldcup",
        name="世界杯问答",
        description="世界杯知识、球队、球星、赛制问答。",
        tool_modules=["worldcup"],
        quick_questions=["2022世界杯冠军是谁", "世界杯小组赛规则是什么"],
    ),
    "ai_knowledge": AgentCapability(
        code="ai_knowledge",
        name="AI知识问答",
        description="LangChain、LangGraph、FastAPI、Dify、Python、Linux、SQL等技术问答。",
        tool_modules=["ai_knowledge"],
        quick_questions=["LangGraph和LangChain区别", "FastAPI常见面试题"],
    ),
}


def get_capability(code: str) -> AgentCapability | None:
    return AGENT_CAPABILITIES.get(code)


def list_capabilities() -> list[dict]:
    return [item.to_dict() for item in AGENT_CAPABILITIES.values()]
