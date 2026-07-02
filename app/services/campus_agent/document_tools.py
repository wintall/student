"""Document processing tools for the football assistant."""
from __future__ import annotations

import hashlib
import json
import mimetypes
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.exceptions import BusinessException
from app.models.user import User
from app.schemas.rag_knowledge import KnowledgeBaseCreate
from app.services import rag_knowledge_service
from app.services.campus_agent.llm_client import call_deepseek
from app.services.document_parser import ensure_allowed_path, read_document
from app.services.ocr_service import ocr_image

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"}
DOCUMENT_EXTENSIONS = {".txt", ".md", ".markdown", ".pdf", ".docx"}
SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | DOCUMENT_EXTENSIONS
DEFAULT_ASSISTANT_KB_NAME = "助手文档知识库"


@dataclass
class AgentFile:
    file_id: str
    name: str
    ext: str
    size: int
    mime_type: str
    path: Path
    kind: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_id": self.file_id,
            "name": self.name,
            "ext": self.ext,
            "size": self.size,
            "mime_type": self.mime_type,
            "path": str(self.path),
            "kind": self.kind,
        }


def _allowed_roots() -> list[Path]:
    project_root = Path(__file__).resolve().parents[3]
    return [
        project_root,
        Path(settings.ABS_UPLOAD_DIR).resolve(),
        (project_root / "文本").resolve(),
    ]


