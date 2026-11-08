from pathlib import Path

from app.core.config import get_settings
from app.models.document import DocFile


def storage_dir() -> Path:
    path = Path(get_settings().STORAGE_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


def file_path(doc_file: DocFile) -> Path:
    return storage_dir() / doc_file.storage_key
