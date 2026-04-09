#!/usr/bin/env bash
# 默认：CLI 一键安装 OpenCode + 合并配置（API Key 用环境变量，无需看板）
# CLI 模式仅依赖系统 Python 标准库，不再安装 uv / 虚拟环境 / 额外 pip 包；仅 UI 模式会准备这些依赖。
#   export OPENCODE_API_KEY='sk-...'   # 可选
#   export OPENCODE_DIR=/custom/path    # 可选（推荐）
#   export OPENCODE_ROOT=/custom/path   # 可选（兼容旧变量）
#   未设 OPENCODE_DIR/OPENCODE_ROOT 时：默认「本仓库所在目录的父目录」+ /opencode（与 dirname(仓库根)/opencode 相同，无硬编码）
#   若该路径无法 mkdir，且是脚本自动推导的，会 warning 后改用 $HOME/opencode
#   ./start.sh                         # 执行安装；结束后提示 source
#   source start.sh                    # 安装后自动 source env_init.sh（当前 bash 会话）
# 看板：
#   ./start.sh ui
# 用 `sh start.sh` 时会强制改为 bash 执行
if [ -z "${BASH_VERSION:-}" ]; then
  if command -v bash >/dev/null 2>&1; then
    exec bash "$0" "$@"
  fi
  echo "error: 未找到 bash，请执行: bash $0" >&2
  exit 1
fi

_IS_SOURCED=0
if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
  _IS_SOURCED=1
fi

_die() {
  echo "error: $*" >&2
  if [[ "$_IS_SOURCED" -eq 1 ]]; then
    return 1
  fi
  exit 1
}

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

_PROGRESS_TTY=0
if [[ -t 1 ]]; then
  _PROGRESS_TTY=1
fi

_PROGRESS_FILL="="
_PROGRESS_EMPTY="-"
if [[ "${LC_ALL:-${LC_CTYPE:-${LANG:-}}}" == *"UTF-8"* || "${LC_ALL:-${LC_CTYPE:-${LANG:-}}}" == *"utf8"* ]]; then
  _PROGRESS_FILL="█"
  _PROGRESS_EMPTY="░"
fi

_log() {
  printf '%s\n' "$*"
}

_print_progress() {
  local percent="$1"
  local message="$2"
  local width=24
  local filled=$(( percent * width / 100 ))
  local empty=$(( width - filled ))
  local fill_bar=""
  local empty_bar=""

  if [[ "$filled" -gt 0 ]]; then
    printf -v fill_bar '%*s' "$filled" ''
    fill_bar="${fill_bar// /${_PROGRESS_FILL}}"
  fi
  if [[ "$empty" -gt 0 ]]; then
    printf -v empty_bar '%*s' "$empty" ''
    empty_bar="${empty_bar// /${_PROGRESS_EMPTY}}"
  fi

  if [[ "$_PROGRESS_TTY" -eq 1 ]]; then
    printf '\r\033[2K[%s%s] %3d%% %s' "$fill_bar" "$empty_bar" "$percent" "$message"
    if [[ "$percent" -ge 100 ]]; then
      printf '\n'
    fi
  else
    printf '[%3d%%] %s\n' "$percent" "$message"
  fi
}

_find_python_cmd() {
  local candidate=""
  for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
      printf '%s' "$candidate"
      return 0
    fi
  done
  return 1
}

# 变量兼容策略：
# 1) 优先 OPENCODE_DIR（新变量）；
# 2) 若只设了 OPENCODE_ROOT，则回填 OPENCODE_DIR；
# 3) 两者都未设时，默认 dirname(ROOT)/opencode。
_OPENCODE_DIR_FROM_PARENT=0
if [[ -n "${OPENCODE_DIR:-}" && -z "${OPENCODE_ROOT:-}" ]]; then
  export OPENCODE_ROOT="${OPENCODE_DIR}"
elif [[ -n "${OPENCODE_ROOT:-}" && -z "${OPENCODE_DIR:-}" ]]; then
  export OPENCODE_DIR="${OPENCODE_ROOT}"
