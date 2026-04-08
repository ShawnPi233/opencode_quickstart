#!/usr/bin/env bash
set -euo pipefail

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

_info() {
  printf '%s\n' "$*"
}

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

DEFAULT_PROVIDER_NAME_FALLBACK="codexzh"
DEFAULT_BASE_URL_FALLBACK="https://api.codexzh.com/v1"
DEFAULT_PROVIDER_NAME="${DEFAULT_PROVIDER_NAME_FALLBACK}"
DEFAULT_BASE_URL="${DEFAULT_BASE_URL_FALLBACK}"
WUXI_NPM_REGISTRY="https://mirrors.cloud.tencent.com/npm/"

_trim() {
  local value="$1"
  value="${value#"${value%%[![:space:]]*}"}"
  value="${value%"${value##*[![:space:]]}"}"
  printf '%s' "$value"
}

_PROMPT_BACK=10
_PROMPT_QUIT=11

_prompt_required() {
  local prompt="$1"
  local value=""
  while true; do
    read -r -p "$prompt" value
    value="$(_trim "$value")"
    case "$value" in
      /back)
        return "$_PROMPT_BACK"
        ;;
      /quit)
        return "$_PROMPT_QUIT"
        ;;
    esac
    if [[ -n "$value" ]]; then
      printf '%s' "$value"
      return 0
    fi
    echo "输入不能为空；输入 /back 返回上一步，/quit 退出。" >&2
  done
}

_prompt_visible_required() {
  local prompt="$1"
  local value=""
  while true; do
    read -r -p "$prompt" value
    value="$(_trim "$value")"
    case "$value" in
      /back)
        return "$_PROMPT_BACK"
        ;;
      /quit)
        return "$_PROMPT_QUIT"
        ;;
    esac
    if [[ -n "$value" ]]; then
      printf '%s' "$value"
      return 0
    fi
    echo "输入不能为空；输入 /back 返回上一步，/quit 退出。" >&2
  done
}

_validate_api_key() {
  local provider_name="$1"
  local base_url="$2"
  local api_key="$3"
  local url="${base_url%/}/models"
  local http_code=""

  if ! command -v curl >/dev/null 2>&1; then
    echo "warning: 未找到 curl，跳过 ${provider_name} API Key 连通性校验。" >&2
    return 0
  fi

  http_code="$(curl -sS -o /dev/null -w '%{http_code}' \
    -H "Authorization: Bearer ${api_key}" \
    -H 'Content-Type: application/json' \
    --connect-timeout 8 \
    --max-time 20 \
    "$url" 2>/dev/null || true)"

  case "$http_code" in
    200)
      echo "${provider_name} API Key 校验通过。" >&2
      return 0
      ;;
    401|403)
      echo "${provider_name} API Key 校验失败：认证未通过（HTTP ${http_code}）。" >&2
      return 1
      ;;
    000|"")
      echo "${provider_name} API Key 校验失败：无法连接 ${url}。" >&2
      return 1
      ;;
    *)
      echo "${provider_name} API Key 校验失败：接口返回 HTTP ${http_code}（${url}）。" >&2
      return 1
      ;;
  esac
}

_prompt_api_key_verified() {
  local provider_name="$1"
  local base_url="$2"
  local prompt="$3"
  local api_key=""

  while true; do
    if api_key="$(_prompt_visible_required "$prompt")"; then
      if _validate_api_key "$provider_name" "$base_url" "$api_key"; then
        printf '%s' "$api_key"
        return 0
      fi
      echo "请重试；输入 /back 返回上一步，/quit 退出。" >&2
    else
      return "$?"
    fi
  done
}

_configure_default_provider() {
  local api_key=""
  local status=0

  export OPENCODE_PROVIDER_NAME="${DEFAULT_PROVIDER_NAME}"
  export OPENCODE_BASE_URL="${DEFAULT_BASE_URL}"

  if api_key="$(_prompt_api_key_verified \
    "${DEFAULT_PROVIDER_NAME}" \
    "${DEFAULT_BASE_URL}" \
    "请输入 ${DEFAULT_PROVIDER_NAME} 的 API Key（输入 /back 返回，/quit 退出）: ")"; then
    export OPENCODE_API_KEY="$api_key"
    return 0
  else
    status="$?"
  fi

  case "$status" in
    $_PROMPT_BACK)
      return "$_PROMPT_BACK"
      ;;
    $_PROMPT_QUIT)
      return "$_PROMPT_QUIT"
      ;;
  esac

  return "$status"
}

