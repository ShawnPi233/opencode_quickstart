#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  if command -v python >/dev/null 2>&1; then
    PYTHON_BIN=python
  else
    echo "error: 未找到 python3/python" >&2
    exit 1
  fi
fi

MIN_VERSION="${OPENCODE_GH_MIN_VERSION:-2.50.0}"
INSTALL_BASE="${HOME}/.local/gh-cli"
INSTALL_BIN_DIR="${HOME}/.local/bin"
FORCE=0

if [[ "${1:-}" == "--force" ]]; then
  FORCE=1
fi

mkdir -p "$INSTALL_BASE" "$INSTALL_BIN_DIR"

_version_ge() {
  "$PYTHON_BIN" - "$1" "$2" <<'PY'
from packaging.version import Version
import sys
print(int(Version(sys.argv[1]) >= Version(sys.argv[2])))
PY
}

_version_ge_fallback() {
  "$PYTHON_BIN" - "$1" "$2" <<'PY'
import sys

def norm(v: str):
    parts = []
    for item in v.split('.'):
        digits = ''.join(ch for ch in item if ch.isdigit())
        parts.append(int(digits or '0'))
    return tuple(parts)

print(int(norm(sys.argv[1]) >= norm(sys.argv[2])))
PY
}

_version_at_least() {
  local current="$1"
  local want="$2"
  if out="$(_version_ge "$current" "$want" 2>/dev/null)"; then
    [[ "$out" == "1" ]]
    return
  fi
  out="$(_version_ge_fallback "$current" "$want")"
  [[ "$out" == "1" ]]
}

CURRENT_VERSION=""
if command -v gh >/dev/null 2>&1; then
  CURRENT_VERSION="$(gh --version 2>/dev/null | "$PYTHON_BIN" -c 'import re,sys; text=sys.stdin.read(); m=re.search(r"gh version\s+([0-9][^\s]*)", text); print(m.group(1) if m else "")')"
fi

if [[ "$FORCE" -eq 0 && -n "$CURRENT_VERSION" ]] && _version_at_least "$CURRENT_VERSION" "$MIN_VERSION"; then
  echo "gh 已满足最低版本要求：${CURRENT_VERSION}"
  exit 0
fi

if command -v curl >/dev/null 2>&1; then
  RELEASE_JSON="$(curl --retry 3 --retry-delay 2 --retry-all-errors --connect-timeout 15 -fsSL https://api.github.com/repos/cli/cli/releases/latest)"
elif command -v wget >/dev/null 2>&1; then
  RELEASE_JSON="$(wget -qO- https://api.github.com/repos/cli/cli/releases/latest)"
else
  echo "error: 未找到 curl/wget，无法下载 gh" >&2
  exit 1
fi

LATEST_TAG="$(printf '%s' "$RELEASE_JSON" | "$PYTHON_BIN" -c 'import json,sys; data=json.load(sys.stdin); print(str(data.get("tag_name", "")).strip())')"
LATEST_VERSION="${LATEST_TAG#v}"
if [[ -z "$LATEST_VERSION" ]]; then
  echo "error: 无法解析 gh 最新版本" >&2
  exit 1
fi

ARCH="$(uname -m)"
case "$ARCH" in
  x86_64|amd64) GH_ARCH="amd64" ;;
  aarch64|arm64) GH_ARCH="arm64" ;;
  armv7l) GH_ARCH="armv6" ;;
  *) echo "error: 不支持的架构: ${ARCH}" >&2; exit 1 ;;
esac

ARCHIVE="gh_${LATEST_VERSION}_linux_${GH_ARCH}.tar.gz"
URL="https://github.com/cli/cli/releases/download/${LATEST_TAG}/${ARCHIVE}"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

echo "安装/升级 gh 到 ${LATEST_VERSION} ..."
if command -v curl >/dev/null 2>&1; then
  curl --retry 3 --retry-delay 2 --retry-all-errors --connect-timeout 15 -fL "$URL" -o "$TMP_DIR/$ARCHIVE"
else
  wget -O "$TMP_DIR/$ARCHIVE" "$URL"
fi

tar -xzf "$TMP_DIR/$ARCHIVE" -C "$TMP_DIR"
SRC_DIR="$TMP_DIR/gh_${LATEST_VERSION}_linux_${GH_ARCH}"
DEST_DIR="$INSTALL_BASE/$LATEST_VERSION"
rm -rf "$DEST_DIR"
mkdir -p "$DEST_DIR"
cp -R "$SRC_DIR"/* "$DEST_DIR/"
ln -sfn "$DEST_DIR/bin/gh" "$INSTALL_BIN_DIR/gh"

echo "gh 已安装：$INSTALL_BIN_DIR/gh"
"$INSTALL_BIN_DIR/gh" --version