elif [[ -z "${OPENCODE_DIR:-}" && -z "${OPENCODE_ROOT:-}" ]]; then
  export OPENCODE_DIR="$(dirname "${ROOT}")/opencode"
  export OPENCODE_ROOT="${OPENCODE_DIR}"
  _OPENCODE_DIR_FROM_PARENT=1
fi

if [[ "${OPENCODE_DIR}" != "${OPENCODE_ROOT}" ]]; then
  echo "warning: OPENCODE_DIR 与 OPENCODE_ROOT 不一致，优先使用 OPENCODE_DIR=${OPENCODE_DIR}" >&2
  export OPENCODE_ROOT="${OPENCODE_DIR}"
fi
export OPENCODE_DIR="${OPENCODE_ROOT}"

MODE="cli"
if [[ "${1:-}" == "ui" ]]; then
  MODE="ui"
  shift
fi

if [[ "$MODE" == "ui" && "$_IS_SOURCED" -eq 1 ]]; then
  _die "不要用 source 启动看板；请执行: bash \"$0\" ui"
fi

# 已装过：仅加载环境（需 bash source；日常可改用 source \"\$OPENCODE_ROOT/env_init.sh\"）
if [[ "$_IS_SOURCED" -eq 1 && "${OPENCODE_QUICK_SOURCE:-}" == "1" ]]; then
  if [[ "${OPENCODE_ROOT:0:1}" == "~" ]]; then
    export OPENCODE_ROOT="${OPENCODE_ROOT/#\~/$HOME}"
  fi
  ENV_INIT="${OPENCODE_ROOT}/env_init.sh"
  [[ -f "$ENV_INIT" ]] || _die "缺少 ${ENV_INIT}，请先执行一次: bash ${ROOT}/start.sh"
  # shellcheck source=/dev/null
  source "$ENV_INIT"
  echo "OPENCODE_QUICK_SOURCE=1：已 source ${ENV_INIT}" >&2
  return 0
fi

_uv_path_prepend() {
  export PATH="${HOME}/.local/bin:${HOME}/.cargo/bin:${PATH}"
}

_install_uv_with_fallback() {
  local install_ok=0

  if command -v curl >/dev/null 2>&1; then
    if curl --retry 3 --retry-delay 2 --retry-all-errors --connect-timeout 15 -fsSL https://astral.sh/uv/install.sh | sh; then
      install_ok=1
    fi
  fi

  if [[ "$install_ok" -eq 0 ]]; then
    _log "通过官方脚本安装 uv 失败，尝试使用 pip --user 安装..."
    local pip_args=(-m pip install --user -U uv)
    if [[ -n "${OPENCODE_PIP_INDEX:-}" ]]; then
      pip_args+=(-i "${OPENCODE_PIP_INDEX}")
    elif [[ -n "${PIP_INDEX_URL:-}" ]]; then
      pip_args+=(-i "${PIP_INDEX_URL}")
    fi

    if "$PYTHON_CMD" "${pip_args[@]}"; then
      install_ok=1
    fi
  fi

  if [[ "$install_ok" -eq 1 ]]; then
    return 0
  fi
  return 1
}

_print_progress 5 "检查运行环境"

PYTHON_CMD="$(_find_python_cmd)" || _die "未找到 python3/python，请先安装 Python 3。"

_ensure_ui_runtime() {
  _uv_path_prepend

  if ! command -v uv >/dev/null 2>&1; then
    _log "正在安装 uv..."
    _install_uv_with_fallback
    _uv_path_prepend
  fi

  if ! command -v uv >/dev/null 2>&1; then
    _die "安装后仍未在 PATH 中找到 uv。请将 ~/.local/bin 加入 PATH 后重试。"
  fi

  VENV="${ROOT}/.venv"
  if [[ ! -x "$VENV/bin/python" ]]; then
    if [[ -d "$VENV" ]]; then
      _log "发现不完整虚拟环境，正在清理..."
      rm -rf "$VENV"
    fi
    _log "正在创建 UI 虚拟环境..."
    uv venv "$VENV"
  fi
}

