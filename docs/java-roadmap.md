# Java 演进路线

现有 Python 标准库实现是经过端到端验证的本地优先 MVP。Java 演进采用增量替换，不推倒已工作的流水线，也不为简历展示制造无业务价值的模块。

## 目标技术栈

- Java 21
- Spring Boot 3
- Maven
- Spring Web 与 Bean Validation
- SQLite/PostgreSQL 可替换持久层
- Apache Lucene 或数据库全文检索
- JUnit 5、Testcontainers、JaCoCo
- OpenAPI、Docker、GitHub Actions

## 里程碑

### J1：领域模型与只读 API

- 状态：已完成（2026-08-09）。
- 已建立 `knowledge-service-java/` Maven 模块。
- 已映射知识条目、分类节点、脱敏来源和关系边。
- 已提供健康检查、分类树、知识条目和搜索只读 API。
- API 只返回 `public` 条目，不返回 `origin`、`raw_path` 或本机绝对路径。
- 已使用契约测试证明 Java API 的核心字段与现有 canonical JSON 一致。
- 已通过 JDK 21、JUnit 5、SQLite 集成测试、MockMvc 和 JaCoCo 验证。

### J2：搜索服务

- 将 J1 的参数化基础搜索升级为 SQLite FTS5 或 Lucene 中文全文搜索。
- 为查询、分页、排序和高亮建立集成测试。
- 记录固定数据集上的基准结果。

### J3：导入与幂等

- 将文件哈希去重、Markdown 导入和任务状态机迁移到 Java。
- 使用数据库事务和 Testcontainers 验证重复执行、失败重试和回滚。

### J4：可部署服务

- 提供 Docker Compose 开发环境。
- 增加 OpenAPI 文档、可观测性和发布流水线。
- 保留完全本地、无账号、无付费 API 的默认运行模式。

## 简历验收标准

只有已经实现并验证的内容才写入简历。每个里程碑应具备 Issue、Pull Request、自动测试和 Release 记录，并能解释架构取舍、真实问题与性能数据。
