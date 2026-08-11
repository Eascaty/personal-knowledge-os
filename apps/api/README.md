# API app

Java 21 + Spring Boot 只读 API，只读取 `workspace/data/state/knowledge.sqlite3` 的 schema v1，并只返回允许暴露的知识字段。

它不拥有导入、分类、迁移或任务状态写入权。HTTP 控制器只依赖应用服务，应用服务再访问只读仓储；接口以 `packages/contracts/openapi.yaml` 为准。

`GET /api/v1/search?q=并发编程` 优先使用现有 SQLite FTS5 trigram 索引，并通过 BM25 排序；短查询、特殊语法或无 FTS 命中时安全降级为参数化 LIKE。结果使用 `[[...]]` 标出命中词，片段已做 HTML 转义，查询始终包含 `visibility='public'` 过滤。

在仓库根目录使用 `./scripts/java-test` 运行全部测试与覆盖率门禁，使用 `./scripts/java-service` 启动本地服务。
