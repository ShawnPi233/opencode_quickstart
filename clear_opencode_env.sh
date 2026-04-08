#!/usr/bin/env bash
# Use with: source ./clear_opencode_env.sh

if [ -z "${BASH_VERSION:-}" ]; then
  echo "error: 请在 bash 中执行: source ./clear_opencode_env.sh" >&2
  return 1 2>/dev/null || exit 1
fi

_was_sourced=0
if [[ "${BASH_SOURCE[0]}" != "$0" ]]; then
  _was_sourced=1
fi

if [[ "$_was_sourced" -ne 1 ]]; then
  echo "warning: 请使用 source 执行，否则不会影响当前 shell。" >&2
fi

# Remove OPENCODE-related variables.
unset OPENCODE_DIR OPENCODE_ROOT OPENCODE_CONFIG OPENCODE_API_KEY OPENCODE_QUICK_SOURCE OPENCODE_FORCE_NPM

# Clear XDG variables only when they point to opencode paths.
for _v in XDG_CONFIG_HOME XDG_DATA_HOME XDG_STATE_HOME; do
  _val="${!_v:-}"
  if [[ "$_val" == *opencode* ]]; then
    unset "$_v"
  fi
done

# Remove PATH entries containing "opencode".
if [[ -n "${PATH:-}" ]]; then
  _new_path=""
  IFS=':' read -r -a _parts <<< "$PATH"
  for _p in "${_parts[@]}"; do
    if [[ "$_p" == *opencode* ]]; then
      continue
    fi
    if [[ -z "$_new_path" ]]; then
      _new_path="$_p"
    else
      _new_path="${_new_path}:$_p"
    fi
  done
  export PATH="$_new_path"
  hash -r 2>/dev/null || true
fi

echo "已清理当前会话中的 opencode 相关环境变量与 PATH 条目。"
