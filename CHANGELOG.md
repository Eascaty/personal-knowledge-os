# 版本记录

## Unreleased

- 使用 Apache License 2.0 开源。
- 增加贡献指南、安全策略、Issue/PR 模板、Dependabot 和 GitHub Actions CI。
- 明确 Python MVP 与 Java 21/Spring Boot 增量演进路线。
- 公开仓库仍严格排除真实知识、数据库、私密导出和生成站点。

## 0.2.0 — 2026-07-30

- 完成本地文件到 SQLite、Markdown、全文搜索、知识图和静态网站的闭环。
- 新增 `scripts/run-pipeline` 单命令自动化和项目锁。
- 新增 private/public 构建、PWA、安全响应头与 Cloudflare 发布适配。
- 新增数据库、磁盘、隐私、断链、构建清单和一致性备份检查。
- 修复 public 发布门禁、分类节点退休、symlink、raw 路径越界和并发竞态。
- 18 项自动测试与三资料端到端样例全部通过。

## 0.1.0 — 2026-07-27

- 建立 `$HOME/ai/knowledge` 单一工程根目录。
- 固化金融、AI、技术三条专业母子链路与 Java 子树。
- 采用 Python 标准库、SQLite、Markdown/JSON 和纯静态网站的零依赖核心方案。
- 默认本地运行、默认私密、默认不连接外网和不执行真实发布。
- 开始实现入库、去重、分类、搜索、知识树、知识图、网站、健康检查、备份和发布门禁。
