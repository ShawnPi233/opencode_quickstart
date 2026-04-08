"""One-click: dirs + optional npm + env_init + provider config + merge to opencode.json."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from pathlib import Path

from lib.env_init import write_env_init
from lib.json_validate import validate_secrets
from lib.merge_config import load_json_file, merged_config, save_json_file
from lib.paths import public_config_path, secrets_config_path
from lib.run_cmd import run_cmd

_SUBDIRS = ("bin", "lib", "config", "data", "state", "config/opencode")


def _append_log(logs: list[str], line: str, emit: Callable[[str], None] | None) -> None:
    logs.append(line)
    if emit is not None:
        emit(line)


def _ensure_openai_api_key(secrets: dict, api_key: str) -> None:
    key = api_key.strip()
    if not key:
        return
    prov = secrets.setdefault("provider", {})
    if not isinstance(prov, dict):
        secrets["provider"] = {}
        prov = secrets["provider"]
    oa = prov.setdefault("openai", {})
    if not isinstance(oa, dict):
        prov["openai"] = {}
        oa = prov["openai"]
    opts = oa.setdefault("options", {})
    if not isinstance(opts, dict):
        oa["options"] = {}
        opts = oa["options"]
    opts["apiKey"] = key


def _ensure_openai_public_provider(
    public: dict, provider_name: str, base_url: str
) -> bool:
    changed = False
    providers = public.setdefault("provider", {})
    if not isinstance(providers, dict):
        public["provider"] = {}
        providers = public["provider"]

    openai = providers.setdefault("openai", {})
    if not isinstance(openai, dict):
        providers["openai"] = {}
        openai = providers["openai"]

    options = openai.setdefault("options", {})
    if not isinstance(options, dict):
        openai["options"] = {}
        options = openai["options"]

    name = provider_name.strip()
    if name and openai.get("name") != name:
        openai["name"] = name
        changed = True

    url = base_url.strip()
    if url and options.get("baseURL") != url:
        options["baseURL"] = url
        changed = True

    return changed


def run_one_click_setup(
    root: Path,
    *,
    api_key: str,
    provider_name: str,
    base_url: str,
    force_npm: bool,
    emit: Callable[[str], None] | None = None,
) -> tuple[bool, list[str]]:
    """
    Returns (ok, log_lines). Custom provider values update provider.openai in public.
    """
    logs: list[str] = []
    pub_path = public_config_path()
    if not pub_path.is_file():
        return False, [
            "缺少仓库内 tracked_config/opencode.public.json，请先 git clone 本工具仓库。"
        ]

    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    for sub in _SUBDIRS:
        (root / sub).mkdir(parents=True, exist_ok=True)
    _append_log(logs, f"1/6 已准备目录: {root}", emit)

    bin_oc = root / "bin" / "opencode"
    if force_npm or not bin_oc.is_file():
        if shutil.which("npm") is None:
            message = "2/6 未找到 npm，且当前目录没有现成的 opencode 可复用。"
            _append_log(logs, message, emit)
            return False, logs
        _append_log(logs, "2/6 正在安装 OpenCode CLI...", emit)
        code, out, err = run_cmd(
            ["npm", "install", "-g", "opencode-ai", "--prefix", str(root)],
            cwd=str(root),
            timeout=1200,
            live=emit is not None,
        )
        if code != 0:
            message = f"2/6 npm 安装失败，退出码 {code}"
            _append_log(logs, message, emit)
            if not emit:
                tail = (out + err).strip()
                if tail:
                    logs.append(tail[-4000:])
            return False, logs
        if not bin_oc.is_file():
            message = "2/6 安装结束，但未生成 bin/opencode"
            _append_log(logs, message, emit)
            return False, logs
        _append_log(logs, "2/6 OpenCode CLI 安装完成", emit)
    else:
        _append_log(logs, "2/6 检测到现有 OpenCode CLI，跳过安装", emit)

    write_env_init(root)
    _append_log(logs, "3/6 已生成 env_init.sh", emit)

    public = load_json_file(pub_path)
    public_changed = _ensure_openai_public_provider(public, provider_name, base_url)
    if public_changed:
        _append_log(logs, "4/6 已更新供应商配置", emit)
    else:
        _append_log(logs, "4/6 保留默认供应商配置", emit)

    sec_path = secrets_config_path()
    secrets = load_json_file(sec_path)
    _ensure_openai_api_key(secrets, api_key)
    sec_path.parent.mkdir(parents=True, exist_ok=True)
    validate_secrets(secrets)
    save_json_file(sec_path, secrets)
    if api_key.strip():
        _append_log(logs, "5/6 已写入 API Key 到本机 secrets", emit)
    else:
        _append_log(logs, "5/6 未提供新 API Key，保留现有 secrets", emit)

    target = root / "config" / "opencode" / "opencode.json"
    save_json_file(target, merged_config(public, secrets))
    _append_log(logs, f"6/6 已生成配置: {target}", emit)
    return True, logs
