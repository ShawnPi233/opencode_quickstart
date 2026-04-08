"""CLI one-click OpenCode setup (no Streamlit).

Environment:
  OPENCODE_ROOT          未设时与 start.sh 一致：<仓库父目录>/opencode
  OPENCODE_API_KEY       写入 secrets 中 provider.openai.options.apiKey（可选）
  OPENCODE_PROVIDER_NAME 覆盖 public 中 provider.openai.name（可选）
  OPENCODE_BASE_URL      覆盖 public 中 provider.openai.options.baseURL（可选）
  OPENCODE_FORCE_NPM     设为 1/true 则强制 npm install
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from lib.one_click import run_one_click_setup
from lib.paths import default_opencode_root


def main() -> int:
    raw = os.environ.get("OPENCODE_ROOT", "").strip()
    if raw:
        root = Path(raw).expanduser().resolve()
    else:
        root = default_opencode_root()

    api_key = os.environ.get("OPENCODE_API_KEY", "")
    provider_name = os.environ.get("OPENCODE_PROVIDER_NAME", "")
    base_url = os.environ.get("OPENCODE_BASE_URL", "")
    force = os.environ.get("OPENCODE_FORCE_NPM", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )

    ok, lines = run_one_click_setup(
        root,
        api_key=api_key,
        provider_name=provider_name,
        base_url=base_url,
        force_npm=force,
        emit=lambda line: print(line, flush=True),
    )
    if not lines:
        print("安装流程未产生输出。", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
