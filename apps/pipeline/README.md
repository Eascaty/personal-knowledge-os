# Pipeline app

Python 本地流水线是知识系统主写入方和唯一任务处理方，负责接收、去重、解析、分类、提炼、SQLite schema、Vault、静态数据生成与发布门禁。可选 Java CLI 只能按同一 schema 将本地文件安全入队，不能处理任务或迁移数据库。

日常使用仍从仓库根目录运行 `scripts/`，不直接依赖本目录内部路径。
