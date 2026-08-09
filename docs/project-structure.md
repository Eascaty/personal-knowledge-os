# 工程目录与模块分工

> 项目根目录：`$HOME/ai/knowledge`

本工程把“用户输入、不可变数据、程序代码、网站产物和运维模板”分开，避免后续资料越来越多时互相污染。

```text
knowledge/
├── README.md                       # 总入口与最短使用说明
├── STATUS.md                       # 当前能做什么、最近测试、下一步
├── AGENTS.md                       # 后续自动维护本工程时必须遵守的规则
├── CHANGELOG.md                    # 面向用户的版本变化
├── LICENSE                         # Apache License 2.0
├── CONTRIBUTING.md                 # 贡献流程与隐私边界
├── SECURITY.md                     # 漏洞报告与安全支持范围
├── pyproject.toml                  # Python 包和 kb 命令
├── .github/                        # CI、Dependabot、Issue 与 PR 模板
│
├── config/
│   ├── taxonomy.json               # 唯一权威专业母子树
│   └── settings.example.json       # 无密钥运行配置示例
│
├── docs/
│   ├── knowledge-system-design.md  # 总体架构活文档
│   ├── java-roadmap.md             # Java 21/Spring Boot 增量演进路线
│   └── project-structure.md        # 本文件
├── workflow/
│   └── WORKFLOW.md                 # 输入到发布的状态机
├── logs/
│   ├── decisions.md                # 长期设计取舍
│   ├── operations.md               # 实质操作审计
│   └── conversation-summary.md     # 需求来历与边界
│
├── src/knowledge_os/
│   ├── cli.py                      # kb 命令入口与全链路编排
│   ├── config/                     # 配置加载和分类树校验
│   ├── db/                         # SQLite schema、事务与全文搜索
│   ├── ingest/                     # 文件接收、解析、哈希和去重
│   ├── knowledge/                  # 摘要、逐级分类、Markdown 与图数据
│   ├── ai/                         # 规则引擎和可选 Ollama 适配器
│   ├── site/                       # 纯静态网站生成器
│   ├── operations/                 # 锁、健康检查、备份和隐私检查
│   └── publish/                    # 发布门禁和 Cloudflare 可选适配
│
├── inbox/
│   ├── files/                      # 日常只需把文件扔到这里
│   └── urls.txt                    # 后续手工网址入口
├── data/
│   ├── raw/                        # 按哈希保存的不可变原始资料
│   ├── normalized/                 # 统一后的 Markdown/文本
│   ├── state/                      # SQLite 状态与项目锁
│   ├── cache/                      # 可安全重建的临时缓存
│   └── quarantine/                 # 失败且需要查看的输入
├── vault/                          # 按专业母子树生成的人类可读 Markdown
│
├── site/
│   ├── static/                     # 手写静态资源
│   └── dist/                       # 每次重新生成的私密站点
├── exports/
│   ├── private/                    # 私密快照/导出，禁止对外同步
│   └── public/                     # 仅显式 public 内容的公开构建
│
├── ops/launchd/                    # 只提供模板，不自动改系统设置
├── scripts/                        # 项目内一键运行、检查、预览脚本
└── tests/
    ├── fixtures/                   # 固定样本
    ├── test_core.py                # 入库、去重、分类与查询
    ├── test_site.py                # 私密/公开站点和防泄露
    ├── test_operations.py          # 健康检查、备份和发布门禁
    └── test_e2e.py                 # 从 inbox 到 site/dist 的完整闭环
```

## 边界与责任

- `src/` 是程序；不能在这里保存用户资料。
- `inbox/` 是唯一日常入口；成功处理后原文件仍保留，重复运行不会重复入库。
- `data/raw/` 是事实来源；程序只追加，不覆盖、不自动删除。
- `vault/`、`site/dist/` 和 `exports/` 都是派生产物，可从 SQLite 和原始资料重建。
- `config/taxonomy.json` 是专业树唯一权威配置；网站中的分类 JSON 都由它生成。
- `exports/public/` 是唯一允许公开上传的内容；私密站点也必须使用 Cloudflare Access 保护。
- `ops/launchd/` 只是可审查模板。本项目不会在未明确启用时修改 `~/Library/LaunchAgents`。

## 模块依赖方向

```text
config + db
   ↑       ↑
ingest → knowledge → site
                 ↘ operations → publish
```

底层模块不能反向依赖网站或发布模块。真实网络发布不属于本地核心的完成条件。
