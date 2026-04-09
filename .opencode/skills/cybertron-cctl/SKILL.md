---
name: cybertron-cctl
description: "Cybertron 平台命令行工具 cctl ：包括一键配置、可用命令、全局约定、认证、任务命令、镜像命令、项目命令、资源池命令、版本与自更新等内容。关键要点包括： 1. 一键配置：支持 mac 和 linux，使用 curl https://teleport-mb.oss-cn-beijing.aliyuncs.com/cctl/install_cctl.sh | bash 进行配置。 2. 可用顶层命令：包括 cctl login、cctl job、cctl image 等多种命令。 3. 全局约定：配置目录为 ~/.cybertronctl/，保存 token、server 等内容，有相应的选择优先级和输出格式约定。 4. 认证：支持多种登录方式，如默认浏览器登录、指定环境登录、手动粘贴 token 等，登录成功后保存信息并验证，token 临近过期或请求返回 401 时会尝试自动刷新。 5. 任务命令：有四种任务类型对应独立顶层命令，已挂载子命令包括列表、详情、创建、停止、日志、复制等操作，创建任务有通用必填参数和按类型追加要求，还支持从 JSON 文件创建。 6. 镜像、项目和资源池命令：镜像命令支持列表、详情、创建、更新、删除、同步等操作；项目命令支持列表、详情、创建；资源池命令支持列表和详情查询。 7. 版本与自更新：可查看完整或简短版本信息，检查是否有新版本，下载并安装最新版，更新时会替换可执行文件并更新本地文件。"
compatibility: opencode
---

---
name: cctl
description: 使用 cctl 命令行工具登录 Cybertron，并通过 CLI 查询/创建任务、管理镜像、项目和资源池。当用户明确要求“用 CLI / cctl 操作”时使用。
---

# cctl — Cybertron CLI

`cctl` 是 Cybertron 平台命令行工具，源码位于 `cmd/cctl/`。版本通过 `-ldflags` 在编译时注入。

## 1. 当前可用顶层命令

当前 root command 已挂载的命令只有这些：

```bash
cctl login
cctl logout
cctl version
cctl update

cctl job
cctl pytorchjob
cctl notebook
cctl devspace

cctl image
cctl project
cctl pool
```

## 2. 全局约定

- 配置目录：`~/.cybertronctl/`
- 保存内容：`token`、`server`、`token_expire_at`
- server 选择优先级：`CCTL_SERVER` > 本地保存的 server
- token 选择优先级：`CYBERTRON_TOKEN` > 本地保存的 token
- 输出格式：
  - `-o table|json|yaml`
  - `-q, --quiet`：只输出 ID，一行一个
  - `-F, --fields`：只输出指定 JSON 字段，逗号分隔；设置后会强制走 JSON 输出
- 未显式指定 `-o` 时：
  - 终端里默认 `table`
  - 非 TTY 场景默认 `json`
- 非 TTY 场景下出错时，CLI 会输出结构化 JSON 错误，便于 agent/脚本消费

机器可读输出常用写法：

```bash
cctl job list -o json
cctl image list -q
cctl project list -F name,projectName,status
```

## 3. 认证

### 3.1 登录与登出

```bash
# 默认 modelbest，优先尝试浏览器登录
cctl login

# 指定环境
cctl login -e dev
cctl login -e thunlp

# 强制手动粘贴 token
cctl login -m
cctl login --manual -e dev

# 直接保存 token
cctl login <token>
cctl login <token> -e dev

# 登出
cctl logout

# 查看版本
cctl version
```

预定义环境：

| 环境名 | 地址 |
|--------|------|
| `modelbest` | `https://cybertron.modelbest.co` |
| `thunlp` | `http://cybertron.thunlp.org` |
| `dev` | `https://cybertron.ali-dev.modelbest.co` |

### 3.2 认证行为说明

- `cctl login` 默认先走浏览器登录，底层依赖 `/auth/cli/session`
- 如果服务端还没实现 CLI session 登录，CLI 会自动回退到手动粘贴 token
- 登录成功后会保存 token 和 server，并尝试调用 `/v2/clusters?page_size=1` 验证 token
- 若保存的是浏览器登录得到的 token，CLI 会基于 `token_expire_at` 在临近过期时自动刷新
- 若请求返回 `401`，CLI 也会尝试自动刷新后再重试一次
- 如果使用 `CYBERTRON_TOKEN` 环境变量注入 token，则不会做本地自动刷新