def _user_upload_dir(user: User) -> Path:
    path = Path(settings.ABS_UPLOAD_DIR).resolve() / "campus_agent_docs" / str(user.id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_name(name: str) -> str:
    cleaned = Path(name or "upload").name
    cleaned = re.sub(r"[^\w.\-\u4e00-\u9fff]+", "_", cleaned, flags=re.UNICODE)
    return cleaned[:180] or "upload"


def _file_kind(ext: str) -> str:
    return "image" if ext.lower() in IMAGE_EXTENSIONS else "document"


def _ensure_allowed_agent_path(user: User, path_text: str) -> Path:
    path = Path(path_text).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise BusinessException(message="文件不存在或不是普通文件。")
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise BusinessException(message="暂不支持该文件类型。支持 txt、md、pdf、docx 和常见图片。")

    user_root = _user_upload_dir(user).resolve()
    roots = _allowed_roots() + [user_root]
    if not any(path == root or root in path.parents for root in roots):
        allowed_text = "、".join(str(root) for root in roots)
        raise BusinessException(message=f"出于安全考虑，仅允许处理项目目录或上传目录下的文件：{allowed_text}")
    return path


def _file_from_path(user: User, path: Path, file_id: str | None = None) -> AgentFile:
    resolved = _ensure_allowed_agent_path(user, str(path))
    ext = resolved.suffix.lower()
    stat = resolved.stat()
    return AgentFile(
        file_id=file_id or _build_file_id(user.id, resolved.name, stat.st_size, resolved),
        name=resolved.name,
        ext=ext,
        size=stat.st_size,
        mime_type=mimetypes.guess_type(resolved.name)[0] or "application/octet-stream",
        path=resolved,
        kind=_file_kind(ext),
    )


def _build_file_id(user_id: int, file_name: str, size: int, path: Path) -> str:
    raw = f"{user_id}:{file_name}:{size}:{path}".encode("utf-8", errors="ignore")
    return hashlib.sha256(raw).hexdigest()[:24]


def _meta_path(path: Path) -> Path:
    return path.with_suffix(f"{path.suffix}.json")


async def save_agent_file(user: User, upload: UploadFile) -> dict[str, Any]:
    file_name = _safe_name(upload.filename or "upload")
    ext = Path(file_name).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise BusinessException(message="暂不支持该文件类型。支持 txt、md、pdf、docx、png、jpg、jpeg、bmp、webp、tif、tiff。")

    data = await upload.read()
    if not data:
        raise BusinessException(message="上传文件为空。")
    if len(data) > settings.MAX_UPLOAD_SIZE:
        raise BusinessException(message=f"文件超过大小限制，最大 {settings.MAX_UPLOAD_SIZE // 1024 // 1024}MB。")

    digest = hashlib.sha256(data).hexdigest()
    stored_name = f"{digest[:24]}{ext}"
    stored_path = _user_upload_dir(user) / stored_name
    stored_path.write_bytes(data)
    mime_type = upload.content_type or mimetypes.guess_type(file_name)[0] or "application/octet-stream"
    _meta_path(stored_path).write_text(
        json.dumps(
            {
                "file_id": digest[:24],
                "name": file_name,
                "ext": ext,
                "size": len(data),
                "mime_type": mime_type,
                "kind": _file_kind(ext),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    agent_file = AgentFile(
        file_id=digest[:24],
        name=file_name,
        ext=ext,
        size=len(data),
        mime_type=mime_type,
        path=stored_path.resolve(),
        kind=_file_kind(ext),
    )
    return agent_file.to_dict()


def resolve_agent_file(user: User, file_id: str, name: str | None = None) -> AgentFile:
    file_id = (file_id or "").strip()
    if not re.fullmatch(r"[a-fA-F0-9]{24,64}", file_id):
        raise BusinessException(message="文件 ID 无效。")
    user_dir = _user_upload_dir(user).resolve()
    matches = list(user_dir.glob(f"{file_id[:24]}.*"))
    matches = [item for item in matches if item.suffix.lower() != ".json"]
    if not matches:
        raise BusinessException(message="没有找到已上传的文件，请重新拖拽上传。")
    file = _file_from_path(user, matches[0], file_id=file_id[:24])
    meta_file = _meta_path(matches[0])
    if meta_file.exists():
        try:
            meta = json.loads(meta_file.read_text(encoding="utf-8"))
            file.name = meta.get("name") or file.name
            file.mime_type = meta.get("mime_type") or file.mime_type
        except Exception:
            pass
    if name:
        file.name = name
    return file


def extract_path(text: str) -> str | None:
    match = re.search(r"([A-Za-z]:\\[^\n\r]+|/[^\n\r]+)", text or "")
    if not match:
        return None
    value = match.group(1).strip().strip('"').strip("'")
    for stopper in [" 总结", " 翻译", " OCR", " 识别", " 提取", " 存入"]:
        if stopper in value:
            value = value.split(stopper)[0].strip()
    return value


def read_text_from_file(agent_file: AgentFile) -> tuple[str | None, str | None]:
    try:
        if agent_file.ext in IMAGE_EXTENSIONS:
            return ocr_image(agent_file.path), None
        if agent_file.ext in DOCUMENT_EXTENSIONS:
            return read_document(agent_file.path), None
        return None, "暂不支持该文件类型。"
    except BusinessException as exc:
        return None, exc.message
    except Exception as exc:
        return None, str(exc)


def read_text_from_path(user: User, path_text: str) -> tuple[str | None, str | None, AgentFile | None]:
    try:
        agent_file = _file_from_path(user, Path(path_text))
        text, error = read_text_from_file(agent_file)
        return text, error, agent_file
    except BusinessException as exc:
        return None, exc.message, None
    except Exception as exc:
        return None, str(exc), None


def _direct_text(message: str) -> str:
    text = (message or "").strip()
    for prefix in ["总结", "概括", "提取重点", "提取", "翻译", "英译中", "中译英", "请帮我", "帮我"]:
        if text.startswith(prefix):
            text = text[len(prefix):].strip(" ：:")
    return text


def _task_from_message(message: str, files: list[AgentFile]) -> str:
    lowered = (message or "").lower()
    if any(word in message for word in ["存入知识库", "加入知识库", "保存到知识库", "导入知识库"]):
        return "save_to_kb"
    if any(word in message for word in ["翻译", "英译中", "中译英", "英文", "中文"]) or "translate" in lowered:
        return "translate"
    if any(word in message for word in ["识别", "OCR", "ocr", "图片文字", "提取文字"]) and any(f.kind == "image" for f in files):
        return "ocr"
    if any(word in message for word in ["重点", "要点", "提取", "摘要", "概括", "总结"]):
        return "summarize"
    if files and any(f.kind == "image" for f in files):
        return "ocr"
    return "summarize"


def summarize(text: str) -> str:
    if not text.strip():
        return "请提供要处理的文本、文件路径，或直接拖拽上传图片、txt、md、pdf、docx 文件。"
    prompt = (
        "你是校园助手的文档处理专家。请用中文输出：1. 核心摘要；2. 关键要点；3. 可执行建议。"
        "不要大段复制原文，尽量用现代、清晰的语言概括。"
    )
    reply = call_deepseek(system_prompt=prompt, user_message=text[:12000], temperature=0.2, max_tokens=1200)
    if reply:
        return reply
    preview = text[:800]
    return f"我已经读取到文本，但当前 AI 生成服务不可用。先给你前 800 字预览：\n{preview}"


def translate(text: str, target: str | None = None) -> str:
    if not text.strip():
        return "请提供要翻译的中文或英文内容，或拖拽上传要翻译的文件。"
    has_chinese = bool(re.search(r"[\u4e00-\u9fff]", text))
    target_lang = target or ("英文" if has_chinese else "中文")
    prompt = f"你是专业翻译助手。请把用户内容翻译成{target_lang}，保留必要术语，表达自然。只输出译文。"
    reply = call_deepseek(system_prompt=prompt, user_message=text[:10000], temperature=0.2, max_tokens=1200)
    if reply:
        return reply
    return "当前 AI 翻译服务不可用，请稍后再试。"


def _target_language(message: str) -> str | None:
    if "英译中" in message or "翻译成中文" in message or "译成中文" in message:
        return "中文"
    if "中译英" in message or "翻译成英文" in message or "译成英文" in message:
        return "英文"
    return None


def _combine_file_texts(files: list[AgentFile]) -> tuple[str, list[dict[str, Any]], list[str]]:
    parts: list[str] = []
    file_context: list[dict[str, Any]] = []
    errors: list[str] = []
    for file in files:
        text, error = read_text_from_file(file)
        file_info = file.to_dict()
        file_info["char_count"] = len(text or "")
        file_context.append(file_info)
        if error:
            errors.append(f"{file.name}：{error}")
            continue
        if not text:
            errors.append(f"{file.name}：没有提取到可用文本")
            continue
        parts.append(f"【{file.name}】\n{text}")
    return "\n\n".join(parts).strip(), file_context, errors


def _latest_document_files(previous_file_context: list[dict[str, Any]] | None, user: User) -> list[AgentFile]:
    files: list[AgentFile] = []
    for item in previous_file_context or []:
        try:
            file_id = str(item.get("file_id") or "")
            files.append(resolve_agent_file(user, file_id, item.get("name")))
        except Exception:
            continue
    return files


def _find_or_create_assistant_kb(db: Session, user: User):
    for item in rag_knowledge_service.list_kbs(db, user, keyword=DEFAULT_ASSISTANT_KB_NAME, include_public=False):
        if item.get("name") == DEFAULT_ASSISTANT_KB_NAME and item.get("owner_id") == user.id:
            return rag_knowledge_service.get_kb(db, int(item["id"]))
    return rag_knowledge_service.create_kb(
        db,
        user,
        KnowledgeBaseCreate(
            name=DEFAULT_ASSISTANT_KB_NAME,
            description="足球助手文档处理模块自动保存的个人知识库",
            scope_type="personal",
        ),
    )


def save_text_to_knowledge_base(db: Session, user: User, title: str, text: str, kb_id: int | None = None) -> dict[str, Any]:
    if not text.strip():
        raise BusinessException(message="没有可存入知识库的文本内容。")
    kb = rag_knowledge_service.get_kb(db, kb_id) if kb_id else _find_or_create_assistant_kb(db, user)
    doc = rag_knowledge_service.import_text(db, user, kb.id, title[:200] or "助手文档", text)
    return {
        "kb_id": kb.id,
        "kb_name": kb.name,
        "document_id": doc.id,
        "title": doc.title,
        "chunk_count": doc.chunk_count,
        "char_count": doc.char_count,
    }


def handle_document_message(
    message: str,
    *,
    user: User,
    db: Session | None = None,
    files: list[AgentFile] | None = None,
    previous_file_context: list[dict[str, Any]] | None = None,
) -> tuple[str, dict]:
    files = files or []
    message = message or ""
    path_text = extract_path(message)
    source = "message"

    if not files and path_text:
        text, error, agent_file = read_text_from_path(user, path_text)
        if error:
            return error, {"source": path_text, "task": "read_file", "files": []}
        files = [agent_file] if agent_file else []
        source = path_text

    if not files and previous_file_context and any(word in message for word in ["刚才", "这个文件", "这张图", "继续", "存入知识库", "加入知识库", "保存到知识库"]):
        files = _latest_document_files(previous_file_context, user)
        source = "memory"

    task = _task_from_message(message, files)
    if files:
        text, file_context, errors = _combine_file_texts(files)
        source = source if source != "message" else "upload"
    else:
        text = _direct_text(message)
        file_context = []
        errors = []

    if errors and not text:
        return "\n".join(errors), {"source": source, "task": task, "files": file_context, "errors": errors}

    if task == "save_to_kb":
        if not db:
            return "当前上下文无法写入知识库，请稍后再试。", {"source": source, "task": task, "files": file_context}
        try:
            title = files[0].name if files else "助手文档"
            saved = save_text_to_knowledge_base(db, user, title, text)
            reply = (
                f"已把文档内容存入综合知识库“{saved['kb_name']}”。\n"
                f"- 文档：{saved['title']}\n"
                f"- 字符数：{saved['char_count']}\n"
                f"- 分片数：{saved['chunk_count']}\n\n"
                "之后你可以在 RAG 知识问答里继续基于它提问。"
            )
            return reply, {"source": source, "task": task, "files": file_context, "saved": saved}
        except Exception as exc:
            return f"存入知识库失败：{exc}", {"source": source, "task": task, "files": file_context, "errors": [str(exc)]}

    if task == "translate":
        reply = translate(text or "", _target_language(message))
    elif task == "ocr":
        reply = text or "没有识别到图片文字。"
    else:
        reply = summarize(text or "")

    if errors:
        reply = f"{reply}\n\n部分文件处理提示：\n" + "\n".join(f"- {item}" for item in errors)
    return reply, {"source": source, "task": task, "files": file_context, "char_count": len(text or ""), "errors": errors}
