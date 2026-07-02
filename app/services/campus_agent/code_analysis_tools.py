"""Code analysis tools for the football assistant."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import settings
from app.exceptions import BusinessException
from app.services.campus_agent.llm_client import call_selected_llm, normalize_ollama_model

SKIP_DIRS = {
    ".git",
    ".idea",
    ".vscode",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "logs",
    "uploads",
}
SENSITIVE_NAMES = {".env", ".env.local", ".env.production", "id_rsa", "id_dsa"}
SENSITIVE_EXTENSIONS = {".pem", ".key", ".pfx", ".p12", ".crt"}
TEXT_EXTENSIONS = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".vue",
    ".json",
    ".toml",
    ".ini",
    ".yaml",
    ".yml",
    ".md",
    ".txt",
    ".sql",
    ".css",
    ".scss",
    ".html",
}
MAX_FILES = 450
MAX_TREE_ITEMS = 220
MAX_FILE_READ = 80_000
MAX_SNIPPET_CHARS = 6_000
REPORT_PREVIEW_CHARS = 1200

CODE_ANALYSIS_KEYWORDS = [
    "分析项目",
    "项目分析",
    "代码体检",
    "分析代码",
    "代码分析",
    "项目结构",
    "模块关系",
    "接口调用链",
    "表关系",
    "权限风险",
    "代码风险",
    "优化方向",
    "代码整改",
    "代码审查",
    "代码评审",
    "架构分析",
    "项目架构",
    "技术栈",
    "这个项目",
    "这个文件",
    "这个目录",
    "看看项目",
    "看看代码",
    "看看目录",
    "review code",
    "code review",
]

CODING_ASSISTANT_KEYWORDS = [
    "编程",
    "写代码",
    "生成代码",
    "代码生成",
    "实现一个",
    "帮我写",
    "解释代码",
    "这段代码",
    "代码什么意思",
    "报错",
    "bug",
    "debug",
    "单元测试",
    "接口怎么写",
    "组件怎么写",
    "SQL",
    "sql",
    "Python",
    "python",
    "FastAPI",
    "fastapi",
    "Vue",
    "vue",
    "TypeScript",
    "JavaScript",
    "Linux",
    "Docker",
    "LangChain",
    "LangGraph",
    "Dify",
]
LOCATE_CODE_KEYWORDS = ["在哪", "哪里", "找一下", "定位", "哪个文件", "入口", "文件位置", "调用链"]
MODIFY_CODE_KEYWORDS = ["修改", "改成", "改为", "删除这段", "替换", "重构", "帮我改", "直接改"]
GENERATE_CODE_KEYWORDS = ["写", "生成", "实现", "给我一个", "示例", "模板", "demo", "Demo"]

PATH_HINT_DIRS = ("app", "frontend", "docs", "tests", "alembic", "scripts", "tools", "文本")
PATH_STOPPERS = [
    " 分析",
    " 看看",
    " 代码",
    " 项目",
    " 文件",
    " 目录",
    " 的",
    "，",
    "。",
    "；",
    ";",
]


@dataclass
class FileSummary:
    path: str
    ext: str
    size: int
    role: str
    symbols: list[str]
    flags: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "ext": self.ext,
            "size": self.size,
            "role": self.role,
            "symbols": self.symbols,
            "flags": self.flags,
        }


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _allowed_roots() -> list[Path]:
    root = _project_root()
    roots = [
        root,
        Path(settings.ABS_UPLOAD_DIR).resolve(),
        (root / "文本").resolve(),
    ]
    for item in settings.CODE_ANALYSIS_ALLOWED_ROOTS or []:
        try:
            if item:
                roots.append(Path(item).expanduser().resolve())
        except Exception:
            continue
    return roots


def _is_sensitive(path: Path) -> bool:
    name = path.name.lower()
    return name in SENSITIVE_NAMES or path.suffix.lower() in SENSITIVE_EXTENSIONS or "secret" in name or "token" in name


def ensure_allowed_code_path(path_text: str | None) -> Path:
    raw = (path_text or "").strip().strip('"').strip("'")
    path = Path(raw or os.getcwd()).expanduser()
    if not path.is_absolute():
        path = (_project_root() / path).resolve()
    else:
        path = path.resolve()
    if not path.exists():
        raise BusinessException(message="路径不存在，请提供项目目录或代码文件路径。")
    roots = [root.resolve() for root in _allowed_roots()]
    if not any(path == root or root in path.parents for root in roots):
        allowed = "、".join(str(root) for root in roots)
        raise BusinessException(message=f"出于安全考虑，仅允许分析这些目录下的代码：{allowed}")
    return path


def extract_code_path(message: str) -> str | None:
    text = message or ""
    quoted = re.search(r"['\"]([A-Za-z]:\\[^'\"]+|/[^'\"]+)['\"]", text)
    if quoted:
        return quoted.group(1).strip()

    relative = re.search(rf"((?:{'|'.join(PATH_HINT_DIRS)})[/\\][^\s，。；;]+)", text)
    if relative:
        return relative.group(1)

    match = re.search(r"([A-Za-z]:\\[^\n\r，。；;]+|(?<!\w)/[^\n\r，。；;]+)", text)
    if match:
        value = match.group(1).strip().strip('"').strip("'")
        for stopper in PATH_STOPPERS:
            if stopper in value:
                value = value.split(stopper)[0].strip()
        return value
    return None


def should_use_code_analysis(message: str) -> bool:
    text = (message or "").strip()
    if not text:
        return False
    lowered = text.lower()
    if any(word in lowered for word in CODE_ANALYSIS_KEYWORDS):
        return True
    if any(word.lower() in lowered for word in CODING_ASSISTANT_KEYWORDS):
        return True
    if extract_code_path(text):
        return True
    if any(text.startswith(f"{name}/") or text.startswith(f"{name}\\") for name in PATH_HINT_DIRS):
        return True
    return False


def _coding_task_type(message: str) -> str:
    text = message or ""
    lowered = text.lower()
    if any(word in text for word in LOCATE_CODE_KEYWORDS):
        return "locate"
    if extract_code_path(text) and any(word in text for word in ["解释", "说明", "看一下", "这个文件", "这段"]):
        return "explain"
    if any(word in text for word in MODIFY_CODE_KEYWORDS):
        return "modify_plan"
    if any(word in text for word in GENERATE_CODE_KEYWORDS) or "code" in lowered:
        return "generate"
    return "qa"


def _looks_like_project_analysis(message: str) -> bool:
    text = message or ""
    if extract_code_path(text) and any(word in text for word in CODE_ANALYSIS_KEYWORDS + ["分析", "体检", "审查", "看看项目"]):
        return True
    return any(word in text for word in ["分析项目", "项目分析", "代码体检", "项目结构", "架构分析", "项目架构"])


def _iter_files(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    files: list[Path] = []
    for current, dirs, names in os.walk(root):
        dirs[:] = [item for item in dirs if item not in SKIP_DIRS and not item.startswith(".")]
        current_path = Path(current)
        for name in names:
            path = current_path / name
            if len(files) >= MAX_FILES:
                return files
            if path.suffix.lower() not in TEXT_EXTENSIONS:
                continue
            if _is_sensitive(path):
                files.append(path)
                continue
            try:
                if path.stat().st_size > MAX_FILE_READ:
                    files.append(path)
                    continue
            except OSError:
                continue
            files.append(path)
    return files


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _read_text(path: Path) -> str:
    if _is_sensitive(path):
        return ""
    if path.stat().st_size > MAX_FILE_READ:
        return ""
    for encoding in ("utf-8", "utf-8-sig", "gbk"):
        try:
            return path.read_text(encoding=encoding, errors="ignore")
        except Exception:
            continue
    return ""


def _file_role(path: Path, rel_path: str) -> str:
    p = rel_path.replace("\\", "/")
    name = path.name
    if p.startswith("app/api/"):
        return "后端接口层"
    if p.startswith("app/services/"):
        return "后端业务服务层"
    if p.startswith("app/models/"):
        return "数据库 ORM 模型"
    if p.startswith("app/schemas/"):
        return "接口数据结构"
    if p.startswith("frontend/src/views/"):
        return "前端页面"
    if p.startswith("frontend/src/components/"):
        return "前端组件"
    if p.startswith("frontend/src/api/"):
        return "前端 API 封装"
    if p.startswith("alembic/"):
        return "数据库迁移"
    if name in {"requirements.txt", "package.json", "vite.config.ts", "alembic.ini"}:
        return "项目配置/依赖"
    if p.startswith("docs/"):
        return "项目文档"
    if p.startswith("tests/"):
        return "测试代码"
    return "普通代码/资料"


def _extract_symbols(path: Path, text: str) -> list[str]:
    if not text:
        return []
    patterns = []
    if path.suffix == ".py":
        patterns = [r"^\s*class\s+([A-Za-z_][\w]*)", r"^\s*def\s+([A-Za-z_][\w]*)", r"@\w+\.((?:get|post|put|delete|patch))\("]
    elif path.suffix in {".ts", ".js", ".tsx", ".jsx", ".vue"}:
        patterns = [r"function\s+([A-Za-z_][\w]*)", r"const\s+([A-Za-z_][\w]*)\s*=", r"export\s+function\s+([A-Za-z_][\w]*)"]
    found: list[str] = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.MULTILINE):
            value = match.group(1)
            if value not in found:
                found.append(value)
            if len(found) >= 12:
                return found
    return found


def _flags(path: Path, text: str) -> list[str]:
    flags: list[str] = []
    if _is_sensitive(path):
        flags.append("敏感文件：未读取内容")
        return flags
    if path.stat().st_size > MAX_FILE_READ:
        flags.append("文件较大：未读取全文")
    if len(text) > 40_000:
        flags.append("文件较长")
    if "TODO" in text or "FIXME" in text:
        flags.append("包含 TODO/FIXME")
    if re.search(r"password\s*=\s*['\"]|api[_-]?key\s*=\s*['\"]|secret\s*=\s*['\"]", text, flags=re.I):
        flags.append("疑似硬编码密钥")
    if "Depends(get_current_user)" not in text and path.as_posix().find("/api/") >= 0 and "@router." in text:
        flags.append("接口文件可能需要检查登录/权限依赖")
    return flags


def _tree(root: Path, files: list[Path]) -> list[str]:
    items = []
    for path in files[:MAX_TREE_ITEMS]:
        items.append(_rel(path, root if root.is_dir() else root.parent))
    return items


def _detect_stack(root: Path, files: list[Path]) -> list[str]:
    names = {path.name for path in files}
    rels = {_rel(path, root if root.is_dir() else root.parent) for path in files}
    stack = []
    if "requirements.txt" in names or any(item.startswith("app/api/") for item in rels):
        stack.extend(["Python", "FastAPI"])
    if any("sqlalchemy" in _read_text(path).lower() for path in files if path.name in {"requirements.txt", "pyproject.toml"}):
        stack.append("SQLAlchemy")
    if any(item.startswith("alembic/") for item in rels):
        stack.append("Alembic")
    if "package.json" in names or any(item.startswith("frontend/") for item in rels):
        stack.extend(["Vue", "Vite", "TypeScript"])
    if any("milvus" in _read_text(path).lower() for path in files if path.name in {"requirements.txt", ".env.example"} or "rag" in path.name.lower()):
        stack.append("Milvus/RAG")
    if any("langgraph" in _read_text(path).lower() for path in files if path.name == "requirements.txt"):
        stack.append("LangGraph")
    return list(dict.fromkeys(stack))


def build_project_index(path_text: str | None) -> dict[str, Any]:
    target = ensure_allowed_code_path(path_text)
    root = target if target.is_dir() else target.parent
    files = _iter_files(target)
    summaries: list[FileSummary] = []
    role_counts: dict[str, int] = {}
    all_flags: list[dict[str, Any]] = []
    for path in files:
        rel_path = _rel(path, root)
        text = _read_text(path)
        role = _file_role(path, rel_path)
        flags = _flags(path, text)
        summary = FileSummary(
            path=rel_path,
            ext=path.suffix.lower(),
            size=path.stat().st_size,
            role=role,
            symbols=_extract_symbols(path, text),
            flags=flags,
        )
        summaries.append(summary)
        role_counts[role] = role_counts.get(role, 0) + 1
        if flags:
            all_flags.append({"path": rel_path, "flags": flags})
    return {
        "target": str(target),
        "root": str(root),
        "is_file": target.is_file(),
        "file_count": len(files),
        "tree": _tree(root, files),
        "stack": _detect_stack(root, files),
        "role_counts": role_counts,
        "files": [item.to_dict() for item in summaries[:MAX_FILES]],
        "flags": all_flags[:80],
        "truncated": len(files) >= MAX_FILES,
    }


def _local_report(question: str, index: dict[str, Any]) -> str:
    lines = [
        f"我已完成编程助手项目体检：{index['target']}",
        "",
        "核心判断：",
        f"- 共扫描 {index['file_count']} 个文本/代码文件。",
        f"- 识别技术栈：{('、'.join(index.get('stack') or [])) or '暂未从关键文件中识别出明确技术栈'}。",
    ]
    if index.get("role_counts"):
        lines.append("- 模块分布：")
        for role, count in sorted(index["role_counts"].items(), key=lambda item: item[0]):
            lines.append(f"  - {role}：{count} 个文件")
    key_files = [item for item in index.get("files", []) if item["role"] in {"后端接口层", "后端业务服务层", "数据库 ORM 模型", "前端页面", "前端组件", "前端 API 封装", "项目配置/依赖"}][:12]
    if key_files:
        lines.append("")
        lines.append("关键文件：")
        for item in key_files:
            symbol_text = f"；符号：{', '.join(item['symbols'][:5])}" if item.get("symbols") else ""
            lines.append(f"- {item['path']}：{item['role']}{symbol_text}")
    if index.get("flags"):
        lines.append("")
        lines.append("需要关注的风险/改进点：")
        for item in index["flags"][:10]:
            lines.append(f"- {item['path']}：{'、'.join(item['flags'])}")
    lines.append("")
    lines.append("可优化方向：")
    lines.append("- 为关键业务流程补自动化测试，尤其是权限、文件上传、写操作确认和数据联动。")
    lines.append("- 对较长的 service / component 做职责拆分，保留清晰的接口层、服务层和工具层边界。")
    lines.append("- 对配置、密钥、上传路径、跨角色权限继续做安全审查。")
    return "\n".join(lines)


def _llm_report(
    question: str,
    index: dict[str, Any],
    llm_provider: str | None = None,
    llm_model: str | None = None,
) -> str | None:
    compact = {
        "target": index.get("target"),
        "file_count": index.get("file_count"),
        "stack": index.get("stack"),
        "role_counts": index.get("role_counts"),
        "tree": index.get("tree", [])[:80],
        "key_files": index.get("files", [])[:80],
        "flags": index.get("flags", [])[:40],
        "truncated": index.get("truncated"),
    }
    prompt = (
        "你是资深软件架构师和代码审查专家。请基于项目索引分析代码项目，要求："
        "1. 说明项目目的和整体架构；2. 分析主要模块职责；3. 指出优点；"
        "4. 按高/中/低风险列出问题；5. 给出短期、中期、长期优化建议；"
        "6. 不要编造索引中不存在的文件；7. 不要输出密钥或敏感信息。"
    )
    return call_selected_llm(
        system_prompt=prompt,
        user_message=f"用户问题：{question}\n\n项目索引：\n{json.dumps(compact, ensure_ascii=False)[:24000]}",
        llm_provider=llm_provider,
        llm_model=llm_model,
        temperature=0.2,
        max_tokens=1800,
    )


def _candidate_keywords(message: str) -> list[str]:
    text = re.sub(r"[^\w\u4e00-\u9fff]+", " ", message or "", flags=re.UNICODE)
    words = [item.strip().lower() for item in text.split() if len(item.strip()) >= 2]
    mapping = {
        "登录": ["login", "auth", "登录"],
        "权限": ["permission", "rbac", "role", "auth", "权限"],
        "学生": ["student", "Student", "学生"],
        "教师": ["teacher", "Teacher", "教师"],
        "课程": ["course", "Course", "课程"],
        "成绩": ["score", "Score", "成绩"],
        "请假": ["leave", "Leave", "请假"],
        "考勤": ["attendance", "Attendance", "考勤"],
        "知识库": ["rag", "knowledge", "Knowledge", "知识库"],
        "助手": ["agent", "assistant", "AIAssistant", "助手"],
        "邮件": ["email", "Email", "邮件"],
        "路由": ["router", "route", "路由"],
        "接口": ["api", "router", "接口"],
        "页面": ["views", "vue", "页面"],
    }
    for key, values in mapping.items():
        if key in message:
            words.extend(value.lower() for value in values)
    return list(dict.fromkeys(words))[:20]


def _score_file_for_query(file_item: dict[str, Any], keywords: list[str]) -> int:
    haystack = " ".join([
        str(file_item.get("path") or ""),
        str(file_item.get("role") or ""),
        " ".join(file_item.get("symbols") or []),
        " ".join(file_item.get("flags") or []),
    ]).lower()
    score = 0
    for word in keywords:
        if word and word.lower() in haystack:
            score += 2 if word.lower() in str(file_item.get("path") or "").lower() else 1
    return score


def _locate_relevant_files(message: str, index: dict[str, Any], limit: int = 10) -> list[dict[str, Any]]:
    keywords = _candidate_keywords(message)
    scored = []
    for item in index.get("files") or []:
        score = _score_file_for_query(item, keywords)
        if score > 0:
            scored.append((score, item))
    scored.sort(key=lambda pair: (-pair[0], pair[1].get("path") or ""))
    if scored:
        return [item for _, item in scored[:limit]]
    return (index.get("files") or [])[:limit]


def _read_target_snippet(path_text: str | None) -> tuple[Path | None, str]:
    if not path_text:
        return None, ""
    path = ensure_allowed_code_path(path_text)
    if path.is_dir():
        return path, ""
    text = _read_text(path)
    return path, text[:MAX_SNIPPET_CHARS]


def _coding_context(message: str, previous_index: dict[str, Any] | None) -> dict[str, Any]:
    path_text = extract_code_path(message)
    index = previous_index
    if path_text:
        try:
            index = build_project_index(path_text)
        except Exception:
            path, snippet = _read_target_snippet(path_text)
            return {"target_path": str(path) if path else path_text, "snippet": snippet, "index": previous_index}
    elif not index:
        try:
            index = build_project_index(str(_project_root()))
        except Exception:
            index = None
    return {"target_path": path_text, "snippet": "", "index": index}


def _local_coding_reply(message: str, task_type: str, context: dict[str, Any]) -> str:
    index = context.get("index") or {}
    relevant = _locate_relevant_files(message, index, limit=8) if index else []
    if task_type == "locate":
        if not relevant:
            return "我暂时没有定位到明确文件。你可以补充功能名、接口名、页面名或项目路径，例如“学生新增接口在哪”。"
        lines = ["我根据项目索引先定位到这些可能相关的文件："]
        for item in relevant:
            symbols = f"，关键符号：{', '.join(item.get('symbols') or [])}" if item.get("symbols") else ""
            lines.append(f"- {item.get('path')}：{item.get('role')}{symbols}")
        lines.append("你可以继续问“解释第一个文件”或“分析这个流程”。")
        return "\n".join(lines)
    if task_type == "modify_plan":
        lines = [
            "我可以先给出受控修改方案，但当前不会直接改文件，避免误改项目。",
            "建议流程：",
            "1. 先定位要改的文件和函数/组件。",
            "2. 给出修改前后代码片段或 diff 建议。",
            "3. 你确认后再进入受控修改流程。",
        ]
        if relevant:
            lines.append("可能相关文件：")
            lines.extend(f"- {item.get('path')}：{item.get('role')}" for item in relevant[:6])
        return "\n".join(lines)
    if task_type == "generate":
        return (
            "可以，我能生成代码示例。请补充技术栈、文件位置和输入输出要求会更准确。\n"
            "例如：用 FastAPI 写一个上传接口、用 Vue + Element Plus 写一个表格页面、写一条 MySQL 建表语句。"
        )
    if context.get("snippet"):
        return f"我已读取到目标文件片段，可以帮你解释其职责、流程和风险。片段长度：{len(context['snippet'])} 字。"
    return "我可以回答编程问题、解释代码、定位文件、生成代码建议，也可以分析项目路径。请直接说你的开发任务。"


def _llm_coding_reply(
    message: str,
    task_type: str,
    context: dict[str, Any],
    llm_provider: str | None = None,
    llm_model: str | None = None,
) -> str | None:
    index = context.get("index") or {}
    relevant = _locate_relevant_files(message, index, limit=12) if index else []
    payload = {
        "task_type": task_type,
        "target_path": context.get("target_path"),
        "snippet": context.get("snippet", "")[:MAX_SNIPPET_CHARS],
        "project": {
            "target": index.get("target"),
            "stack": index.get("stack"),
            "role_counts": index.get("role_counts"),
            "relevant_files": relevant,
        } if index else None,
    }
    system_prompt = (
        "你是校园助手内置的编程助手，能力类似轻量级代码协作助手。"
        "请用中文回答，优先给出可执行的工程建议。"
        "如果用户要改代码，只给方案、文件定位、补丁思路和注意事项，不声称已经修改文件。"
        "如果用户要生成代码，请给出完整但不过度冗长的代码片段，并说明应放在哪个文件。"
        "如果上下文不足，先列出缺少的信息。不要泄露密钥，不要建议危险命令。"
    )
    return call_selected_llm(
        system_prompt=system_prompt,
        user_message=f"用户请求：{message}\n\n上下文：\n{json.dumps(payload, ensure_ascii=False)[:22000]}",
        llm_provider=llm_provider,
        llm_model=llm_model,
        temperature=0.25,
        max_tokens=1600,
    )


def handle_coding_assistant_message(
    message: str,
    previous_index: dict[str, Any] | None = None,
    user_id: int | None = None,
    llm_provider: str | None = None,
    llm_model: str | None = None,
) -> tuple[str, dict[str, Any]]:
    task_type = _coding_task_type(message)
    context = _coding_context(message, previous_index)
    reply = _llm_coding_reply(
        message,
        task_type,
        context,
        llm_provider=llm_provider,
        llm_model=llm_model,
    ) or _local_coding_reply(message, task_type, context)
    data = {
        "task": "coding_assistant",
        "task_type": task_type,
        "index": context.get("index"),
        "target_path": context.get("target_path"),
        "llm_provider": llm_provider or "system",
        "llm_model": normalize_ollama_model(llm_model) if (llm_provider or "").lower() in {"local", "ollama"} else (llm_model or "default"),
        "can_modify": False,
        "safety": "当前版本提供代码问答、定位、解释、生成和修改方案，不直接写入文件。",
    }
    return reply, data


def _safe_report_name(value: str) -> str:
    name = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", value or "code_analysis", flags=re.UNICODE)
    name = name.strip("._")
    return (name[:60] or "code_analysis")


def _report_dir(user_id: int | None = None) -> Path:
    root = Path(settings.ABS_UPLOAD_DIR).resolve() / "code_analysis_reports"
    if user_id is not None:
        root = root / str(user_id)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _write_report_file(question: str, reply: str, index: dict[str, Any], user_id: int | None = None) -> dict[str, Any]:
    now = datetime.now()
    target_name = _safe_report_name(Path(str(index.get("target") or "project")).name)
    file_name = f"code_analysis_{now.strftime('%Y%m%d_%H%M%S')}_{target_name}.txt"
    path = _report_dir(user_id) / file_name
    content = "\n".join([
        "编程助手项目体检报告",
        "=" * 32,
        f"生成时间：{now.strftime('%Y-%m-%d %H:%M:%S')}",
        f"分析目标：{index.get('target') or '-'}",
        f"扫描文件数：{index.get('file_count') or 0}",
        f"识别技术栈：{('、'.join(index.get('stack') or [])) or '暂未识别'}",
        f"用户问题：{question or '-'}",
        "",
        "报告正文",
        "-" * 32,
        reply,
        "",
        "说明：本报告由校园助手编程助手模块基于静态项目索引和大模型总结生成，可作为后续整改参考。",
    ])
    path.write_text(content, encoding="utf-8")
    return {
        "path": str(path),
        "file_name": file_name,
        "size": path.stat().st_size,
        "preview": content[:REPORT_PREVIEW_CHARS],
    }


def analyze_code_message(
    message: str,
    previous_index: dict[str, Any] | None = None,
    user_id: int | None = None,
    llm_provider: str | None = None,
    llm_model: str | None = None,
) -> tuple[str, dict[str, Any]]:
    path_text = extract_code_path(message)
    if not path_text and previous_index and any(word in message for word in ["继续", "这个项目", "这个文件", "风险", "优化", "模块", "接口", "表关系"]):
        index = previous_index
    else:
        index = build_project_index(path_text)
    reply = _llm_report(message, index, llm_provider=llm_provider, llm_model=llm_model) or _local_report(message, index)
    report = _write_report_file(message, reply, index, user_id=user_id)
    reply = f"{reply}\n\n编程助手项目体检报告已生成：{report['path']}"
    return reply, {
        "task": "code_analysis",
        "index": index,
        "report": report,
        "llm_provider": llm_provider or "system",
        "llm_model": normalize_ollama_model(llm_model) if (llm_provider or "").lower() in {"local", "ollama"} else (llm_model or "default"),
    }