## 4. 任务命令

四种任务类型分别对应独立顶层命令，CLI 会自动注入 `kind`：

| 命令 | 别名 | 任务类型 |
|------|------|----------|
| `cctl job` | `jobs`, `j` | `BATCH` |
| `cctl pytorchjob` | `pytorchjobs`, `pj`, `ptj` | `PYTORCHJOB` |
| `cctl notebook` | `notebooks`, `nb` | `NOTEBOOK` |
| `cctl devspace` | `devspaces`, `ds` | `DEVSPACE` |

### 4.1 当前已挂载的子命令

```bash
# 列表
cctl job list [--project X] [--cluster X] [--status X] [--own] [--limit 50] [--page 1] [--web]

# 详情
cctl job get <id-or-name> [--web]

# 创建
cctl job create ...
cctl pytorchjob create ...
cctl notebook create ...
cctl devspace create ...

# 停止
cctl job stop <id-or-name> [--reason "..."]

# 日志
cctl job logs <id-or-name> [--pod <name>] [--tail 100]

# 复制
cctl job copy <id-or-name> [--dry-run] [覆盖字段...]
```

通用别名：

- `list`：`ls`, `l`
- `get`：`g`, `describe`, `desc`
- `stop`：`kill`
- `logs`：`log`
- `copy`：`cp`, `clone`

### 4.2 列表与详情

```bash
# 过滤训练任务
cctl job list --project my-project --cluster paratera --status RUNNING --own

# 直接打开 Web 页面
cctl job list --web
cctl job get 1234 --web
```

- `list --web` 会直接打开任务列表页
- `get --web` 会优先打开 `dashboardUrl`，否则退化到 `/job-detail?id=<task-id>`

### 4.3 创建任务

所有类型通用的必填参数：

- `--project`
- `--cluster`
- `--image`
- `--resource-pool`

按任务类型追加要求：

| 参数 | `BATCH` | `PYTORCHJOB` | `NOTEBOOK` | `DEVSPACE` |
|------|---------|--------------|------------|------------|
| `--entry` | 必填 | 必填 | 非必填 | 非必填 |
| `--workers` | - | 必填 | - | - |
| `--duration` | - | - | 必填 | 非必填 |

常用可选参数：

- `--priority HIGH|NORMAL|PREEMPTABLE`
- `--gpu`
- `--gpu-model`
- `--cpu`
- `--memory`
- `--env KEY=VALUE`，可重复传
- `--requeue`
- `--namespace`
- `--code-type git`
- `--git-path`
- `--git-ref`

典型示例：

```bash
# BATCH
cctl job create \
  --project my-project \
  --cluster gpu-cluster \
  --resource-pool training-pool \
  --image nvcr.io/nvidia/pytorch:24.01-py3 \
  --gpu 8 --gpu-model A100 \
  --entry "python train.py --epochs 100"

# PYTORCHJOB
cctl pytorchjob create \
  --project my-project \
  --cluster gpu-cluster \
  --resource-pool training-pool \
  --image my-training:latest \
  --gpu 8 --gpu-model H100 \
  --workers 4 \
  --entry "torchrun --nproc_per_node=8 train.py"

# NOTEBOOK
cctl notebook create \
  --project my-project \
  --cluster gpu-cluster \
  --resource-pool training-pool \
  --image jupyter:latest \
  --gpu 1 --duration 240
```

创建行为说明：

- `--resource-pool` 可以传资源池 `ID`、`name` 或 `alias`
- `--cpu` / `--memory` 未显式给定时，CLI 可能调用 `/resources/recommend` 自动补全推荐值
- `--code-type=git` 时必须补 `--git-path`
- 支持从 JSON 文件创建，指定 `-f` 后其余 flag 会被忽略

任务 JSON 支持两种格式：

```json
{
  "task": {
    "kind": "BATCH",
    "project": "my-project",
    "cluster": "gpu-cluster",
    "resourcePool": "training-pool",
    "image": "nvcr.io/nvidia/pytorch:24.01-py3",
    "resources": {
      "gpuCount": 8,
      "gpuModel": "A100",
      "cpu": 32,
      "memory": "128Gi"
    },
    "entry": "python train.py"
  }
}
```

