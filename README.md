# Personal Knowledge OS

[![CI](https://github.com/Eascaty/personal-knowledge-os/actions/workflows/ci.yml/badge.svg)](https://github.com/Eascaty/personal-knowledge-os/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.9%2B-3776AB.svg)](pyproject.toml)

一个本地优先、隐私友好、零付费 API 的个人知识处理系统。它把本地资料转换为可搜索的 Markdown、SQLite、知识树、关系图和静态网站，同时默认阻止私人内容进入公开构建。

这是项目的统一根目录。设计文档、工作流、配置、操作记录、程序与测试均保存在这里。

## 项目特点

- **本地优先**：解析、去重、分类、搜索与建站均可离线完成。
- **隐私默认安全**：资料默认 `private`，公开构建采用显式白名单。
- **零付费依赖**：核心只使用 Python 标准库和 SQLite，不要求云 API。
- **可恢复与可审计**：原始资料不可变保存，任务可重试，关键操作有记录。
- **可扩展分类**：使用严格父子树表达专业归属，关系边表达跨领域联系。
- **工程化验证**：18 项自动测试覆盖幂等、越界路径、隐私门禁和完整流水线。

## 当前目标

建立一套零付费 API、本地优先、自动整理并可在线随时访问的个人知识系统：

```text
投入本地文件
→ 本地解析与去重
→ 本地 AI 提炼
→ 逐级归入专业母子树
→ 生成 Markdown、搜索索引与知识地图
→ 自动构建静态网站
→ 通过发布门禁
→ 登录云账号后发布为受保护的线上知识库
```

当前阶段暂不实施 ChatGPT/Gemini 账号接入，也不优先开发批量网页爬虫。

## 快速入口

- [总体设计](docs/knowledge-system-design.md)
- [工程目录与模块分工](docs/project-structure.md)
- [当前状态](STATUS.md)
- [自动化工作流](workflow/WORKFLOW.md)
- [专业分类骨架](config/taxonomy.json)
- [测试报告](docs/test-report.md)
- [代码审查](docs/code-review.md)
- [Java 演进路线](docs/java-roadmap.md)
- [设计决策](logs/decisions.md)
- [操作记录](logs/operations.md)
- [本次对话摘要](logs/conversation-summary.md)

## 目录约定

```text
knowledge/
├── AGENTS.md                 # 后续 Codex 工作规则
├── README.md
├── STATUS.md
├── pyproject.toml            # Python 包与 kb 命令
├── config/                   # 分类、运行和发布配置
├── docs/                     # 活文档与示意资料
├── workflow/                 # 自动化流程说明
├── logs/                     # 决策、操作和对话摘要
├── inbox/                    # 用户投放入口
├── data/                     # 私密原始数据、数据库和缓存
├── vault/                    # 可阅读 Markdown 知识树
├── src/knowledge_os/         # 核心、网站、运维和发布代码
├── site/                     # 静态网站资源与构建产物
├── exports/                  # 对外导出；只有 public 可上传
├── ops/                      # launchd 等可选运维模板
├── scripts/                  # 本地命令与调度脚本
└── tests/                    # 自动化测试
```

## 日常使用目标

把资料放入 `inbox/files/`，然后运行：

```bash
./scripts/run-pipeline
```

这一个命令会离线完成扫描、去重、解析、分类、知识页、搜索、关系图、网站
构建和发布前检查。无需安装 Python 包，也不会发送网络请求。

查看本地网站：

```bash
./scripts/preview-site
```

浏览器打开 `http://127.0.0.1:8765`。

其他常用命令：

```bash
./scripts/kb status
./scripts/kb query "G1"
./scripts/doctor
./scripts/backup
./scripts/test
```

`ops/launchd/` 提供每15分钟自动执行的模板，但按照“不修改项目外目录”的
要求，目前没有自动安装。Cloudflare 发布适配器也默认只生成计划；真实上线
仍需用户以后登录自己的 Cloudflare 账号并启用 Access。

## 开源边界

公开仓库只包含程序、配置示例、虚构测试资料和文档。真实知识库、SQLite 数据库、收件箱、私密站点、备份和凭据均由 `.gitignore` 排除。请勿把自己的资料放入公开提交。

## Java 路线

当前 Python 版本是已验证的零依赖 MVP。后续将在不破坏现有流水线的前提下增加 Java 21 + Spring Boot 服务模块，逐步实现领域 API、全文搜索、幂等导入和容器化部署。具体里程碑见 [Java 演进路线](docs/java-roadmap.md)。

## 参与贡献

请先阅读 [贡献指南](CONTRIBUTING.md) 和 [安全策略](SECURITY.md)。提交前至少运行：

```bash
./scripts/test
```

本项目采用 [Apache License 2.0](LICENSE) 开源。
