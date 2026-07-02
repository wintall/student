"""Shared OCR helpers for assistant document processing."""
from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path


WINDOWS_TESSERACT_PATHS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
]


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _configure_tesseract():
    import pytesseract

    tesseract_cmd = os.getenv("TESSERACT_CMD") or shutil.which("tesseract")
    if not tesseract_cmd:
        for candidate in WINDOWS_TESSERACT_PATHS:
            if Path(candidate).exists():
                tesseract_cmd = candidate
                break
    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    project_tessdata = _project_root() / "tools" / "tessdata"
    if project_tessdata.exists() and not os.getenv("TESSDATA_PREFIX"):
        os.environ["TESSDATA_PREFIX"] = str(project_tessdata)

    return pytesseract


def _detect_language(pytesseract) -> tuple[str, str | None]:
    try:
        languages = set(pytesseract.get_languages(config=""))
    except Exception as exc:
        return "", f"OCR 语言包读取失败：{exc}"
    if {"chi_sim", "eng"}.issubset(languages):
        return "chi_sim+eng", None
    if "chi_sim" in languages:
        return "chi_sim", None
    if "eng" in languages:
        return "eng", "当前只检测到英文 OCR 语言包，中文图片识别效果会比较差。"
    return "", "OCR 语言包不可用。请确认 tessdata 中存在 chi_sim.traineddata 或 eng.traineddata。"


def ocr_image(path: Path) -> str:
    try:
        from PIL import Image, ImageOps
        import pytesseract  # noqa: F401
    except Exception:
        return "当前环境还没有安装 OCR 依赖。请安装 Pillow、pytesseract，并确保本机 Tesseract OCR 可用。"

    pytesseract = _configure_tesseract()
    lang, warning = _detect_language(pytesseract)
    if not lang:
        return warning or "OCR 语言包不可用。"

    try:
        image = Image.open(path)
        if image.mode not in {"RGB", "L"}:
            image = image.convert("RGB")
        if min(image.size) < 1200:
            image = image.resize((image.width * 2, image.height * 2))
        image = ImageOps.grayscale(image)
        image = ImageOps.autocontrast(image)
        text = pytesseract.image_to_string(image, lang=lang, config="--psm 6").strip()
        text = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", text)
        if warning and text:
            return f"{text}\n\n提示：{warning}"
        return text or "没有识别到图片文字。"
    except Exception as exc:
        return f"OCR 识别失败：{exc}"


def ocr_image_bytes(data: bytes, suffix: str = ".png") -> str:
    if not data:
        return "没有识别到图片文字。"
    suffix = suffix if suffix.startswith(".") else f".{suffix}"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    try:
        return ocr_image(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)