if [[ "$MODE" == "ui" ]]; then
  # PyPI 镜像（仅 UI 模式需要 pip/uv 下载依赖）
  if [[ -z "${OPENCODE_PIP_INDEX:-}" && -z "${PIP_INDEX_URL:-}" && -z "${UV_INDEX_URL:-}" && -z "${OPENCODE_CLUSTER:-}" ]]; then
    _auto_idx=""
    if [[ -f "$ROOT/detect_pypi_mirror.sh" ]]; then
      _auto_idx="$(bash "$ROOT/detect_pypi_mirror.sh" 2>/dev/null | head -n1 | tr -d '\r')"
    fi
    if [[ -n "${_auto_idx}" ]]; then
      OPENCODE_PIP_INDEX="${_auto_idx}"
    fi
  fi

  PIP_INDEX_EXTRA=()
  if [[ -n "${OPENCODE_PIP_INDEX:-}" ]]; then
    PIP_INDEX_EXTRA=(--index-url "${OPENCODE_PIP_INDEX}")
  elif [[ -z "${PIP_INDEX_URL:-}" && -z "${UV_INDEX_URL:-}" ]]; then
    case "${OPENCODE_CLUSTER:-}" in
      zw10|ningxia|paratera)
        PIP_INDEX_EXTRA=(--index-url "https://pypi.zw10.paratera.com/root/pypi/+simple/")
        ;;
      wuxi|swnexus|thuway)
        PIP_INDEX_EXTRA=(--index-url "https://swnexus.thuwayinfo.com/repository/group-pypi/simple")
        ;;
    esac
  fi
  if [[ ${#PIP_INDEX_EXTRA[@]} -gt 0 ]]; then
    _log "PyPI 索引: ${PIP_INDEX_EXTRA[1]}"
  fi

  _print_progress 20 "准备 UI 运行环境"
  _ensure_ui_runtime
  _print_progress 45 "安装 Streamlit 依赖"
  _log "正在安装看板依赖..."
  uv pip install -q -r "$ROOT/requirements.txt" --python "$VENV/bin/python" "${PIP_INDEX_EXTRA[@]}"
  _print_progress 100 "启动 Streamlit"
  _log "正在启动 Streamlit，退出请按 Ctrl+C。"
  exec "$VENV/bin/streamlit" run "$ROOT/app.py" "$@"
fi

_print_progress 20 "准备 OpenCode 目录"

if ! mkdir -p "${OPENCODE_ROOT}" 2>/dev/null; then
  if [[ "${_OPENCODE_DIR_FROM_PARENT:-0}" -eq 1 ]]; then
    echo "warning: 无法在 ${OPENCODE_ROOT} 创建目录，已改用 \${HOME}/opencode" >&2
    export OPENCODE_ROOT="${HOME}/opencode"
    export OPENCODE_DIR="${OPENCODE_ROOT}"
    mkdir -p "${OPENCODE_ROOT}" || _die "无法创建 ${OPENCODE_ROOT}"
  else
    _die "无法创建 OPENCODE_ROOT=${OPENCODE_ROOT}，请改为可写路径，例如 export OPENCODE_DIR=\"\${HOME}/opencode\""
  fi
fi

_log "安装目录: ${OPENCODE_DIR}"

_print_progress 45 "执行 OpenCode 安装"

if ! PYTHONPATH="$ROOT" "$PYTHON_CMD" -m lib.cli_setup; then
  _die "一键安装/合并配置失败（见上方日志）"
fi

ENV_INIT="${OPENCODE_ROOT}/env_init.sh"
if [[ -f "$ENV_INIT" ]]; then
  _print_progress 90 "加载环境配置"
  if [[ "$_IS_SOURCED" -eq 1 ]]; then
    # shellcheck source=/dev/null
    source "$ENV_INIT"
    echo "" >&2
    echo "已加载环境，可直接运行 opencode。" >&2
  else
    echo "" >&2
    echo "后续在新终端先执行：" >&2
    echo "  source \"${ENV_INIT}\"" >&2
    echo "也可在本仓库执行: source start.sh" >&2
  fi
  _print_progress 100 "安装完成"
else
  _die "未找到 env_init.sh（不应发生）"
fi
