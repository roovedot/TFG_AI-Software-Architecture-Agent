"""File processing utilities for uploaded documents and images."""

from __future__ import annotations

import base64
from pathlib import Path

from fastapi import UploadFile

SUPPORTED_TEXT_EXTENSIONS = {
    ".txt", ".md", ".csv", ".json", ".xml", ".yaml", ".yml",
    ".py", ".js", ".ts", ".java", ".go", ".rs", ".html", ".css",
    ".toml", ".ini", ".sh", ".sql", ".graphql", ".cfg", ".bat",
}

SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

# MIME types for images
IMAGE_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF bytes using PyMuPDF."""
    import fitz  # pymupdf

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages: list[str] = []
    for page in doc:
        text = page.get_text()
        if text.strip():
            pages.append(text)
    doc.close()
    return "\n\n".join(pages)


def read_text_file(file_bytes: bytes, filename: str) -> str:
    """Decode text file bytes as UTF-8 with latin-1 fallback."""
    try:
        return file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return file_bytes.decode("latin-1")


def encode_image_to_base64(file_bytes: bytes, content_type: str) -> dict:
    """Encode image bytes to base64 and return metadata dict."""
    b64 = base64.b64encode(file_bytes).decode("ascii")
    return {"mime_type": content_type, "base64_data": b64}


async def process_uploaded_file(
    file: UploadFile,
) -> tuple[str | None, dict | None]:
    """Process a single uploaded file.

    Returns:
        (text_content, None) for text and PDF files.
        (None, image_dict) for image files.

    Raises:
        ValueError: If the file type is not supported.
    """
    filename = file.filename or "unknown"
    ext = Path(filename).suffix.lower()
    file_bytes = await file.read()

    if ext == ".pdf":
        text = extract_text_from_pdf(file_bytes)
        header = f"--- {filename} ---"
        return f"{header}\n{text}", None

    if ext in SUPPORTED_TEXT_EXTENSIONS:
        text = read_text_file(file_bytes, filename)
        header = f"--- {filename} ---"
        return f"{header}\n{text}", None

    if ext in SUPPORTED_IMAGE_EXTENSIONS:
        mime = IMAGE_MIME_TYPES.get(ext, file.content_type or "image/png")
        img_dict = encode_image_to_base64(file_bytes, mime)
        return None, img_dict

    raise ValueError(f"Unsupported file type: {ext} ({filename})")
