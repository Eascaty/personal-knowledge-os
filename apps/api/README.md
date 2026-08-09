# API app

Java 21 + Spring Boot 只读 API，只读取 `workspace/data/state/knowledge.sqlite3` 的 schema v1，并只返回允许暴露的知识字段。

它不拥有导入、分类、迁移或任务状态写入权。使用仓库根目录 `./scripts/java-test` 和 `./scripts/java-service`。
