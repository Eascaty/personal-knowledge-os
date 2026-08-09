# 版本记录

## Unreleased

## 0.3.0 — 2026-08-09

- 增加 Java 21 + Spring Boot 3.5 的只读知识服务。
- 增加健康检查、分类树、知识列表、详情与基础搜索 API v1。
- Java API 仅返回公开知识，并对来源绝对路径进行结构性裁剪。
- 增加 7 项 JUnit、SQLite 集成、MockMvc 和 canonical JSON 契约测试。
- GitHub Actions 增加 Java 21 Maven 构建与 JaCoCo 覆盖率报告。

## 0.2.0 — 2026-08-09

- 使用 Apache License 2.0 开源。
- 增加贡献指南、安全策略、Issue/PR 模板、Dependabot 和 GitHub Actions CI。
- 明确 Python MVP 与 Java 21/Spring Boot 增量演进路线。
- 公开仓库仍严格排除真实知识、数据库、私密导出和生成站点。
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
