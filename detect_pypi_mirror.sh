#!/usr/bin/env bash
# 根据 findmnt / 常见挂载点判断宁夏并行 vs 无锡，向 stdout 打印一条 PyPI simple 根 URL。
# 未识别则不输出（退出码 0）。说明性日志可写到 stderr。
#
# 无锡特征：thuwayfs、挂载目标 /wuxi_gpfs、/wuxi_train
# 宁夏特征：paratera_ningxia、JuiceFS:modelbest（并行训练平台常见）

set -euo pipefail

URL_WUXI='https://swnexus.thuwayinfo.com/repository/group-pypi/simple'
URL_NINGXIA='https://pypi.zw10.paratera.com/root/pypi/+simple/'

log() { printf '%s\n' "$*" >&2; }

_fm=''
if command -v findmnt >/dev/null 2>&1; then
  _fm=$(findmnt -no TARGET,SOURCE,FSTYPE 2>/dev/null || true)
  if [[ -z "${_fm}" ]]; then
    _fm=$(findmnt 2>/dev/null || true)
  fi
fi

_match_wuxi() {
  grep -qE 'thuwayfs|/wuxi_gpfs|/wuxi_train' <<<"${_fm}"
}

_match_ningxia() {
  grep -qE 'paratera_ningxia|JuiceFS:modelbest' <<<"${_fm}"
}

_pick_by_mountpoints() {
  local w n
  w=0
  n=0
  [[ -d /wuxi_train || -d /wuxi_gpfs ]] && w=1
  [[ -d /paratera_ningxia ]] && n=1
  if [[ $w -eq 1 && $n -eq 1 ]]; then
    log "detect_pypi_mirror: 同时存在无锡与宁夏目录特征，请设置 OPENCODE_PIP_INDEX 或 OPENCODE_CLUSTER"
    return 1
  fi
  if [[ $w -eq 1 && $n -eq 0 ]]; then
    echo "$URL_WUXI"
    log "detect_pypi_mirror: 根据目录挂载点推断为无锡 (wuxi_train/wuxi_gpfs)"
    return 0
  fi
  if [[ $n -eq 1 && $w -eq 0 ]]; then
    echo "$URL_NINGXIA"
    log "detect_pypi_mirror: 根据目录挂载点推断为宁夏并行 (paratera_ningxia)"
    return 0
  fi
  return 1
}

if [[ -n "${_fm}" ]]; then
  if _match_wuxi; then
    echo "$URL_WUXI"
    log "detect_pypi_mirror: findmnt 匹配无锡 (thuwayfs / wuxi_*)"
    exit 0
  fi
  if _match_ningxia; then
    echo "$URL_NINGXIA"
    log "detect_pypi_mirror: findmnt 匹配宁夏并行 (paratera_ningxia / JuiceFS:modelbest)"
    exit 0
  fi
fi

if _pick_by_mountpoints; then
  exit 0
fi

log "detect_pypi_mirror: 未识别集群特征，使用默认 PyPI（由 uv 决定）"
exit 0
