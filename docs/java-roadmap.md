# Java 演进路线

现有 Python 标准库实现是经过端到端验证的本地优先 MVP。Java 演进采用增量替换，不推倒已工作的流水线，也不制造无业务价值的模块。

## 目标技术栈

- Java 21
- Spring Boot 3
- Maven
- Spring Web 与 Bean Validation
- SQLite/PostgreSQL 可替换持久层
- SQLite FTS5；数据规模或分词需求超过单机 SQLite 边界后再评估 Lucene
- JUnit 5、Testcontainers、JaCoCo
- OpenAPI、Docker、GitHub Actions

## 里程碑

### J1：领域模型与只读 API

- 状态：已完成（2026-08-09）。
- 已建立 `apps/api/` Maven 模块。
- 已映射知识条目、分类节点、脱敏来源和关系边。
- 已提供健康检查、分类树、知识条目和搜索只读 API。
- API 只返回 `public` 条目，不返回 `origin`、`raw_path` 或本机绝对路径。
- 已使用契约测试证明 Java API 的核心字段与现有 canonical JSON 一致。
- 已将 `packages/contracts/openapi.yaml` 和 canonical JSON Schema 固化为跨应用 v1 契约，Java 与 Python 共用同一份虚构样例。
- 已通过 JDK 21、JUnit 5、SQLite 集成测试、MockMvc 和 JaCoCo 验证。

### J2：搜索服务

- 状态：已完成（2026-08-12），待 PR 合并。
- 已将独立搜索接口升级为 SQLite FTS5 trigram，并使用 BM25 对标题、标签、分类路径、摘要和正文加权排序。
- 低于3个字符的查询、包含 FTS 语法字符的查询及无 FTS 命中的查询自动降级为参数化 LIKE。
- 搜索结果提供 `[[...]]` 纯文本高亮标记、分页、稳定排序和可见命中片段；数据库查询始终过滤 private 内容。
- 查询上限固定为200字符，通配符按普通字符处理，返回片段进行 HTML 转义。
- 查询、分页、排序、高亮、隐私、特殊字符和降级路径均有集成测试。
- 固定2,000条中文资料的本机基准见 [`benchmarks/java-search.md`](benchmarks/java-search.md)。

### J3：导入与幂等

- 将文件哈希去重、Markdown 导入和任务状态机迁移到 Java。
- 使用数据库事务和 Testcontainers 验证重复执行、失败重试和回滚。

### J4：可部署服务

- 提供 Docker Compose 开发环境。
- 基于现有 OpenAPI v1 契约增加可观测性和发布流水线。
- 保留完全本地、无账号、无付费 API 的默认运行模式。

## 工程验收标准

每个里程碑应具备 Issue、Pull Request、自动测试和 Release 记录，并能解释架构取舍、真实问题与性能数据。
