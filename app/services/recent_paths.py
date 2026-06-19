from __future__ import annotations

from pathlib import Path

from .config import load_config, save_config


MAX_RECENT = 8


def get_recent_paths() -> list[str]:
    config = load_config()
    paths = config.get("recent_paths", [])
    return [path for path in paths if isinstance(path, str)]


def add_recent_path(path: str | Path) -> list[str]:
    resolved = str(Path(path).expanduser().resolve())
    recent = [p for p in get_recent_paths() if p != resolved]
    recent.insert(0, resolved)
    recent = recent[:MAX_RECENT]
    config = load_config()
    config["recent_paths"] = recent
    save_config(config)
    return recent


def get_theme() -> str:
    return str(load_config().get("theme", "dark"))


def set_theme(theme: str) -> None:
    config = load_config()
    config["theme"] = theme
    save_config(config)


def get_scan_engine() -> str:
    engine = str(load_config().get("scan_engine", "auto"))
    return engine if engine in {"auto", "standard", "parallel", "everything", "windows_fast"} else "auto"


def set_scan_engine(engine: str) -> None:
    config = load_config()
    config["scan_engine"] = engine if engine in {"auto", "standard", "parallel", "everything", "windows_fast"} else "auto"
    save_config(config)


def get_everything_cli_path() -> str:
    return str(load_config().get("everything_cli_path", ""))


def set_everything_cli_path(path: str) -> None:
    config = load_config()
    config["everything_cli_path"] = path.strip()
    save_config(config)


def get_parallel_workers() -> int:
    try:
        return int(load_config().get("parallel_workers", 0))
    except (TypeError, ValueError):
        return 0


def set_parallel_workers(workers: int) -> None:
    config = load_config()
    config["parallel_workers"] = max(0, min(32, int(workers)))
    save_config(config)


def get_prefer_indexed_scan() -> bool:
    return bool(load_config().get("prefer_indexed_scan", False))


def set_prefer_indexed_scan(prefer: bool) -> None:
    config = load_config()
    config["prefer_indexed_scan"] = bool(prefer)
    save_config(config)


def get_language() -> str:
    language = str(load_config().get("language", "en"))
    return language if language in {"en", "it"} else "en"


def set_language(language: str) -> None:
    config = load_config()
    config["language"] = language if language in {"en", "it"} else "en"
    save_config(config)


def has_seen_onboarding() -> bool:
    return bool(load_config().get("onboarding_seen", False))


def set_onboarding_seen(seen: bool = True) -> None:
    config = load_config()
    config["onboarding_seen"] = bool(seen)
    save_config(config)
