import math
import mimetypes
import re
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import UploadFile

from .config import get_settings
from .mail import generate_id

STORED_NAME_SEPARATOR = "__"


def _files_root() -> Path:
    settings = get_settings()
    base_dir = Path(__file__).resolve().parent.parent
    root = Path(settings.files_dir)
    if not root.is_absolute():
        root = base_dir / root
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_user_id(user_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", user_id)


def get_user_dir(user_id: str, create: bool = False) -> Path:
    user_dir = _files_root() / _safe_user_id(user_id)
    if create:
        user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir


def sanitize_filename(name: Optional[str]) -> str:
    base = Path(name or "").name
    return base if base else "file"


def build_stored_name(file_id: str, original_name: str) -> str:
    safe_name = sanitize_filename(original_name)
    return f"{file_id}{STORED_NAME_SEPARATOR}{safe_name}"


def split_stored_name(stored_name: str) -> str:
    if STORED_NAME_SEPARATOR in stored_name:
        return stored_name.split(STORED_NAME_SEPARATOR, 1)[1] or stored_name
    return stored_name


def split_file_id(stored_name: str) -> str:
    if STORED_NAME_SEPARATOR in stored_name:
        return stored_name.split(STORED_NAME_SEPARATOR, 1)[0] or stored_name
    return stored_name


def resolve_user_file(user_id: str, filename: str) -> Optional[Path]:
    user_dir = get_user_dir(user_id, create=False)
    if not user_dir.exists():
        return None
    candidate = (user_dir / filename).resolve()
    try:
        candidate.relative_to(user_dir.resolve())
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def list_user_files(user_id: str) -> List[Path]:
    user_dir = get_user_dir(user_id, create=False)
    if not user_dir.exists():
        return []
    return [path for path in user_dir.iterdir() if path.is_file()]


def guess_mime_type(path: Path) -> str:
    mime, _ = mimetypes.guess_type(path.name)
    return mime or "application/octet-stream"


def format_file_size(bytes_size: int) -> str:
    if bytes_size <= 0:
        return "0 B"
    k = 1024
    sizes = ["B", "KB", "MB", "GB"]
    i = int(min(len(sizes) - 1, math.floor(math.log(bytes_size, k))))
    value = bytes_size / (k ** i)
    value_str = f"{value:.1f}".rstrip("0").rstrip(".")
    return f"{value_str} {sizes[i]}"


def save_upload(user_id: str, upload: UploadFile) -> Dict[str, Any]:
    file_id = generate_id()
    stored_name = build_stored_name(file_id, upload.filename or "file")
    destination = get_user_dir(user_id, create=True) / stored_name
    with destination.open("wb") as buffer:
        shutil.copyfileobj(upload.file, buffer)
    size_bytes = destination.stat().st_size
    content_type = upload.content_type or guess_mime_type(destination)
    return {
        "id": file_id,
        "filename": stored_name,
        "name": split_stored_name(stored_name),
        "size_bytes": size_bytes,
        "type": content_type,
    }
