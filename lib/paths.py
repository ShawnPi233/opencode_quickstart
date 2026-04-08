"""Repository-relative paths; no hard-coded machine absolute paths."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def default_opencode_root() -> Path:
    """
    与 ``start.sh`` 默认一致：未设置 ``OPENCODE_ROOT`` 时，为
    ``<本仓库根目录的父目录>/opencode``（等价于 ``dirname(仓库根)/opencode``）。
    """
    return (repo_root().resolve().parent / "opencode").resolve()


def tracked_config_dir() -> Path:
    return repo_root() / "tracked_config"


def public_config_path() -> Path:
    return tracked_config_dir() / "opencode.public.json"


def secrets_config_path() -> Path:
    return tracked_config_dir() / "opencode.secrets.json"


def local_dir() -> Path:
    return repo_root() / ".local"


def ui_settings_path() -> Path:
    return local_dir() / "settings.json"


def templates_dir() -> Path:
    return repo_root() / "templates"


def ensure_local_dir() -> None:
    local_dir().mkdir(parents=True, exist_ok=True)


def load_ui_settings() -> dict[str, Any]:
    path = ui_settings_path()
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_ui_settings(data: dict[str, Any]) -> None:
    ensure_local_dir()
    path = ui_settings_path()
    merged = load_ui_settings()
    merged.update(data)
    path.write_text(json.dumps(merged, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def resolve_opencode_root(*, sidebar_input: str | None = None) -> Path:
    """
    Priority: OPENCODE_ROOT env → sidebar string → default_opencode_root()
    （默认 ``<仓库父目录>/opencode``，与 ``start.sh`` 一致）。
    Relative paths are resolved against repo_root().
    """
    env = os.environ.get("OPENCODE_ROOT", "").strip()
    if env:
        p = Path(env).expanduser()
        if not p.is_absolute():
            p = (repo_root() / p).resolve()
        else:
            p = p.resolve()
        return p

    raw = (sidebar_input or "").strip()
    if raw:
        p = Path(raw).expanduser()
        if not p.is_absolute():
            p = (repo_root() / p).resolve()
        else:
            p = p.resolve()
        return p

    return default_opencode_root()


def target_opencode_json(root: Path) -> Path:
    return root / "config" / "opencode" / "opencode.json"


def env_init_script_path(root: Path) -> Path:
    return root / "env_init.sh"
