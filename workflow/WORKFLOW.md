# 自动化工作流

## 1. 用户入口

第一阶段只保留两个明确入口：

```text
workspace/inbox/files/       放入本地文件
workspace/inbox/urls.txt     一行一个手工网址
```

不进行全网递归抓取。

## 2. 已实现命令

```text
./scripts/run-pipeline
./scripts/kb init
./scripts/kb ingest <文件或目录>
./scripts/kb run
./scripts/kb query "问题"
./scripts/kb build-data
./scripts/doctor
./scripts/backup
./scripts/test
```

日常只需 `./scripts/run-pipeline`。项目内 launchd 模板也调用该命令，但不会
未经授权安装到系统目录。

## 3. 作业状态

```text
NEW
→ RECEIVED
→ EXTRACTED
→ DEDUPED
→ CLASSIFIED
→ ENRICHED
→ INDEXED
→ BUILT
→ PUBLISHED

失败 → RETRY → QUARANTINE
```

每一阶段必须：

- 有幂等键。
- 在 SQLite 事务中提交状态。
- 可独立重试。
- 记录输入哈希、配置版本和输出。
- 不覆盖人工编辑。

## 4. 分类工作流

```text
读取 taxonomy 当前父节点
→ 获取该父节点直接子级
→ 关键词和 FTS5 生成候选
→ 本地模型结构化选择
→ 规则校验
→ 选择已有节点或创建允许的新子节点
→ 写入一个主路径
→ 生成零个或多个辅助关系
```

模型不得绕过父节点直接把资料放入任意深层位置。

## 5. 构建工作流

```text
SQLite + vault Markdown
→ taxonomy.json
→ 按一级模块拆分内容数据
→ 按模块生成搜索索引
→ 生成关系图数据
→ 生成报告
→ Python 标准库生成原生 HTML/CSS/JavaScript
→ workspace/site/dist/
```

数据包接近5MiB时继续按子树拆分，避免形成过大的线上文件。

## 6. 发布工作流

发布条件：

- 内容哈希与线上版本不同。
- 距离最后一次变更至少15分钟。
- 当日部署少于10次。
- 分类、断链、隐私、搜索和页面测试全部成功。

发布顺序：

```text
build-data
→ build-site
→ database/privacy/broken-link/site-bundle gate
→ Cloudflare dry-run plan
→ 用户显式允许真实网络发布
→ 写入 deployment 记录
```

任何一步失败：

- 不替换当前线上版本。
- 记录失败原因。
- 根据策略重试。
- 达到最大次数后进入隔离状态。

## 7. 健康报告

每日生成：

- 待处理任务数
- 最近成功与失败
- 隔离资料
- 磁盘剩余空间
- 数据库完整性
- 孤立节点
- 断链
- 缺少来源的观点
- 线上版本和本地版本
- 上次成功发布时间

## 8. 后续输入适配器

账号聊天、RSS、网页采集、OCR 与音视频均作为独立输入适配器接入统一 `sources/jobs` 接口，不改变分类、知识生成和发布核心。