_configure_custom_provider() {
  local provider_name=""
  local base_url=""
  local api_key=""
  local status=0

  while true; do
    if provider_name="$(_prompt_required "请输入供应商名称（输入 /back 返回，/quit 退出）: ")"; then
      :
    else
      status="$?"
      case "$status" in
        $_PROMPT_BACK)
          return "$_PROMPT_BACK"
          ;;
        $_PROMPT_QUIT)
          return "$_PROMPT_QUIT"
          ;;
      esac
      return "$status"
    fi

    while true; do
      if base_url="$(_prompt_required "请输入供应商 URL（输入 /back 返回，/quit 退出）: ")"; then
        :
      else
        status="$?"
        case "$status" in
          $_PROMPT_BACK)
            break
            ;;
          $_PROMPT_QUIT)
            return "$_PROMPT_QUIT"
            ;;
        esac
        return "$status"
      fi

      while true; do
        if api_key="$(_prompt_api_key_verified \
          "$provider_name" \
          "$base_url" \
          "请输入该供应商的 API Key（输入 /back 返回，/quit 退出）: ")"; then
          export OPENCODE_PROVIDER_NAME="$provider_name"
          export OPENCODE_BASE_URL="$base_url"
          export OPENCODE_API_KEY="$api_key"
          return 0
        else
          status="$?"
          case "$status" in
            $_PROMPT_BACK)
              break
              ;;
            $_PROMPT_QUIT)
              return "$_PROMPT_QUIT"
              ;;
          esac
          return "$status"
        fi
      done
    done
  done
}

_load_default_provider() {
  local config_path="$ROOT/tracked_config/opencode.public.json"
  local line=""
  local name_re='"name"[[:space:]]*:[[:space:]]*"([^"]+)"'
  local url_re='"baseURL"[[:space:]]*:[[:space:]]*"([^"]+)"'

  [[ -f "$config_path" ]] || return 0

  while IFS= read -r line; do
    if [[ "$line" =~ $name_re ]]; then
      DEFAULT_PROVIDER_NAME="${BASH_REMATCH[1]}"
      break
    fi
  done < "$config_path"

  while IFS= read -r line; do
    if [[ "$line" =~ $url_re ]]; then
      DEFAULT_BASE_URL="${BASH_REMATCH[1]}"
      break
    fi
  done < "$config_path"
}

_is_wuxi_cluster() {
  local fm=""
  if command -v findmnt >/dev/null 2>&1; then
    fm="$(findmnt -no TARGET,SOURCE,FSTYPE 2>/dev/null || true)"
    if [[ -z "$fm" ]]; then
      fm="$(findmnt 2>/dev/null || true)"
    fi
  fi

  if [[ -n "$fm" ]] && [[ "$fm" =~ thuwayfs|/wuxi_gpfs|/wuxi_train ]]; then
    return 0
  fi

  if [[ -d /wuxi_train || -d /wuxi_gpfs ]]; then
    return 0
  fi

  return 1
}

_maybe_set_wuxi_npm_registry() {
  if [[ -n "${NPM_CONFIG_REGISTRY:-}" || -n "${npm_config_registry:-}" ]]; then
    return 0
  fi

  if _is_wuxi_cluster; then
    export NPM_CONFIG_REGISTRY="$WUXI_NPM_REGISTRY"
    export npm_config_registry="$WUXI_NPM_REGISTRY"
    _info "检测到无锡集群，npm 将使用镜像: $WUXI_NPM_REGISTRY"
  fi
}

