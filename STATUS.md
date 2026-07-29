# 项目状态

- 更新时间：2026-07-30（Asia/Shanghai）
- 阶段：本地全链路完成并通过发布前审查
- 总体状态：可本地运行；等待用户以后配置 Cloudflare 账号后上线

## 已实现

- 系统采用严格的专业母子树，并允许无限增加一级模块和子级。
- 当前已知主干：
  - `金融 / 财经 / 信用卡 / 美股`
  - `AI / Agent / 智能体`
  - `技术 / 程序员 / Java开发`
- Java 开发允许继续展开 JVM、并发、Spring、数据库、微服务等专业子树。
- 核心处理在 Mac 本地完成，不使用付费模型 API。
- 最终知识库需要在线随时访问，Mac 关机后线上现有版本仍可打开。
- 推荐使用 Cloudflare Pages 静态托管和 Cloudflare Access 私密登录。
- 账号聊天接入与批量网页爬虫暂缓。
- Python 3.9 标准库 CLI 与 SQLite schema。
- 文件扫描、SHA-256 去重、不可变 raw、Markdown 标准化。
- 文本、Markdown、代码、HTML、DOCX；PDF 可选调用本地 `pdftotext`。
- 规则提炼器默认零依赖运行；可选本地 Ollama。
- 三阶段可重试队列、失败隔离、FTS5 中文搜索。
- 严格逐级母子分类、Vault、canonical JSON、搜索和关系图数据。
- 原生 HTML/CSS/JS 静态网站、响应式、PWA、private/public 隔离。
- 项目锁、SQLite 一致性备份、隐私、断链、数据库和发布门禁。
- `scripts/run-pipeline` 单命令离线全链路。
- launchd 项目内模板，未修改 macOS 系统目录。

## 已验证环境

- 电脑：Apple Silicon M3
- 内存：16GB
- 可用磁盘：约247GB（验证时）
- SQLite：支持 FTS5 与 trigram
- 推荐本地模型规模：4B–8B 量化模型，单并发

## 最近验证

- Python 3.9 语法解析通过。
- 18 项 unittest 全部通过。
- 三份样例生成9个任务，全部完成。
- 重复运行不新增资料或任务。
- 金融、AI、Java/G1 三条路径全部正确。
- 发布门禁会拒绝 private 候选包冒充 public。
- 分类节点删除后资料进入“待归类”，不会生成孤立引用。
- symlink 和越界 raw 路径回归测试通过。
- SQLite、隐私、断链、PWA 缓存和公开过滤检查通过。
- 正式项目目录已完成干净初始化、18项复验与一致性初始备份。
- 桌面端和手机端浏览器验收通过，页面交互正常且控制台0错误。

## 尚需用户以后完成

1. 把真实资料放入 `inbox/files/`。
2. 如需持续后台运行，再明确选择是否安装 launchd 模板。
3. 登录 Cloudflare，创建 Pages 项目并配置 Access 精确邮箱策略。
4. 账号聊天、网址抓取、OCR 和音视频属于后续输入适配器。
