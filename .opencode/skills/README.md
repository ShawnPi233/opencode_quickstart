# Project Skills

这个目录用于存放 `opencode` 的项目级 skills。

这些 skill 的目标不是替代全局能力，而是让 agent 在当前项目里更快进入状态、少走弯路，并在安装完成后直接获得更稳定的协作体验。

## 当前已预置

### `opencode-bootstrap`
- 用途：安装完 `opencode` 后做项目级初始化检查
- 适合场景：首次接入、检查 `.opencode` 结构、建立最小工作流

### `repo-onboarding`
- 用途：快速识别仓库结构、技术栈、启动命令和关键入口
- 适合场景：第一次进入项目、准备动手修改前建立上下文

### `deploy-helper`
- 用途：判断部署方式、整理上线步骤、排查部署失败
- 适合场景：部署、发布、服务启动异常、环境不一致

### `project-conventions`
- 用途：沉淀项目级实现边界、验证顺序和协作习惯
- 适合场景：希望 agent 更克制、更贴近项目现状地修改代码

### `env-doctor`
- 用途：检查本地开发与部署前环境是否健康
- 适合场景：依赖缺失、权限问题、代理异常、环境不确定

### `log-troubleshooter`
- 用途：从日志中提炼根因并给出最短修复路径
- 适合场景：启动失败、服务报错、日志很长但需要快速定位问题

### `git-safe-helper`
- 用途：安全检查工作区、梳理改动边界、辅助提交准备
- 适合场景：提交前检查、差异梳理、避免误提交敏感文件或无关改动

### `test-and-fix`
- 用途：围绕当前改动做最小相关测试并修复高相关失败
- 适合场景：改完代码后验证、定向跑测试、识别历史失败与新增失败

## 推荐使用顺序

### 安装完成后
1. `opencode-bootstrap`
2. `env-doctor`
3. `project-conventions`

### 第一次进入仓库
1. `repo-onboarding`
2. `project-conventions`
3. `env-doctor`

### 开发与修改阶段
1. `repo-onboarding`
2. `test-and-fix`
3. `git-safe-helper`

### 部署与排障阶段
1. `deploy-helper`
2. `log-troubleshooter`
3. `env-doctor`

## 设计原则

- 一个 skill 只解决一类问题，避免做成万能指令集。
- 优先只读检查，再做修改或执行动作。
- 优先给结论、最短路径和边界条件，不堆砌过程。
- 尽量复用项目现有结构和约定，不额外发明复杂体系。

## 后续扩展建议

后续可以按需要继续增加这些 skill：

- `local-dev`：统一本地启动、调试、环境变量和 mock 约定
- `docs-writer`：生成 README、接手文档、部署说明和 FAQ
- `dependency-upgrade`：安全升级依赖并给出验证路径
- `release-notes`：基于变更生成发布说明和升级摘要

## 维护建议

- 新增 skill 时，保持 frontmatter 和章节结构一致。
- 优先补充项目真实高频场景，不为了凑数量而增加 skill。
- 如果仓库逐渐形成稳定约定，可把一部分内容上移到 `AGENTS.md`，把 skill 保持为面向场景的能力包。
