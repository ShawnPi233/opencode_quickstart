# OpenCode Quickstart

用于快速安装 OpenCode，并把配置拆成两部分：

- `tracked_config/opencode.public.json`：可进 Git 的公开配置
- `tracked_config/opencode.secrets.json`：仅本机保存的密钥，不进 Git

运行时会把两者合并到：

- `<OPENCODE_ROOT>/config/opencode/opencode.json`

## 快速开始

推荐在当前 shell 里执行：

```bash
source /user/baibingsong/opencode_quickstart/quick_start.sh
```

首次运行会提示你选择供应商，并输入 API Key。

`quick_start.sh` 在无锡集群会自动检测并为 npm 设置镜像：
`https://mirrors.cloud.tencent.com/npm/`（仅在未手动设置 npm registry 时生效）。

如果只想执行安装，不立刻加载环境：

```bash
cd /user/baibingsong/opencode_quickstart
bash start.sh
```

安装完成后，按提示执行：

```bash
source "<OPENCODE_ROOT>/env_init.sh"
```

## 日常使用

每开一个新终端，都要先加载环境：

```bash
source "<OPENCODE_ROOT>/env_init.sh"
```

然后就可以直接用：

```bash
opencode --help
```

默认安装目录：

```text
<本仓库父目录>/opencode
```

也可以手动指定：

```bash
export OPENCODE_DIR=/your/path/opencode
source quick_start.sh
```

## Git 同步配置

推荐只同步公开配置：

- 提交 `tracked_config/opencode.public.json`
- 不提交 `tracked_config/opencode.secrets.json`
- 不提交合并后的 `opencode.json`

当前仓库已忽略密钥文件：`tracked_config/opencode.secrets.json`。

典型流程：

```bash
cd /user/baibingsong/opencode_quickstart
git add tracked_config/opencode.public.json
git commit -m "chore: update opencode config"
git push
```

新机器使用时：

1. 拉取仓库
2. 手动补上本机的 `tracked_config/opencode.secrets.json`
3. 运行 `source quick_start.sh`

## 配置文件说明

| 文件 | 是否进 Git | 用途 |
|------|------------|------|
| `tracked_config/opencode.public.json` | 是 | 主题、模型、供应商结构、`baseURL` 等公开配置 |
| `tracked_config/opencode.secrets.json` | 否 | API Key 等私密字段 |
| `<OPENCODE_ROOT>/config/opencode/opencode.json` | 否 | 运行时合并结果 |

## 可选：启动看板

如果你想用 Streamlit 界面：

```bash
cd /user/baibingsong/opencode_quickstart
bash start.sh ui
```

## 常用环境变量

| 变量 | 说明 |
|------|------|
| `OPENCODE_DIR` | OpenCode 安装目录，推荐使用 |
| `OPENCODE_ROOT` | 兼容旧变量，效果等同于 `OPENCODE_DIR` |
| `OPENCODE_API_KEY` | 安装时写入本机 `opencode.secrets.json` |
| `OPENCODE_FORCE_NPM=1` | 强制重新安装 OpenCode CLI |
| `OPENCODE_PIP_INDEX` | 指定 Python 包索引 |
| `OPENCODE_CLUSTER` | 使用内置镜像别名，如 `zw10`、`wuxi` |

## 镜像源

网络环境特殊时，可以先指定 Python 包源：

```bash
export OPENCODE_PIP_INDEX='https://pypi.zw10.paratera.com/root/pypi/+simple/'
source quick_start.sh
```

或者使用内置别名：

```bash
export OPENCODE_CLUSTER=zw10
source quick_start.sh
```

## 注意

- 不要把真实 API Key 提交到 Git
- 不要把完整 `opencode.json` 推到远程
- 如果密钥曾误提交，请立即轮换
