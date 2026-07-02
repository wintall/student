import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Iterable

from app.exceptions import BusinessException
from app.services.ocr_service import ocr_image_bytes


TEXT_EXTENSIONS = {".txt", ".md", ".markdown"}
PDF_EXTENSIONS = {".pdf"}
DOCX_EXTENSIONS = {".docx"}
SUPPORTED_EXTENSIONS = TEXT_EXTENSIONS | PDF_EXTENSIONS | DOCX_EXTENSIONS


def read_text_file(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gbk"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise BusinessException(message="文件编码无法识别，请使用 UTF-8 或 GBK 文本")


def read_pdf_file(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except Exception as exc:
        raise BusinessException(message="当前环境缺少 pypdf，无法解析 PDF，请先安装依赖") from exc

    try:
        reader = PdfReader(str(path))
        pages = []
        image_notes = []
        for index, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text() or ""
            pages.append(page_text)
            try:
                for image_index, image in enumerate(page.images, start=1):
                    image_text = ocr_image_bytes(image.data, Path(image.name or ".png").suffix or ".png")
                    if image_text and "没有识别到图片文字" not in image_text:
                        image_notes.append(f"【第 {index} 页图片 {image_index} OCR】\n{image_text}")
            except Exception:
                continue
        if image_notes:
            pages.append("\n\n".join(image_notes))
        return "\n\n".join(pages).strip()
    except Exception as exc:
        raise BusinessException(message=f"PDF 解析失败：{exc}") from exc


def _docx_table_to_markdown(table, namespace: dict[str, str]) -> str:
    rows = []
    for row in table.findall(".//w:tr", namespace):
        cells = []
        for cell in row.findall("./w:tc", namespace):
            texts = [node.text or "" for node in cell.findall(".//w:t", namespace)]
            value = "".join(texts).strip().replace("\n", " ")
            cells.append(value)
        if cells:
            rows.append(cells)
    if not rows:
        return ""
    width = max(len(row) for row in rows)
    normalized = [row + [""] * (width - len(row)) for row in rows]
    header = normalized[0]
    divider = ["---"] * width
    body = normalized[1:]

    def line(values: list[str]) -> str:
        return "| " + " | ".join(values) + " |"

    return "\n".join([line(header), line(divider), *[line(row) for row in body]])


def read_docx_file(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as docx:
            xml_text = docx.read("word/document.xml")
            media_items = [
                (name, docx.read(name))
                for name in docx.namelist()
                if name.startswith("word/media/")
                and Path(name).suffix.lower() in {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"}
            ]
    except Exception as exc:
        raise BusinessException(message=f"Word 文档解析失败：{exc}") from exc

    try:
        root = ET.fromstring(xml_text)
        namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
        paragraphs = []
        for paragraph in root.findall(".//w:p", namespace):
            texts = [node.text or "" for node in paragraph.findall(".//w:t", namespace)]
            line = "".join(texts).strip()
            if line:
                paragraphs.append(line)

        table_texts = []
        for index, table in enumerate(root.findall(".//w:tbl", namespace), start=1):
            table_text = _docx_table_to_markdown(table, namespace)
            if table_text:
                table_texts.append(f"【表格 {index}】\n{table_text}")

        image_texts = []
        for index, (name, data) in enumerate(media_items, start=1):
            image_text = ocr_image_bytes(data, Path(name).suffix or ".png")
            if image_text and "没有识别到图片文字" not in image_text:
                image_texts.append(f"【图片 {index} OCR：{Path(name).name}】\n{image_text}")

        parts = []
        if paragraphs:
            parts.append("【正文】\n" + "\n\n".join(paragraphs))
        if table_texts:
            parts.append("【表格内容】\n" + "\n\n".join(table_texts))
        if image_texts:
            parts.append("【图片文字】\n" + "\n\n".join(image_texts))
        return "\n\n".join(parts).strip()
    except Exception as exc:
        raise BusinessException(message=f"Word 文档文本提取失败：{exc}") from exc


def read_document(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in TEXT_EXTENSIONS:
        return read_text_file(path)
    if ext in PDF_EXTENSIONS:
        return read_pdf_file(path)
    if ext in DOCX_EXTENSIONS:
        return read_docx_file(path)
    raise BusinessException(message=f"暂不支持 {ext or '未知'} 文件类型，仅支持 txt、md、pdf、docx")


def _normalize_text(text: str) -> str:
    lines = [line.rstrip() for line in (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    normalized = "\n".join(lines)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def _split_long_paragraph(paragraph: str, chunk_size: int, overlap: int) -> list[str]:
    parts: list[str] = []
    sentences = re.split(r"(?<=[。！？!?；;])", paragraph)
    current = ""
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        candidate = f"{current}{sentence}" if current else sentence
        if len(candidate) <= chunk_size:
            current = candidate
            continue
        if current:
            parts.append(current)
        if len(sentence) <= chunk_size:
            current = sentence
            continue
        start = 0
        while start < len(sentence):
            end = min(start + chunk_size, len(sentence))
            parts.append(sentence[start:end])
            if end >= len(sentence):
                break
            start = max(end - overlap, start + 1)
        current = ""
    if current:
        parts.append(current)
    return parts


def split_text(text: str, chunk_size: int, overlap: int) -> list[str]:
    normalized = _normalize_text(text)
    if not normalized:
        return []

    chunk_size = max(int(chunk_size or 700), 200)
    overlap = max(min(int(overlap or 0), chunk_size // 2), 0)

    paragraphs = [p.strip() for p in normalized.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""

    def push(value: str):
        cleaned = value.strip()
        if cleaned:
            chunks.append(cleaned)

    for paragraph in paragraphs:
        if len(paragraph) > chunk_size:
            if current:
                push(current)
                current = ""
            for part in _split_long_paragraph(paragraph, chunk_size, overlap):
                push(part)
            continue

        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            push(current)
            if overlap and chunks:
                prefix = chunks[-1][-overlap:]
                current = f"{prefix}\n\n{paragraph}".strip()
                if len(current) > chunk_size:
                    current = paragraph
            else:
                current = paragraph

    if current:
        push(current)

    return chunks


def ensure_allowed_path(path_text: str, allowed_roots: Iterable[Path]) -> Path:
    path = Path(path_text).expanduser().resolve()
    if not path.exists() or not path.is_file():
        raise BusinessException(message="文件不存在或不是普通文件")
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise BusinessException(message="仅支持 txt、md、pdf、docx 文件")

    resolved_roots = [root.resolve() for root in allowed_roots]
    if not any(path == root or root in path.parents for root in resolved_roots):
        roots = "、".join(str(root) for root in resolved_roots)
        raise BusinessException(message=f"出于安全考虑，仅允许导入项目目录或上传目录下的文件：{roots}")
    return path
