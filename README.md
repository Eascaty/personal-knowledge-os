# Personal Knowledge OS

这是个人知识体系项目的统一根目录。设计文档、工作流、配置、操作记录、后续程序与测试均应保存在这里。

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