也支持直接传裸 `Task` 对象，不带 `"task"` 包装。

### 4.4 日志与停止

```bash
cctl job stop 1234 --reason "manual stop"
cctl job logs 1234 --tail 200
cctl job logs 1234 --pod task-1234-worker-0
```

- `logs` 只支持当前处于 `RUNNING` 状态的任务
- 未指定 `--pod` 时，默认取主 pod

### 4.5 复制任务

```bash
# 先预览
cctl job copy 1174 --image new-image:latest --dry-run

# 再提交
cctl job copy 1174 --image new-image:latest
```

`copy` 支持覆盖这些字段：

- `--image`
- `--entry`
- `--priority`
- `--gpu`
- `--gpu-model`
- `--cpu`
- `--memory`
- `--workers`
- `--duration`
- `--project`
- `--cluster`
- `--git-ref`
- `--dry-run`

## 5. 镜像命令

```bash
# 列表 / 详情
cctl image list [--usage training|inference] [--status X] [--group N] [--own] [--limit 50] [--page 1]
cctl image get <name-or-id>

# 创建
cctl image create \
  --image-name pytorch-24.01 \
  --url nvcr.io/nvidia/pytorch:24.01-py3 \
  --usage training \
  [--canonical-name "..."] \
  [--description "..."] \
  [--source "..."] \
  [--hub-url "..."] \
  [--group N]

# 从 JSON 创建
cctl image create -f image.json

# 更新
cctl image update <name-or-id> [--image-name ...] [--url ...] [--canonical-name ...] [--usage ...] [--description ...] [--source ...] [--hub-url ...] [--group N]

# 删除 / 同步
cctl image delete <name-or-id>
cctl image sync <name-or-id>
```

镜像 JSON 示例：

```json
{
  "image": {
    "imageName": "pytorch-24.01",
    "url": "nvcr.io/nvidia/pytorch:24.01-py3",
    "canonicalName": "nvidia/pytorch:24.01-py3",
    "usage": "training",
    "description": "PyTorch 24.01"
  }
}
```

也支持直接传裸 `Image` 对象。

## 6. 项目命令

```bash
cctl project list [--name X] [--own] [--limit 50]
cctl project get <name-or-id>
cctl project create --name my-project [--description "..."]
```

项目别名：

- `project`：`projects`, `proj`

## 7. 资源池命令

```bash
cctl pool list [--own] [--role training|inference]
cctl pool get <name|alias|id>
```

资源池别名：

- `pool`：`pools`, `pl`

说明：

- 资源池当前桥接的是 v1 接口：`/api/resource_pool/`
- `pool list --own` 时会附带 `role` 过滤；默认 `training`
- `pool get` 内部会先解析资源池 name/alias/id，再去查详情

## 8. 版本与自更新

```bash
# 查看完整版本信息（版本号、commit、构建时间）
cctl version

# 只输出版本号
cctl version --short

# 检查是否有新版本
cctl update --check

# 下载并安装最新版
cctl update
```

说明：

- 版本信息通过 `-ldflags` 在编译时注入（`version`、`commit`、`date`）
- `cctl update` 从 OSS 下载最新二进制替换当前可执行文件
- 同时更新本地 `.cursor/skills/cctl/SKILL.md`（如果已存在）
- 可通过 `CCTL_OSS_BASE` 环境变量覆盖下载服务器地址

## 9. 当前不要依赖的命令

以下能力虽然在源码里已经有实现函数，但当前 root command 没有挂载，不应在 skill 里当成可用命令：

- `cctl cluster ...`
- `cctl notebook extend ...`
- `cctl devspace restore ...`
- `cctl devspace heartbeat ...`
- `cctl job queue-position ...`

如果后续把这些命令正式挂到 `newRootCmd()` / `newKindAliasCmd()`，再把它们补回 skill。

## 10. 推荐工作流

### 10.1 登录后创建训练任务

```bash
cctl login -e dev
cctl pool list --own
cctl image list --usage training --limit 10
cctl job create \
  --project my-project \
  --cluster gpu-cluster \
  --resource-pool platform \
  --image nvcr.io/nvidia/pytorch:24.01-py3 \
  --gpu 8 \
  --entry "python train.py"
```

### 10.2 用机器可读方式筛选结果

```bash
cctl job list -F name,status,cluster
cctl image list -q
cctl project list -o yaml
```
