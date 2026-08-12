# API app

Java 21 + Spring Boot API 默认只读 `workspace/data/state/knowledge.sqlite3` 的 schema v1，并只返回允许暴露的知识字段。

HTTP 服务不拥有导入、分类、迁移或任务状态写入权。控制器只依赖应用服务，应用服务再访问只读仓储；接口以 `packages/contracts/openapi.yaml` 为准。

`GET /api/v1/search?q=并发编程` 优先使用现有 SQLite FTS5 trigram 索引，并通过 BM25 排序；短查询、特殊语法或无 FTS 命中时安全降级为参数化 LIKE。结果使用 `[[...]]` 标出命中词，片段已做 HTML 转义，查询始终包含 `visibility='public'` 过滤。

在仓库根目录使用 `./scripts/java-test` 运行全部测试与覆盖率门禁，使用 `./scripts/java-service` 启动本地服务。

J3 提供独立的离线文件导入 CLI：`./scripts/java-import <文件>`。它只写入不可变 raw、source、初始 extract 任务和审计事件，不开放 HTTP 写接口，也不执行分类、提炼或 schema 迁移。Java 与 Python 写入共用 `workspace/data/state/knowledge-os.lock`，有其他写任务时立即拒绝运行。