_menu_select() {
  local prompt="$1"
  shift
  local -a options=("$@")
  local selected=0
  local key=""
  local esc=""
  local lines_to_rewind=0
  local prefix_active="\033[36m●\033[0m"
  local prefix_idle="○"
  local label_active_start="\033[1m"
  local label_active_end="\033[0m"

  if [[ ${#options[@]} -eq 0 ]]; then
    return 1
  fi

  if [[ ! -t 1 ]]; then
    return 1
  fi

  printf '\033[?25l'
  trap 'printf "\033[?25h"' RETURN

  while true; do
    if [[ "$lines_to_rewind" -gt 0 ]]; then
      printf '\033[%dA' "$lines_to_rewind"
    fi
    printf '\033[J'

    printf '\033[1m%s\033[0m\n' "$prompt"
    for i in "${!options[@]}"; do
      if [[ "$i" -eq "$selected" ]]; then
        printf '  %b %b%s%b\n' "$prefix_active" "$label_active_start" "${options[$i]}" "$label_active_end"
      else
        printf '  %s %s\n' "$prefix_idle" "${options[$i]}"
      fi
    done
    printf '\033[2m%s\033[0m\n' '↑ ↓ 切换，Enter 确认'
    lines_to_rewind=$(( ${#options[@]} + 2 ))

    IFS= read -r -s -n1 key
    case "$key" in
      "")
        REPLY="$selected"
        printf '\033[%dA\033[J' "$lines_to_rewind"
        printf '已选择：%s\n\n' "${options[$selected]}"
        return 0
        ;;
      $'\x1b')
        IFS= read -r -s -n2 -t 0.1 esc || true
        key+="$esc"
        case "$key" in
          $'\x1b[A')
            selected=$(((selected - 1 + ${#options[@]}) % ${#options[@]}))
            ;;
          $'\x1b[B')
            selected=$(((selected + 1) % ${#options[@]}))
            ;;
        esac
        ;;
    esac
  done
}

_choose_provider_fallback() {
  local choice=""
  local status=0

  while true; do
    echo "请选择供应商配置："
    echo "  1. 默认供应商 ${DEFAULT_PROVIDER_NAME}（${DEFAULT_BASE_URL}）"
    echo "  2. 添加新供应商"
    echo "  3. 跳过"
    echo "  4. 退出"
    read -r -p "请输入选项 [1/2/3/4]: " choice
    choice="$(_trim "$choice")"
    case "$choice" in
      1|"")
        if _configure_default_provider; then
          status=0
        else
          status="$?"
        fi
        case "$status" in
          0)
            return 0
            ;;
          $_PROMPT_BACK)
            continue
            ;;
          $_PROMPT_QUIT)
            _die "已退出初始化。"
            ;;
        esac
        ;;
      2)
        if _configure_custom_provider; then
          status=0
        else
          status="$?"
        fi
        case "$status" in
          0)
            return 0
            ;;
          $_PROMPT_BACK)
            continue
            ;;
          $_PROMPT_QUIT)
            _die "已退出初始化。"
            ;;
        esac
        ;;
      3)
        unset OPENCODE_PROVIDER_NAME OPENCODE_BASE_URL OPENCODE_API_KEY
        return 0
        ;;
      4)
        _die "已退出初始化。"
        ;;
      *)
        echo "仅支持 1/2/3/4，请重试。" >&2
        ;;
    esac
  done
}

_choose_provider() {
  local status=0

  if [[ ! -t 0 || ! -t 1 ]]; then
    _choose_provider_fallback
    return 0
  fi

  while true; do
    _menu_select \
      "请选择供应商配置（上下方向键切换，回车确认）：" \
      "使用当前默认供应商 ${DEFAULT_PROVIDER_NAME}（${DEFAULT_BASE_URL}）" \
      "添加新供应商" \
      "跳过" \
      "退出"

    case "$REPLY" in
      0)
        if _configure_default_provider; then
          status=0
        else
          status="$?"
        fi
        case "$status" in
          0)
            return 0
            ;;
          $_PROMPT_BACK)
            continue
            ;;
          $_PROMPT_QUIT)
            _die "已退出初始化。"
            ;;
        esac
        ;;
      1)
        if _configure_custom_provider; then
          status=0
        else
          status="$?"
        fi
        case "$status" in
          0)
            return 0
            ;;
          $_PROMPT_BACK)
            continue
            ;;
          $_PROMPT_QUIT)
            _die "已退出初始化。"
            ;;
        esac
        ;;
      2)
        unset OPENCODE_PROVIDER_NAME OPENCODE_BASE_URL OPENCODE_API_KEY
        return 0
        ;;
      3)
        _die "已退出初始化。"
        ;;
    esac
  done
}

# 优先读取当前环境变量，兼容新旧变量名。
_load_default_provider

if [[ -n "${OPENCODE_DIR:-}" && -z "${OPENCODE_ROOT:-}" ]]; then
  export OPENCODE_ROOT="${OPENCODE_DIR}"
elif [[ -n "${OPENCODE_ROOT:-}" && -z "${OPENCODE_DIR:-}" ]]; then
  export OPENCODE_DIR="${OPENCODE_ROOT}"
fi

if [[ -n "${OPENCODE_DIR:-}" ]]; then
  ENV_INIT="${OPENCODE_DIR}/env_init.sh"
  if [[ -f "$ENV_INIT" ]]; then
    # shellcheck source=/dev/null
    source "$ENV_INIT"
    _info "已加载环境: $ENV_INIT"
    if [[ "$_IS_SOURCED" -eq 0 ]]; then
      echo "提示：建议使用 source quick_start.sh 使环境变量保留在当前 shell。" >&2
    fi
    exit 0
  fi
fi

_info "未检测到可用环境，开始初始化。"
_choose_provider

cd "$ROOT"
export OPENCODE_DIR="$(dirname "$(pwd -P)")/opencode"
export OPENCODE_ROOT="${OPENCODE_DIR}"
_maybe_set_wuxi_npm_registry

bash "$ROOT/start.sh"

# 安装后只 source 环境，避免再跑一遍安装逻辑。
export OPENCODE_QUICK_SOURCE=1
# shellcheck source=/dev/null
source "$ROOT/start.sh"
unset OPENCODE_QUICK_SOURCE

_info "初始化完成。"
if [[ "$_IS_SOURCED" -eq 0 ]]; then
  echo "提示：建议使用 source quick_start.sh 使环境变量保留在当前 shell。" >&2
fi
