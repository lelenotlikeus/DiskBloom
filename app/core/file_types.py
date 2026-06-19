from __future__ import annotations

from pathlib import Path


TYPE_EXTENSIONS: dict[str, set[str]] = {
    "videos": {".mp4", ".mkv", ".mov", ".avi", ".wmv", ".webm", ".m4v"},
    "images": {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp", ".heic", ".svg"},
    "archives": {".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".iso"},
    "documents": {".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".txt", ".md", ".rtf", ".odt"},
    "code": {".py", ".js", ".ts", ".html", ".css", ".json", ".xml", ".java", ".cpp", ".c", ".h", ".cs", ".go", ".rs", ".sql", ".sh", ".ps1"},
    "executables/apps": {".exe", ".msi", ".app", ".dmg", ".pkg", ".deb", ".rpm", ".apk", ".bat", ".cmd"},
    "audio": {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".wma"},
}


def classify_extension(path_or_extension: str | Path) -> str:
    ext = Path(path_or_extension).suffix.lower() if not str(path_or_extension).startswith(".") else str(path_or_extension).lower()
    for category, extensions in TYPE_EXTENSIONS.items():
        if ext in extensions:
            return category
    return "other"
